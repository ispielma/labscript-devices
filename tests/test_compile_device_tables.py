"""Compiling shots whose devices write a table of strings.

A device's generate_code runs at the very end of a compile, so a dtype it names
that numpy no longer understands stops the shot file from being written at all,
and the half-finished file left behind cannot be compiled a second time either:
the groups written before the failure are already in it. Nothing warns earlier
than that.

Six tables here named the 'a<n>' spelling numpy 2.0 removed. Two can be reached
with no hardware attached, because a device's labscript-side class is only
Python and numpy: the NI_DAQmx acquisitions table and Camera's exposures table.
The other four are written by BLACS workers partway through a shot -- the
measured wait durations of NI_DAQmx, PrawnBlaster and CiceroOpalKellyXEM3001,
and AlazarTechBoard, whose module will not even import without libATSApi -- and
none of those can be reached without the hardware they drive.
"""
import os
import sys
import tempfile
import textwrap
import unittest
from types import ModuleType

import labscript_utils.h5_lock  # must precede h5py, as labscript itself does
import h5py

import labscript


# Any NI_DAQmx model with analog input will do; this is one of the common ones.
DAQMX_SHOT = textwrap.dedent(
    '''
    from labscript import start, stop, AnalogIn, AnalogOut
    from labscript_devices.DummyPseudoclock.labscript_devices import (
        DummyPseudoclock,
    )
    from labscript_devices.NI_DAQmx.models.NI_PCIe_6363 import NI_PCIe_6363

    DummyPseudoclock(name='pseudoclock')
    NI_PCIe_6363(
        name='daq',
        parent_device=pseudoclock.clockline,
        clock_terminal='/daq/PFI0',
        MAX_name='daq',
        acquisition_rate=1000.0,
    )
    # An even number of analog outputs: the DAQmx library needs an even total
    # number of samples, and generate_code refuses to compile without it.
    AnalogOut(name='analog_out', parent_device=daq, connection='ao0')
    AnalogOut(name='another_analog_out', parent_device=daq, connection='ao1')
    AnalogIn(name='analog_in', parent_device=daq, connection='ai0')

    start()
    analog_out.constant(0, 0.0)
    another_analog_out.constant(0, 0.0)
    analog_in.acquire('a measurement', 0.1, 0.5, units='V')
    stop(1.0)
    '''
)


CAMERA_SHOT = textwrap.dedent(
    '''
    from labscript import start, stop, Trigger
    from labscript_devices.DummyPseudoclock.labscript_devices import (
        DummyPseudoclock,
    )
    from labscript_devices.DummyIntermediateDevice import (
        DummyIntermediateDevice,
    )
    from labscript_devices.Camera import Camera

    DummyPseudoclock(name='pseudoclock')
    DummyIntermediateDevice(
        name='intermediate_device', parent_device=pseudoclock.clockline
    )
    Trigger(
        name='camera_trigger',
        parent_device=intermediate_device,
        connection='port0/line0',
    )
    Camera(
        name='camera',
        parent_device=camera_trigger,
        connection='trigger',
        exposure_time=0.1,
    )

    start()
    camera.expose('an exposure', 0.5, 'flat', exposure_time=0.1)
    stop(1.0)
    '''
)


class CompileTestCase(unittest.TestCase):
    """Compiles one shot the way runmanager's batch compiler does."""

    shot = None

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.script = os.path.join(self.directory, 'a_shot.py')
        with open(self.script, 'w') as f:
            f.write(self.shot)
        self.run_file = os.path.join(self.directory, 'a_shot.h5')
        # A run file as runmanager makes one: globals and nothing else.
        with h5py.File(self.run_file, 'w') as f:
            f.create_group('globals')

        self.saved_main = sys.modules.get('__main__')
        self.saved_cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.saved_cwd)
        if self.saved_main is not None:
            sys.modules['__main__'] = self.saved_main
        try:
            labscript.labscript_cleanup()
        except Exception:
            pass

    def compile_the_shot(self):
        module = ModuleType('__main__')
        module.__file__ = self.script
        sys.modules['__main__'] = module
        os.chdir(self.directory)
        try:
            labscript.labscript_init(self.run_file, labscript_file=self.script)
            with open(self.script) as f:
                code = compile(f.read(), self.script, 'exec', dont_inherit=True)
            exec(code, module.__dict__)
        finally:
            labscript.labscript_cleanup()


class NI_DAQmxTests(CompileTestCase):
    shot = DAQMX_SHOT

    def test_a_shot_asking_a_daqmx_board_for_an_acquisition_compiles(self):
        self.compile_the_shot()

        with h5py.File(self.run_file, 'r') as f:
            acquisitions = f['devices/daq/AI'][:]

        self.assertEqual(len(acquisitions), 1)
        acquisition = acquisitions[0]
        self.assertEqual(acquisition['connection'].decode(), 'ai0')
        self.assertEqual(acquisition['label'].decode(), 'a measurement')
        self.assertEqual(acquisition['units'].decode(), 'V')
        self.assertEqual(acquisition['start'], 0.1)
        self.assertEqual(acquisition['stop'], 0.5)

    def test_the_acquisitions_table_is_written_as_earlier_versions_wrote_it(self):
        # 'a256' was only ever an alias for 'S256', so renaming it changed
        # nothing on disk. Pinning bytes here is what says the shot files this
        # writes are still the ones BLACS and lyse already know how to read.
        self.compile_the_shot()

        with h5py.File(self.run_file, 'r') as f:
            dtype = f['devices/daq/AI'].dtype

        for column in ('connection', 'label', 'wait label', 'units'):
            self.assertEqual(dtype[column].kind, 'S', column)


class CameraTests(CompileTestCase):
    shot = CAMERA_SHOT

    def test_a_shot_exposing_a_camera_compiles(self):
        self.compile_the_shot()

        with h5py.File(self.run_file, 'r') as f:
            exposures = f['devices/camera/EXPOSURES'][:]

        self.assertEqual(len(exposures), 1)
        exposure = exposures[0]
        self.assertEqual(exposure['name'].decode(), 'an exposure')
        self.assertEqual(exposure['frametype'].decode(), 'flat')
        self.assertEqual(exposure['time'], 0.5)

    def test_the_exposures_table_is_written_as_earlier_versions_wrote_it(self):
        self.compile_the_shot()

        with h5py.File(self.run_file, 'r') as f:
            dtype = f['devices/camera/EXPOSURES'].dtype

        for column in ('name', 'frametype'):
            self.assertEqual(dtype[column].kind, 'S', column)


if __name__ == '__main__':
    unittest.main()
