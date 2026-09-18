Triggerable Cameras
===================

Overview
~~~~~~~~

The generic camera device, from which all the others derive. It holds the
structure every camera shares -- exposures, triggering, camera attributes, and
where images are stored in the shot file -- and knows nothing about any
particular camera API. A camera for a given API is a subclass of this whose
BLACS worker names an interface class.

.. autosummary::
   labscript_devices.TriggerableCamera.labscript_devices
   labscript_devices.TriggerableCamera.blacs_tabs
   labscript_devices.TriggerableCamera.blacs_workers

Installation
~~~~~~~~~~~~


Usage
~~~~~


Detailed Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: labscript_devices.TriggerableCamera
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.TriggerableCamera.labscript_devices
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.TriggerableCamera.blacs_tabs
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.TriggerableCamera.blacs_workers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:
