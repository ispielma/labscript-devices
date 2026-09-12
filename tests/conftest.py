"""Settings that have to be in place before Qt and the suite are imported.

Running the tests is not supposed to put anything on the screen of whoever runs
them, and there are two separate ways they otherwise would.

`labscript_utils.excepthook` replaces `sys.excepthook` at import time, and every
unhandled exception then spawns a separate tkinter subprocess window, up to ten
at once. A single bad run leaves a pile of them to close by hand.

`test_imaqdx_camera_tab.py` reaches Qt, and a widget that is ever shown reaches
the screen with it. Rendering offscreen is what lets a test show a real widget
without one appearing — the fix for such a test is never to stop showing it,
because Qt does not lay out or paint a widget that was never shown, and the
assertions would then read nothing and pass vacuously.

Both are set here rather than expected on the command line: a test run should
not depend on remembering two environment variables. They affect test runs only
— a real run does not import this file, so the error dialog still appears where
it is meant to, which is the rule the workspace `AGENTS.md` guards.

The platform setting must be made before qtutils imports Qt, which is why it
lives in a conftest rather than a fixture: pytest imports conftest first.
`setdefault` leaves an explicit choice alone, so anyone who wants to watch a
test drive a real widget can export `QT_QPA_PLATFORM` themselves.

Careful with the escape hatch: `labscript_utils.excepthook` reads this as
`bool(os.environ.get(...))`, so *any* non-empty value suppresses the dialog --
`LABSCRIPT_NO_ERROR_DIALOG=0` suppresses it exactly as `=1` does. `setdefault`
will not overwrite an explicit setting, but the only settings that restore the
dialog are the empty string or unsetting the variable. Someone writing a test
of the dialog will reach for `=0`, get no dialog, and have no reason to suspect
the environment.

A test *of* the error dialog should set
`labscript_utils.excepthook.NO_ERROR_DIALOG` directly for its own duration
rather than relying on the environment.
"""
import os

os.environ.setdefault('LABSCRIPT_NO_ERROR_DIALOG', '1')
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
