"""The IMAQdx camera tab's attribute-copy button.

on_copy_clicked reached for QApplication under the module it lived in before
Qt5, so the Copy button in the camera's attributes dialog raised AttributeError
rather than copying anything. Only the clipboard call needs a Qt application;
the tab itself is never constructed here, so no camera has to be attached.
"""
import unittest

import labscript_utils.h5_lock  # must precede h5py, as the tab itself does
import h5py

from qtutils.qt import QtWidgets

from labscript_devices.IMAQdxCamera.blacs_tabs import IMAQdxCameraTab


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
        self.tab = IMAQdxCameraTab.__new__(IMAQdxCameraTab)
        self.tab.attributes_dialog = AnAttributesDialog(ATTRIBUTES)
        self.qapplication.clipboard().clear()

    def test_copy_puts_the_attributes_on_the_clipboard(self):
        self.tab.on_copy_clicked(None)

        self.assertEqual(self.qapplication.clipboard().text(), ATTRIBUTES)


if __name__ == '__main__':
    unittest.main()
