"""
Pytest configuration and shared fixtures for rovers-basestation tests.

This conftest.py ensures the project root is in sys.path so that
imports like `xbee.app`, `auto_boot.auto_boot`, and `utils.GPS` work
correctly during test collection and execution.
"""

import os
import sys
import types
from pathlib import Path

# Set XBEE_NO_GUI before any tkinter imports to prevent GUI windows during tests
os.environ["XBEE_NO_GUI"] = "1"

# NOTE: This conftest enforces a headless environment by replacing Tkinter
# with lightweight stub modules. This ensures deterministic behavior in CI
# and avoids platform-dependent GUI windows during tests.
#
# If a specific test suite requires the real tkinter library, you must:
#  - run the suite with a modified conftest that does not replace sys.modules,
#  - or monkeypatch sys.modules and reload the module under test to obtain a
#    real tkinter import during that particular test (not recommended in CI).

# Module name constants
_TKINTER_MODULE = "tkinter"
_TKINTER_TTK_MODULE = "tkinter.ttk"
_TKINTER_FONT_MODULE = "tkinter.font"

# Don't import the real tkinter here - instead replace the module in
# sys.modules with a lightweight stub below. Importing tkinter early can
# trigger GUI initialisation and we explicitly want to avoid that during tests.


# Define a tiny stub with required members used by the application
class _TkStub:
    def __init__(self, *args, **kwargs):
        # Intentionally empty - used to replace tkinter.Tk in tests
        pass

    def title(self, *args, **kwargs):
        return None

    def geometry(self, *args, **kwargs):
        return None

    def columnconfigure(self, *args, **kwargs):
        return None

    def rowconfigure(self, *args, **kwargs):
        return None

    def after_idle(self, *args, **kwargs):
        return None

    def mainloop(self, *args, **kwargs):
        return None

    def quit(self, *args, **kwargs):
        return None


class _StyleStub:
    def configure(self, *args, **kwargs):
        return None


def _widget_stub(*args, **kwargs):
    class _Widget:
        def grid(self, *a, **k):
            return None

        def columnconfigure(self, *a, **k):
            return None

        def rowconfigure(self, *a, **k):
            return None

        def configure(self, *a, **k):
            return None

        def config(self, *a, **k):
            return None

        def delete(self, *a, **k):
            return None

        def insert(self, *a, **k):
            return None

        def yview(self, *a, **k):
            return None

        def set(self, *a, **k):
            return None

    return _Widget()


ttk_stub = types.ModuleType(_TKINTER_TTK_MODULE)
ttk_stub.Frame = _widget_stub  # type: ignore[attr-defined]
ttk_stub.Label = _widget_stub  # type: ignore[attr-defined]
ttk_stub.LabelFrame = _widget_stub  # type: ignore[attr-defined]
ttk_stub.Scrollbar = _widget_stub  # type: ignore[attr-defined]
ttk_stub.Style = lambda: _StyleStub()  # type: ignore[attr-defined]

font_stub = types.ModuleType(_TKINTER_FONT_MODULE)
tk_stub = types.ModuleType(_TKINTER_MODULE)
tk_stub.Tk = _TkStub  # type: ignore[attr-defined]
tk_stub.Text = lambda *a, **k: _widget_stub()  # type: ignore[attr-defined]
tk_stub.END = "end"  # type: ignore[attr-defined]
tk_stub.WORD = "word"  # type: ignore[attr-defined]
tk_stub.CENTER = "center"  # type: ignore[attr-defined]
tk_stub.W = "w"  # type: ignore[attr-defined]
tk_stub.VERTICAL = "vertical"  # type: ignore[attr-defined]
tk_stub.font = font_stub  # type: ignore[attr-defined]
tk_stub.ttk = ttk_stub  # type: ignore[attr-defined]

# If real tkinter is loaded, we still want safe behavior. We explicitly
# assign our stub modules into sys.modules below which guarantees imports
# pick up our stubs; additionally, when a real tkinter module is present
# (unlikely in CI tests), we also try to replace particular members with
# stubs to avoid creating any GUI widgets. This makes test behavior
# deterministic regardless of the environment.
# Always use stub modules to ensure no real GUI initialization and avoid
# accidental import side-effects. We deliberately assign rather than
# using setdefault to ensure the stub is used even if the real module
# was previously imported.
sys.modules[_TKINTER_MODULE] = tk_stub
sys.modules[_TKINTER_TTK_MODULE] = ttk_stub
sys.modules[_TKINTER_FONT_MODULE] = font_stub

# If a real tkinter.ttk exists, ensure we override Style to a safe stub
if _TKINTER_TTK_MODULE in sys.modules:
    try:
        real_ttk = sys.modules[_TKINTER_TTK_MODULE]
        real_ttk.Style = lambda: _StyleStub()  # type: ignore[attr-defined]
    except Exception:
        pass
# Add the repository root to sys.path for imports
REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Re-export fixtures from fixtures.py so they're available to all tests
# Import the module and use pytest_plugins pattern for proper fixture discovery
pytest_plugins = ["tests.fixtures"]
