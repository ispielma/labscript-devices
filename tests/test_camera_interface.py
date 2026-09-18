"""The contract between a camera worker and the camera object it drives.

TriggerableCameraWorker duck-types its camera: it calls a set of methods and
reaches for two attributes, and nothing declares that set anywhere the worker
can check. A camera missing one of them fails with an AttributeError partway
through a shot, on hardware, which is the worst place to find out.

The first test here is that list, checked against every camera in the tree. The
rest pin the behaviour of the shared grab_multiple, because each vendor's
acquisition loop is being replaced by it and the replacement has to keep every
one of their failure behaviours exactly: IMAQdx retries on its timeout code and
skips a frame when the shot says not to fail; Pylon and FlyCapture2 retry
forever on their own error classes; Spinnaker and the dummy camera do not retry
at all.
"""
import sys
import unittest

import numpy as np

from labscript_devices.TriggerableCamera.blacs_workers import (
    TriggerableCameraInterface,
)
from labscript_devices.IMAQdxCamera.blacs_workers import IMAQdx_Camera
from labscript_devices.PylonCamera.blacs_workers import Pylon_Camera
from labscript_devices.SpinnakerCamera.blacs_workers import Spinnaker_Camera
from labscript_devices.FlyCapture2Camera.blacs_workers import FlyCapture2_Camera
from labscript_devices.AndorSolis.blacs_workers import AndorCamera
from labscript_devices.DummyCamera.blacs_workers import Dummy_Camera


# What TriggerableCameraWorker calls on self.camera, whatever camera it is.
REQUIRED_METHODS = [
    'set_attributes',
    'snap',
    'grab',
    'grab_multiple',
    'configure_acquisition',
    'stop_acquisition',
    'abort_acquisition',
    'close',
]

# What it assigns to. Both are read back by the acquisition loop.
REQUIRED_ATTRIBUTES = ['exception_on_failed_shot', '_abort_acquisition']

# The worker composes the attributes it saves from these, unless the camera's
# worker overrides get_attributes_as_dict. Pylon, FlyCapture2 and AndorSolis do.
COMPOSE_ATTRIBUTES_FROM = ['get_attribute_names', 'get_attribute']

EVERY_CAMERA = [
    IMAQdx_Camera,
    Pylon_Camera,
    Spinnaker_Camera,
    FlyCapture2_Camera,
    AndorCamera,
    Dummy_Camera,
]

CAMERAS_THE_WORKER_COMPOSES_ATTRIBUTES_FOR = [
    IMAQdx_Camera,
    Spinnaker_Camera,
    Dummy_Camera,
]


class ContractTests(unittest.TestCase):
    def test_every_camera_has_what_the_worker_calls(self):
        for camera in EVERY_CAMERA:
            for name in REQUIRED_METHODS:
                with self.subTest(camera=camera.__name__, member=name):
                    self.assertTrue(
                        callable(getattr(camera, name, None)),
                        f'{camera.__name__} has no {name}()',
                    )

    def test_every_camera_has_what_the_worker_assigns_to(self):
        # These are read back by the acquisition loop, so a camera that never
        # declares them works only because assignment creates them.
        for camera in EVERY_CAMERA:
            for name in REQUIRED_ATTRIBUTES:
                with self.subTest(camera=camera.__name__, member=name):
                    self.assertTrue(
                        hasattr(camera, name),
                        f'{camera.__name__} never declares {name}',
                    )

    def test_cameras_the_worker_asks_for_attributes_by_name_can_answer(self):
        for camera in CAMERAS_THE_WORKER_COMPOSES_ATTRIBUTES_FOR:
            for name in COMPOSE_ATTRIBUTES_FROM:
                with self.subTest(camera=camera.__name__, member=name):
                    self.assertTrue(callable(getattr(camera, name, None)))

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
        TriggerableCameraInterface.__init__(self)
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
