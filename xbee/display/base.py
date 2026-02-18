"""
Display system base classes and factory.

This module contains:
- BaseDisplay: Abstract interface that BaseStation calls
- HeadlessDisplay: Logging-only implementation for daemon/headless environments
- create_display(): Factory that picks the right implementation
- Tkinter stubs for headless/test environments
- UI layout constants

To add a new display method to BaseStation, add it to BaseDisplay,
then implement it in HeadlessDisplay (log-only) and TkinterDisplay (GUI).
"""

import abc
import logging
import os
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _env_flag_enabled(name: str) -> bool:
    """Return True when an env var is set to a truthy value."""
    raw = (os.getenv(name) or "").strip().lower()
    return raw in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 480
SIDEBAR_WIDTH = 140
SIDEBAR_PADDING = (4, 4)
INDICATOR_SIZE = 30
BANNER_HEIGHT = 56

PANEL_STYLE = "Panel.TLabelframe"
PANEL_LABEL_STYLE = f"{PANEL_STYLE}.Label"
SIDEBAR_LABEL_STYLE = "Sidebar.TLabel"
SIDEBAR_SMALL_STYLE = "SidebarSmall.TLabel"

DEFAULT_MODULE_VIEW_KEY = "life"
MODULE_VIEW_LABELS = {
    "life": "Life Detection",
    "auto": "Autonomous",
    "arm": "Arm",
}
MODULE_VIEW_ORDER = ("life", "auto", "arm")


# ---------------------------------------------------------------------------
# Tkinter stubs (used when tkinter is unavailable or in headless mode)
# ---------------------------------------------------------------------------


class _GenericWidgetStub:
    """No-op widget used in headless / test environments."""

    def __init__(self, *args, **kwargs):
        pass  # Stub: intentionally empty

    def grid(self, *args, **kwargs):
        return None

    def columnconfigure(self, *args, **kwargs):
        return None

    def rowconfigure(self, *args, **kwargs):
        return None

    def configure(self, *args, **kwargs):
        return None

    def config(self, *args, **kwargs):
        return None

    def delete(self, *args, **kwargs):
        return None

    def insert(self, *args, **kwargs):
        return None

    def yview(self, *args, **kwargs):
        return None

    def set(self, *args, **kwargs):
        return None


# Try importing real tkinter; fall back to stubs if unavailable.
tk: Any
ttk: Any
font: Any

try:
    import tkinter as tk
    from tkinter import font, ttk

    TK_AVAILABLE = True
except ImportError:
    import types

    class _TkStub:
        def __init__(self, *args, **kwargs):
            pass  # Stub: intentionally empty

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

    def _text_stub(*args, **kwargs):
        return _GenericWidgetStub()

    def _frame_stub(*args, **kwargs):
        return _GenericWidgetStub()

    def _label_stub(*args, **kwargs):
        return _GenericWidgetStub()

    def _scrollbar_stub(*args, **kwargs):
        return _GenericWidgetStub()

    def _canvas_stub(*args, **kwargs):
        return _GenericWidgetStub()

    def _combobox_stub(*args, **kwargs):
        return _GenericWidgetStub()

    def _separator_stub(*args, **kwargs):
        return _GenericWidgetStub()

    class _StringVarStub:
        def __init__(self, value=None):
            self._value = value

        def get(self):
            return self._value

        def set(self, value):
            self._value = value

    tk = types.SimpleNamespace(
        Tk=_TkStub,
        Text=_text_stub,
        Frame=_frame_stub,
        Canvas=_canvas_stub,
        StringVar=_StringVarStub,
        END="end",
        WORD="word",
        CENTER="center",
        W="w",
        VERTICAL="vertical",
    )
    ttk = types.SimpleNamespace(
        Frame=_frame_stub,
        Label=_label_stub,
        LabelFrame=_label_stub,
        Scrollbar=_scrollbar_stub,
        Combobox=_combobox_stub,
        Separator=_separator_stub,
        Style=lambda: _StyleStub(),
    )
    font = None
    TK_AVAILABLE = False


# ---------------------------------------------------------------------------
# Abstract display interface
# ---------------------------------------------------------------------------


class BaseDisplay(abc.ABC):
    """Abstract display interface used by BaseStation.

    Every method here is called from the control loop or main().
    Implement all of them to create a new display backend.
    """

    @abc.abstractmethod
    def update_controller_display(
        self, controller_id: int, controller_data: Dict[str, Any]
    ): ...

    @abc.abstractmethod
    def update_controller_values(self, values: Dict[str, Any]): ...

    @abc.abstractmethod
    def update_modes(self, creep: bool = False, reverse: bool = False): ...

    @abc.abstractmethod
    def update_telemetry(self, telemetry: Dict[str, Any]): ...

    @abc.abstractmethod
    def update_communication_status(self, connected: bool, message_count: int = 0): ...

    @abc.abstractmethod
    def set_simulation_mode(self, is_simulation: bool): ...

    @abc.abstractmethod
    def run(self): ...

    @abc.abstractmethod
    def quit(self): ...


