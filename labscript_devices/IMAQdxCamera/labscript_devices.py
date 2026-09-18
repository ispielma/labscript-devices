#####################################################################
#                                                                   #
# /labscript_devices/IMAQdxCamera/labscript_devices.py              #
#                                                                   #
# Copyright 2019, Monash University and contributors                #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

from labscript_devices.TriggerableCamera.labscript_devices import TriggerableCamera


class IMAQdxCamera(TriggerableCamera):
    """Sub-class of :obj:`TriggerableCamera` for cameras driven through IMAQdx.

    IMAQdx composes a camera's serial number from two 32-bit halves and
    spells it in hexadecimal, so this class accepts a hexadecimal string and
    presents the camera to BLACS under the same spelling. Every other camera
    uses its serial number as its own API spells it.
    """

    description = 'IMAQdx Camera'

    def __init__(self, name, parent_device, connection, serial_number, **kwargs):
        """Takes what :obj:`TriggerableCamera` takes, with `serial_number`
        given as an integer or as a string holding a hexadecimal literal."""
        if isinstance(serial_number, (str, bytes)):
            serial_number = int(serial_number, 16)
        TriggerableCamera.__init__(
            self, name, parent_device, connection, serial_number, **kwargs
        )
        # Set after the parent has run: it reads self.serial_number, and
        # BLACS_connection is not read until the connection table is generated.
        self.BLACS_connection = hex(self.serial_number)[2:].upper()
