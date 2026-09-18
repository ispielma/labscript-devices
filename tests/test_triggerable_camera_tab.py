"""The camera tab's attribute-copy button.

on_copy_clicked reaches for QApplication under QtWidgets, where it has lived
since Qt5; asking QtGui for it raises AttributeError and the Copy button in
the attributes dialog copies nothing. Only the clipboard call needs a Qt
application; the tab itself is never constructed here, so no camera has to be
attached.

The button belongs to TriggerableCameraTab, which every camera inherits, so
that is what this tests -- reaching it through a vendor subclass would move
the test off its subject the moment that subclass grew a copy button of its
own.
"""
import unittest

import labscript_utils.h5_lock  # must precede h5py, as the tab itself does
import h5py

from qtutils.qt import QtWidgets

from labscript_devices.TriggerableCamera.blacs_tabs import TriggerableCameraTab


ATTRIBUTES = 'AcquisitionAttributes::Bitspp: 8\nCameraAttributes::Gain: 1.0\n'


def a_qapplication():
    """One QApplication for the whole process, as Qt requires."""
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication(['test'])


class AnAttributesDialog:
    """The dialog the tab loads from its .ui file, reduced to what is read."""

    def __init__(self, text):
        self.plainTextEdit = QtWidgets.QPlainTextEdit()
        self.plainTextEdit.setPlainText(text)


class CopyAttributesTests(unittest.TestCase):
    def setUp(self):
        self.qapplication = a_qapplication()
        # __init__ builds a whole BLACS tab against a camera; on_copy_clicked
        # reads only the dialog, so give it one and nothing else:
        self.tab = TriggerableCameraTab.__new__(TriggerableCameraTab)
        self.tab.attributes_dialog = AnAttributesDialog(ATTRIBUTES)
        self.qapplication.clipboard().clear()

    def test_copy_puts_the_attributes_on_the_clipboard(self):
        self.tab.on_copy_clicked(None)

        self.assertEqual(self.qapplication.clipboard().text(), ATTRIBUTES)


if __name__ == '__main__':
    unittest.main()
