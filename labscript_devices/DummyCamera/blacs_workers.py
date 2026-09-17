#####################################################################
#                                                                   #
# /labscript_devices/DummyCamera/blacs_workers.py                   #
#                                                                   #
# Copyright 2026, Ian Spielman and contributors                     #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

from labscript_utils import dedent
import labscript_utils.h5_lock
import h5py

from labscript_utils.shared_drive import path_to_local

from labscript_devices.TriggerableCamera.blacs_workers import (
    MockCamera,
    TriggerableCameraWorker,
)


class Dummy_Camera(MockCamera):
    """A camera whose frames were computed when the shot was compiled.

    It acquires the way any camera acquires, one frame per grab in the order the
    triggers arrive, but the frames come from the shot file rather than from a
    sensor. In manual mode there is no shot, so it falls back to the image
    MockCamera returns -- the one place a frame is looked at with nothing around
    it to say where it came from, and so the one place the watermark on that
    image is the thing that says so.
    """

    # What marks these images as not real data once they are in the shot file.
    # It is a camera attribute rather than pixels drawn onto the image because a
    # watermark does not cancel in OD = -log((atoms - dark) / (probe - dark)),
    # and would ruin the absorption analysis this camera exists to feed. The
    # attribute path every camera already uses saves it beside the images.
    identifying_attributes = {'NOT_REAL_DATA': True}

    def __init__(self, serial_number=None):
        MockCamera.__init__(self)
        self.attributes.update(self.identifying_attributes)
        self.images = None
        self.index = 0

    def load_images(self, images):
        """Take the frames this shot compiled, to be returned one per grab."""
        self.images = images
        self.index = 0

    def grab(self):
        if self.images is None:
            return self.snap()
        if self.index >= len(self.images):
            msg = """This shot compiled %d images and the camera has been asked
                for one more. A dummy camera produces one image per exposure, so
                more triggers have arrived than the shot has exposures."""
            raise ValueError(dedent(msg) % len(self.images))
        image = self.images[self.index]
        self.index += 1
        return image


class DummyCameraWorker(TriggerableCameraWorker):
    """Thin sub-class of :obj:`TriggerableCameraWorker`.

    It names :obj:`Dummy_Camera` as its interface class, and hands that camera
    the images the shot compiled before the acquisition starts. Everything
    after that -- the acquisition thread, saving the images to the shot file
    and displaying them in the tab -- is inherited unchanged, which is what
    makes these images indistinguishable from a real camera's downstream."""

    interface_class = Dummy_Camera

    def transition_to_buffered(self, device_name, h5_filepath, initial_values, fresh):
        local_filepath = h5_filepath
        if getattr(self, 'is_remote', False):
            local_filepath = path_to_local(h5_filepath)
        with h5py.File(local_filepath, 'r') as f:
            group = f['devices'][self.device_name]
            images = group['IMAGES'][:] if 'IMAGES' in group else None
        self.camera.load_images(images)
        return TriggerableCameraWorker.transition_to_buffered(
            self, device_name, h5_filepath, initial_values, fresh
        )
