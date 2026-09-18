"""The contract between a camera worker and the camera object it drives.

TriggerableCameraWorker duck-types its camera: it calls a set of methods and
reaches for two attributes, and nothing declares that set anywhere the worker
can check. A camera missing one of them fails partway through a shot, on
hardware, which is the worst place to find out -- with a NotImplementedError
naming it if it inherits TriggerableCameraInterface, and an AttributeError if
it does not.

The first test here is that list, checked against every camera in the tree. The
rest pin the behaviour of the shared grab_multiple, because each vendor's
acquisition loop is being replaced by it and the replacement has to keep every
one of their failure behaviours exactly: IMAQdx retries on its timeout code and
skips a frame when the shot says not to fail; Pylon and FlyCapture2 retry
forever on their own error classes; Spinnaker and the dummy camera do not retry
at all.
"""
import unittest

from labscript_devices.TriggerableCamera.blacs_workers import (
    TriggerableCameraInterface,
)
from labscript_devices.IMAQdxCamera.blacs_workers import IMAQdx_Camera
from labscript_devices.PylonCamera.blacs_workers import Pylon_Camera
from labscript_devices.SpinnakerCamera.blacs_workers import Spinnaker_Camera
from labscript_devices.FlyCapture2Camera.blacs_workers import FlyCapture2_Camera
from labscript_devices.AndorSolis.blacs_workers import AndorCamera
from labscript_devices.DummyCamera.blacs_workers import Dummy_Camera


# What TriggerableCameraWorker calls on self.camera that no base can supply,
# because there is nothing generic to say: it is all one vendor's API.
VENDOR_MUST_WRITE = [
    'set_attributes',
    'snap',
    'grab',
    'configure_acquisition',
    'stop_acquisition',
    'close',
]

# What the inherited, composing get_attributes_as_dict reaches for. Not in the
# list above because a camera that writes its own get_attributes_as_dict never
# reads an attribute one at a time and owes neither of these.
COMPOSING_DEFAULT_NEEDS = ['get_attribute_names', 'get_attribute']

# Every camera in the tree.
EVERY_CAMERA = [
    IMAQdx_Camera,
    Pylon_Camera,
    Spinnaker_Camera,
    FlyCapture2_Camera,
    AndorCamera,
    Dummy_Camera,
]


def written_by_the_camera(camera, name):
    """Whether this camera writes `name` itself.

    Resolving the name is not enough once every camera inherits
    TriggerableCameraInterface: it supplies a stub for each member of the
    contract, so getattr succeeds whether or not the camera implements it and
    the failure moves to the middle of a shot. What this asks is whether the
    camera brought its own.
    """
    return getattr(camera, name, None) is not getattr(TriggerableCameraInterface, name, None)


class ContractTests(unittest.TestCase):
    def test_every_camera_writes_the_members_only_it_can(self):
        for camera in EVERY_CAMERA:
            for name in VENDOR_MUST_WRITE:
                with self.subTest(camera=camera.__name__, member=name):
                    self.assertTrue(
                        written_by_the_camera(camera, name),
                        f'{camera.__name__} does not implement {name}(); it '
                        f'would inherit the stub, which raises mid-shot',
                    )

    def test_every_camera_in_the_tree_inherits_the_base(self):
        # The rest of the contract -- grab_multiple, abort_acquisition, and the
        # two flags the acquisition loop reads back -- is what inheriting
        # supplies. Asking whether each name resolves would answer itself once
        # the base defines them all, so this asks the question that is really
        # being put: are these six still getting them from there. A camera
        # outside the tree need not inherit; the worker duck-types it.
        for camera in EVERY_CAMERA:
            with self.subTest(camera=camera.__name__):
                self.assertTrue(issubclass(camera, TriggerableCameraInterface))

    def test_every_camera_can_read_its_attributes_as_a_dict(self):
        # Two ways to satisfy this, and every camera takes one of them: write
        # get_attributes_as_dict, the way Pylon and FlyCapture2 do because
        # their APIs hand over the lot in one call, or inherit the composing
        # default and write the two readers it reaches for.
        for camera in EVERY_CAMERA:
            with self.subTest(camera=camera.__name__):
                if written_by_the_camera(camera, 'get_attributes_as_dict'):
                    continue
                missing = [
                    name
                    for name in COMPOSING_DEFAULT_NEEDS
                    if not written_by_the_camera(camera, name)
                ]
                self.assertEqual(
                    missing,
                    [],
                    f'{camera.__name__} inherits the composing '
                    f'get_attributes_as_dict but does not implement '
                    f'{" or ".join(missing)}; it would inherit the stub, '
                    f'which raises mid-shot',
                )

    def test_an_unwritten_member_names_the_camera_and_the_member(self):
        class ACameraMissingSnap(TriggerableCameraInterface):
            pass

        with self.assertRaises(NotImplementedError) as raised:
            ACameraMissingSnap().snap()

        self.assertIn('ACameraMissingSnap', str(raised.exception))
        self.assertIn('snap', str(raised.exception))


