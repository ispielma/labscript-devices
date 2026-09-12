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

Both must be set before the module that reads each is imported, which is why
this is a conftest rather than a fixture: pytest imports conftest first. The
platform setting has to beat qtutils importing Qt. The dialog setting has to
beat `labscript_utils.excepthook`, which captures the environment once at module
scope -- setting the variable after that import does nothing, though a test can
still assign `NO_ERROR_DIALOG` directly at any point.
`setdefault` leaves an explicit choice alone, so anyone who wants to watch a
test drive a real widget can export `QT_QPA_PLATFORM` themselves.

`setdefault` leaves an explicit setting alone, and an explicit setting means what
it looks like: `LABSCRIPT_NO_ERROR_DIALOG=0` keeps the dialog on, as do `false`,
`no`, `off` and the empty string. Anything else suppresses it.

A test *of* the error dialog should set
`labscript_utils.excepthook.NO_ERROR_DIALOG` directly for its own duration
rather than relying on the environment.
"""
import os

os.environ.setdefault('LABSCRIPT_NO_ERROR_DIALOG', '1')
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
