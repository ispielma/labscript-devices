#####################################################################
#                                                                   #
# /labscript_devices/DummyCamera/sensor.py                          #
#                                                                   #
# Copyright 2026, Ian Spielman and contributors                     #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

"""Where a dummy camera's pixels are, and what it shows when nothing says otherwise.

Both halves of the device need these. The labscript half evaluates image
functions on the grid while the shot compiles; the BLACS worker needs the same
grid for a manual-mode frame, where there is no shot and so no image function.
Neither half can import the other's module -- one reaches labscript and through
it pylab, the other reaches blacs -- so they share this one, which needs neither.
"""

import numpy as np

from labscript_utils import dedent


def sensor_grid(camera_attributes, pixel_size=(1.0, 1.0), magnification=1.0):
    """The meshgrid a dummy camera's image functions are evaluated on.

    Object-plane coordinates in micrometres: the sensor's pixels scaled by
    `pixel_size` and `magnification` and centred on the sensor, so that a
    function can model a cloud in physical units without restating the imaging
    geometry. At the default 1 um pixels and 1x magnification the grid is
    numerically the pixel indices.

    `Width` and `Height` come from the camera's attributes, where a real
    camera's resolution comes from. A dummy camera has no sensor to fall back
    on, so they are required rather than defaulted: an image quietly the wrong
    size is worse than one that does not compile.
    """
    missing = [key for key in ('Width', 'Height') if key not in camera_attributes]
    if missing:
        msg = """A dummy camera's images are whatever size its camera_attributes
            say they are, and this camera's do not say: %s missing. Give it
            camera_attributes={'Width': ..., 'Height': ...}, the way a real
            camera is told its resolution."""
        raise ValueError(dedent(msg) % ' and '.join(missing))
    width = int(camera_attributes['Width'])
    height = int(camera_attributes['Height'])
    pixel_x, pixel_y = pixel_size
    x = (np.arange(width) - (width - 1) / 2) * pixel_x / magnification
    y = (np.arange(height) - (height - 1) / 2) * pixel_y / magnification
    return np.meshgrid(x, y)


def default_image(X, Y):
    """The image a dummy camera produces when no function was given for one.

    A Gaussian dip in a flat background, so that a connection table with a dummy
    camera in it compiles and runs before anyone has written a model, and so
    that the Snap button in the BLACS tab shows something. It takes the
    arguments every image function takes and returns counts, like any other:
    nothing about it is special to the camera.
    """
    background = 500.0
    width = min(np.ptp(X), np.ptp(Y)) / 10 or 1.0
    return background * (1 - 0.5 * np.exp(-(X ** 2 + Y ** 2) / (2 * width ** 2)))