class AWaitingForTrigger(Exception):
    """What a camera raises when no frame has arrived yet."""


class ACameraFault(Exception):
    """What a camera's own API raises when something is wrong with it."""


class AScriptedCamera(TriggerableCameraInterface):
    """A camera whose every grab is dictated by the test.

    Each entry of `outcomes` is either an image to return or an exception to
    raise. What the camera considers transient or skippable is set per test, so
    one fake stands in for all five vendors' policies.
    """

    def __init__(self, outcomes, transient=(), skippable=()):
        self.outcomes = list(outcomes)
        self.transient = transient
        self.skippable = skippable
        self.grabs = 0

    def is_transient_grab_error(self, exception):
        return isinstance(exception, self.transient)

    def is_skippable_grab_error(self, exception):
        return isinstance(exception, self.skippable)

    def grab(self):
        self.grabs += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class GrabMultipleTests(unittest.TestCase):
    def test_a_clean_acquisition_collects_every_frame_in_order(self):
        camera = AScriptedCamera([10, 20, 30])

        images = []
        camera.grab_multiple(3, images)

        self.assertEqual(images, [10, 20, 30])

    def test_a_camera_still_waiting_for_a_trigger_is_asked_again(self):
        # IMAQdx on its timeout code, Pylon on TimeoutException, FlyCapture2 on
        # Fc2error: the shot decides when the trigger comes, so the acquisition
        # waits rather than giving up.
        camera = AScriptedCamera(
            [AWaitingForTrigger(), AWaitingForTrigger(), 10, 20],
            transient=AWaitingForTrigger,
        )

        images = []
        camera.grab_multiple(2, images)

        self.assertEqual(images, [10, 20])
        self.assertEqual(camera.grabs, 4)

    def test_a_camera_that_does_not_retry_lets_the_failure_out(self):
        # Spinnaker and the dummy camera declare nothing transient, so their
        # acquisition fails rather than waiting.
        camera = AScriptedCamera([10, AWaitingForTrigger(), 30])

        with self.assertRaises(AWaitingForTrigger):
            camera.grab_multiple(3, [])

    def test_a_real_fault_ends_the_acquisition(self):
        camera = AScriptedCamera(
            [10, ACameraFault(), 30], transient=AWaitingForTrigger
        )

        with self.assertRaises(ACameraFault):
            camera.grab_multiple(3, [])

    def test_a_shot_told_not_to_fail_gives_up_the_frame_and_carries_on(self):
        # IMAQdx's behaviour under exception_on_failed_shot=False: the frame is
        # lost and the acquisition moves to the next exposure.
        camera = AScriptedCamera(
            [10, ACameraFault(), 30], skippable=ACameraFault
        )
        camera.exception_on_failed_shot = False

        images = []
        camera.grab_multiple(3, images)

        self.assertEqual(images, [10, 30])

    def test_a_shot_told_to_fail_fails_on_the_same_error(self):
        camera = AScriptedCamera(
            [10, ACameraFault(), 30], skippable=ACameraFault
        )
        camera.exception_on_failed_shot = True

        with self.assertRaises(ACameraFault):
            camera.grab_multiple(3, [])

    def test_an_abort_stops_between_frames_and_clears_the_flag(self):
        camera = AScriptedCamera([10, 20, 30])
        camera.abort_acquisition()

        images = []
        camera.grab_multiple(3, images)

        self.assertEqual(images, [])
        self.assertEqual(camera.grabs, 0)
        # Cleared, so the next shot is not aborted before it starts.
        self.assertFalse(camera._abort_acquisition)


if __name__ == '__main__':
    unittest.main()
