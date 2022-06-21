# -*- coding: utf-8 -*-
"""
Created on Thu Jun  2 13:30:09 2022

@author: rubidium
"""
#This registers the arduino device as a class in the labscript devices module, for use in connectivity with blacs
#This device should be imported in the connection table from labscript_devices

import labscript_devices

#This registers the device as a class. 
#The "BLACS_tab" input gives the path to find the particular device tab for the arduino device being connected
labscript_devices.register_classes(
    'Arduino_Device',
    BLACS_tab='labscript_devices.Arduino_Device.blacs_tabs.Arduino_Device_Tab',
    runviewer_parser=None
)