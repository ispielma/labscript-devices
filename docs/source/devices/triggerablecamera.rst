Triggerable Cameras
===================

Overview
~~~~~~~~

The generic camera, from which all the others derive. It holds the structure
every camera shares -- exposures, triggering, camera attributes, and where
images are stored in the shot file -- and knows nothing about any particular
camera API. A camera for a given API is a subclass of this whose BLACS worker
names an interface class.

That interface class is the object the worker talks to in place of hardware,
and :obj:`~labscript_devices.TriggerableCamera.blacs_workers.TriggerableCameraInterface`
is what it implements: the contract the worker calls, an acquisition loop, and
an abort. Inheriting it is an offer rather than a requirement -- the worker
duck-types its camera -- but a camera that does is told which member it has
not written, rather than failing partway through a shot.

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