# ---------------------------------------------------------------------------
# Headless display (for daemons / systemd / tests)
# ---------------------------------------------------------------------------


class HeadlessDisplay(BaseDisplay):
    """Logs updates instead of rendering a GUI. Same API as TkinterDisplay."""

    def __init__(self):
        self.headless = True
        self.running = True
        self.controllers = {}
        self.controller_values = {}
        self._controller_lock = threading.Lock()
        self._mode_lock = threading.Lock()
        self.creep_mode = True
        self.reverse_mode = False
        self.simulation_mode = False
        self.telemetry_data = {}
        self._telemetry_lock = threading.Lock()

    def set_simulation_mode(self, is_simulation: bool):
        self.simulation_mode = is_simulation
        if is_simulation:
            logger.info("HeadlessDisplay: SIMULATION MODE ACTIVE")

    def update_controller_display(
        self, controller_id: int, controller_data: Dict[str, Any]
    ):
        with self._controller_lock:
            self.controllers[controller_id] = controller_data
        logger.debug(
            "HeadlessDisplay updated controller %d: %s", controller_id, controller_data
        )

    def update_controller_values(self, values: Dict[str, Any]):
        with self._controller_lock:
            if values and isinstance(next(iter(values.values()), None), dict):
                self.controller_values = {k: dict(v) for k, v in values.items()}
            else:
                self.controller_values = dict(values) if values else {}
        logger.debug("HeadlessDisplay controller values: %s", values)

    def update_modes(self, creep: bool = False, reverse: bool = False):
        with self._mode_lock:
            self.creep_mode = creep
            self.reverse_mode = reverse
        logger.debug("HeadlessDisplay modes: creep=%s, reverse=%s", creep, reverse)

    def update_telemetry(self, telemetry: Dict[str, Any]):
        try:
            with self._telemetry_lock:
                self.telemetry_data.update(telemetry)
        except Exception:
            logger.exception("Failed to update telemetry data")
            raise
        logger.debug("HeadlessDisplay telemetry: %s", telemetry)

    def update_communication_status(self, connected: bool, message_count: int = 0):
        status = "Connected" if connected else "Disconnected"
        logger.info(f"HeadlessDisplay comm: {status} (messages: {message_count})")

    def run(self):
        return

    def quit(self):
        self.running = False


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_display(prefer_gui: Optional[bool] = None) -> BaseDisplay:
    """Return the appropriate display implementation.

    Args:
        prefer_gui: True = force GUI, False = force headless, None = auto-detect.
    """
    env_no_gui = _env_flag_enabled("XBEE_NO_GUI")

    # Default to headless under pytest
    try:
        import sys

        override_gui = _env_flag_enabled("XBEE_TEST_OVERRIDE_GUI")
        if "pytest" in sys.modules and not override_gui:
            env_no_gui = True
    except Exception:
        pass

    if prefer_gui is False or (prefer_gui is None and env_no_gui) or not TK_AVAILABLE:
        logger.info("Using HeadlessDisplay (GUI disabled or unavailable)")
        return HeadlessDisplay()

    try:
        # Lazy import to avoid circular dependency
        from xbee.display.gui import TkinterDisplay

        return TkinterDisplay()
    except (ImportError, RuntimeError, ValueError) as e:
        logger.warning("Failed to init TkinterDisplay (%s). Using headless.", e)
        return HeadlessDisplay()
    except Exception as e:
        logger.warning("Failed to init TkinterDisplay (%s). Using headless.", e)
        return HeadlessDisplay()


__all__ = [
    "BaseDisplay",
    "HeadlessDisplay",
    "create_display",
    "TK_AVAILABLE",
    "WINDOW_WIDTH",
    "WINDOW_HEIGHT",
    "SIDEBAR_WIDTH",
    "SIDEBAR_PADDING",
    "INDICATOR_SIZE",
    "BANNER_HEIGHT",
    "PANEL_STYLE",
    "PANEL_LABEL_STYLE",
    "SIDEBAR_LABEL_STYLE",
    "SIDEBAR_SMALL_STYLE",
    "DEFAULT_MODULE_VIEW_KEY",
    "MODULE_VIEW_LABELS",
    "MODULE_VIEW_ORDER",
    "_GenericWidgetStub",
    "tk",
    "ttk",
    "font",
]
