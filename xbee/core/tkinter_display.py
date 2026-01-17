"""
Tkinter-based display system for rover basestation.
Replaces pygame display with cross-platform GUI.
Provides a headless fallback for systemd/daemon environments.
"""

import abc
import logging
import os
import threading
import time
from typing import Any, Dict, Optional

from .command_codes import CONSTANTS

logger = logging.getLogger(__name__)

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


class _GenericWidgetStub:
    def __init__(self, *args, **kwargs):
        # Intentionally empty: generic no-op widget constructor used by tests and
        # in headless environments to satisfy API compatibility checks.
        pass

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
            # Headless Tk stub: replace tkinter.Tk in headless environments to avoid errors in tests
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

    _WidgetStub = _GenericWidgetStub


class BaseDisplay(abc.ABC):
    """
    Abstract minimal display interface used by the basestation.
    Implementations should provide the following methods used by base_station:
    - update_controller_display
    - update_controller_values
    - update_modes
    - update_telemetry
    - update_communication_status
    - set_simulation_mode
    - run
    - quit
    """

    @abc.abstractmethod
    def update_controller_display(
        self, controller_id: int, controller_data: Dict[str, Any]
    ):
        ...

    @abc.abstractmethod
    def update_controller_values(self, values: Dict[str, Any]):
        ...

    @abc.abstractmethod
    def update_modes(self, creep: bool = False, reverse: bool = False):
        ...

    @abc.abstractmethod
    def update_telemetry(self, telemetry: Dict[str, Any]):
        ...

    @abc.abstractmethod
    def update_communication_status(self, connected: bool, message_count: int = 0):
        ...

    @abc.abstractmethod
    def set_simulation_mode(self, is_simulation: bool):
        ...

    @abc.abstractmethod
    def run(self):
        ...

    @abc.abstractmethod
    def quit(self):
        ...


class HeadlessDisplay(BaseDisplay):
    """
    A simple headless display used for services or when no X display is available.
    It logs updates instead of rendering UI and provides the same API as TkinterDisplay.
    """

    def __init__(self):
        self.headless = True
        self.running = True
        self.controllers = {}
        self.controller_values = {}
        self._controller_lock = threading.Lock()
        # Lock protecting mode flags to avoid race conditions when reading/updating
        self._mode_lock = threading.Lock()
        # Default: enable creep mode on startup
        self.creep_mode = True
        self.reverse_mode = False
        self.simulation_mode = False
        self.telemetry_data = {}
        self._telemetry_lock = threading.Lock()

    def set_simulation_mode(self, is_simulation: bool):
        """
        Set simulation mode status (for API compatibility with TkinterDisplay).

        Args:
            is_simulation: True if running in simulation mode
        """
        self.simulation_mode = is_simulation
        if is_simulation:
            logger.info(
                "HeadlessDisplay: SIMULATION MODE ACTIVE - No rover communication"
            )

    def update_controller_display(
        self, controller_id: int, controller_data: Dict[str, Any]
    ):
        with self._controller_lock:
            self.controllers[controller_id] = controller_data
        logger.debug(
            f"HeadlessDisplay updated controller {controller_id}: {controller_data}"
        )

    def update_controller_values(self, values: Dict[str, Any]):
        with self._controller_lock:
            # Handle both old (flat) and new (nested per-controller) format
            # New format: {"xbox": {...}, "n64": {...}}
            # Old format: {"ly": 0.5, "lx": 0.0, ...} (flat dict)
            if values and isinstance(next(iter(values.values()), None), dict):
                # New nested format - deep copy each controller's values
                self.controller_values = {k: dict(v) for k, v in values.items()}
            else:
                # Old flat format - store as-is for backward compatibility
                self.controller_values = dict(values) if values else {}
        logger.debug(f"HeadlessDisplay controller values: {values}")

    def update_modes(self, creep: bool = False, reverse: bool = False):
        # Protect mode updates to avoid races with readers in the display thread
        with self._mode_lock:
            self.creep_mode = creep
            self.reverse_mode = reverse
        logger.debug(f"HeadlessDisplay mode update - creep={creep}, reverse={reverse}")

    def update_telemetry(self, telemetry: Dict[str, Any]):
        # Use _telemetry_lock to protect telemetry data from concurrent updates while UI reads
        try:
            with self._telemetry_lock:
                self.telemetry_data.update(telemetry)
        except Exception:
            # Log and re-raise to surface issues cleanly; do not swallow exceptions silently
            logger.exception("Failed to update telemetry data")
            raise
        logger.debug("HeadlessDisplay telemetry update: %s", telemetry)

    def update_communication_status(self, connected: bool, message_count: int = 0):
        logger.info(
            f"HeadlessDisplay comm status: {'Connected' if connected else 'Disconnected'} - messages: {message_count}"
        )

    def run(self):
        # Headless display is a no-op: run() returns immediately to preserve API for tests
        return

    def quit(self):
        self.running = False


class TkinterDisplay(BaseDisplay):
    """
    Tkinter-based display for rover basestation with simulation mode warning.
    """

    def __init__(self):
        """
        Initialize the tkinter display system.
        Note: Use the `create_display()` factory to obtain a HeadlessDisplay in environments where
        a GUI is unavailable or disabled. If Tkinter is unavailable or UI initialization fails, this
        constructor will raise an exception; callers should use `create_display()` for a safe fallback.
        """
        # Raise if GUI disabled or Tkinter unavailable; callers should use create_display() factory instead.
        env_no_gui = os.environ.get("XBEE_NO_GUI", "").lower() in ("1", "true", "yes")
        if env_no_gui or not TK_AVAILABLE:
            raise RuntimeError(
                "Tkinter unavailable (XBEE_NO_GUI set or tkinter not installed). "
                "Use create_display() to get a HeadlessDisplay."
            )

        try:
            self.root = tk.Tk()
            self.root.title("SPEX Rover Basestation Control")
            self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        except Exception as e:
            # Let Tkinter initialization failures propagate so callers or factory can explicitly handle them.
            logger.error(f"Tkinter initialization failed ({e}).")
            raise

        # Controller data (protected by a lock for thread-safety)
        self.controllers = {}
        self.controller_values = {}
        self._controller_lock = threading.Lock()
        # Lock protecting mode flags to avoid race conditions between update and read
        self._mode_lock = threading.Lock()

        # Mode flags - default to creep mode enabled on startup
        self.creep_mode = True
        self.reverse_mode = False
        # Start with CONSTANTS value but allow runtime override via set_simulation_mode
        self.simulation_mode = CONSTANTS.SIMULATION_MODE
        # Track if simulation mode banner should be shown (set at runtime)
        self._show_simulation_banner = False

        # Telemetry data (protected by a lock for thread-safety)
        self.telemetry_data = {}
        self._telemetry_lock = threading.Lock()

        # Type annotations for widget attributes (can be either real widgets or stubs for testing)
        # Using Any to avoid complex Union types with tkinter widgets
        self.comm_status_label: Any = None
        self.update_counter_label: Any = None
        self.controller_text: Any = None
        self.module_text: Any = None
        self.module_frame: Any = None

        # Sidebar indicators
        self.creep_indicator: Any = None
        self.reverse_indicator: Any = None
        self.auto_status_indicator: Any = None
        self.auto_status_text_label: Any = None
        self.auto_toggle_indicator: Any = None
        self.rover_status_indicator: Any = None
        self.rover_status_text_label: Any = None
        self.life_toggle_indicator: Any = None

        # Simulation banner widgets
        self._warning_canvas: Any = None
        self._sim_view_var: Any = None
        self._sim_view_dropdown: Any = None

        # Module view state
        self._module_view = "life"
        self._module_view_override: Optional[str] = None
        self._auto_status_state: str = "teleop"

        self._setup_ui()
        self._setup_styles()

        # Start UI update thread
        self.running = True
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()

    def _setup_styles(self):
        """
        Setup custom styles for the UI.
        """
        self.style = ttk.Style()

        # Simulation banner container style
        self.style.configure("Banner.TFrame", relief="raised", borderwidth=2)

        # Panel styles
        self.style.configure(PANEL_STYLE, padding=8)
        self.style.configure(PANEL_LABEL_STYLE, font=("Arial", 12, "bold"))

        # Sidebar labels
        self.style.configure(SIDEBAR_LABEL_STYLE, font=("Arial", 11, "bold"))
        self.style.configure(SIDEBAR_SMALL_STYLE, font=("Arial", 9))

    def _setup_ui(self):
        """
        Setup the main UI layout.
        """
        # Skip UI setup if root is a test mock to avoid constructing real widgets during tests
        try:
            import unittest.mock as _unittest_mock

            mock_cls = getattr(_unittest_mock, "Mock", None)
        except Exception:
            mock_cls = None

        if mock_cls is not None and isinstance(self.root, mock_cls):
            logger.info("Detected mock tkinter root; skipping UI setup for tests")
            # Provide minimal stub widgets so display-using code can call methods safely in tests
            stub_widget = _GenericWidgetStub()
            self.comm_status_label = stub_widget
            self.update_counter_label = stub_widget
            self.controller_text = stub_widget
            self.module_text = stub_widget
            self.module_frame = stub_widget
            self.creep_indicator = stub_widget
            self.reverse_indicator = stub_widget
            self.auto_status_indicator = stub_widget
            self.auto_status_text_label = stub_widget
            self.auto_toggle_indicator = stub_widget
            self.rover_status_indicator = stub_widget
            self.rover_status_text_label = stub_widget
            self.life_toggle_indicator = stub_widget
            return

        # Main container
        main_frame = ttk.Frame(self.root, padding="8")
        main_frame.grid(row=0, column=0, sticky="nsew")

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Placeholder for simulation mode warning banner (created dynamically)
        self._warning_banner_frame = None
        self._warning_banner_parent = main_frame

        # Main content frame
        content_frame = ttk.Frame(main_frame)
        content_frame.grid(row=1, column=0, sticky="nsew")
        content_frame.columnconfigure(1, weight=1)
        content_frame.rowconfigure(0, weight=1)

        # Sidebar
        self._create_sidebar(content_frame)

        # Main panels (controller + module)
        self._create_main_panels(content_frame)

    def _create_warning_banner(self, parent):
        """
        Create the big red warning banner for simulation mode.
        """
        warning_frame = ttk.Frame(parent, style="Banner.TFrame")
        warning_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        warning_frame.columnconfigure(0, weight=1)
        warning_frame.rowconfigure(0, weight=1)

        canvas = tk.Canvas(warning_frame, height=BANNER_HEIGHT, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="ew")
        self._warning_canvas = canvas

        if self._sim_view_var is None:
            self._sim_view_var = tk.StringVar(
                value=self._get_module_view_label(self._module_view)
            )
        if self._sim_view_dropdown is None:
            self._sim_view_dropdown = ttk.Combobox(
                warning_frame,
                textvariable=self._sim_view_var,
                values=self._get_module_view_labels(),
                state="readonly",
                width=18,
            )
            self._sim_view_dropdown.bind(
                "<<ComboboxSelected>>", self._on_sim_view_change
            )

        canvas.bind("<Configure>", self._redraw_warning_banner)
        self._redraw_warning_banner()

        return warning_frame

    def _redraw_warning_banner(self, _event: Optional[Any] = None):
        """Render diagonal stripes, label, and dropdown inside the banner canvas."""
        if not self._warning_canvas:
            return
        canvas = self._warning_canvas
        width = max(1, int(getattr(canvas, "winfo_width", lambda: 0)()))
        height = max(1, int(getattr(canvas, "winfo_height", lambda: 0)()))

        try:
            canvas.delete("all")
            canvas.configure(background="white")
        except Exception:
            return

        stripe_width = 14
        stripe_step = stripe_width * 2
        for x in range(-height, width + height + stripe_width, stripe_step):
            try:
                canvas.create_polygon(
                    x,
                    0,
                    x + stripe_width,
                    0,
                    x + stripe_width + height,
                    height,
                    x + height,
                    height,
                    fill="#d22",
                    outline="",
                )
            except Exception:
                break

        try:
            canvas.create_text(
                16,
                height // 2,
                anchor="w",
                text="Simulation Mode",
                fill="black",
                font=("Arial", 16, "bold"),
            )
        except Exception:
            pass

        if self._sim_view_dropdown is not None:
            try:
                canvas.create_window(
                    width - 12,
                    height // 2,
                    anchor="e",
                    window=self._sim_view_dropdown,
                )
            except Exception:
                pass

    def _get_module_view_labels(self) -> list[str]:
        return [MODULE_VIEW_LABELS[key] for key in MODULE_VIEW_ORDER]

    def _get_module_view_label(self, key: str) -> str:
        return MODULE_VIEW_LABELS.get(key, MODULE_VIEW_LABELS[DEFAULT_MODULE_VIEW_KEY])

    def _get_module_view_key(self, label: str) -> str:
        for key, value in MODULE_VIEW_LABELS.items():
            if value == label:
                return key
        return DEFAULT_MODULE_VIEW_KEY

    def _on_sim_view_change(self, _event: Optional[Any] = None) -> None:
        if not self.simulation_mode or self._sim_view_var is None:
            return
        label = self._sim_view_var.get()
        self._module_view_override = self._get_module_view_key(label)

    def _create_sidebar(self, parent):
        sidebar = ttk.Frame(parent, padding=SIDEBAR_PADDING)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.configure(width=SIDEBAR_WIDTH)
        sidebar.grid_propagate(False)

        row = 0
        self.creep_indicator, _label, row = self._add_indicator_row(
            sidebar, row, "Creep Mode"
        )
        self.reverse_indicator, _label, row = self._add_indicator_row(
            sidebar, row, "Reverse"
        )
        row = self._add_sidebar_separator(sidebar, row)

        (
            self.auto_status_indicator,
            self.auto_status_text_label,
            row,
        ) = self._add_indicator_row(sidebar, row, "Auto Status", show_state_label=True)
        self.auto_toggle_indicator, _label, row = self._add_indicator_row(
            sidebar, row, "Auto Toggle"
        )
        row = self._add_sidebar_separator(sidebar, row)

        (
            self.rover_status_indicator,
            self.rover_status_text_label,
            row,
        ) = self._add_indicator_row(sidebar, row, "Rover Status", show_state_label=True)
        row = self._add_sidebar_separator(sidebar, row)

        self.life_toggle_indicator, _label, row = self._add_indicator_row(
            sidebar, row, "Life Toggle"
        )
        row = self._add_sidebar_separator(sidebar, row)

        self.comm_status_label = ttk.Label(
            sidebar,
            text=self._format_comm_status(False),
            style=SIDEBAR_SMALL_STYLE,
            justify="left",
            wraplength=SIDEBAR_WIDTH - 16,
        )
        self.comm_status_label.grid(row=row, column=0, sticky="w")
        row += 1

        self.update_counter_label = ttk.Label(
            sidebar, text="Updates: 0", style=SIDEBAR_SMALL_STYLE
        )
        self.update_counter_label.grid(row=row, column=0, sticky="w")

    def _add_indicator_row(
        self, parent, row: int, label_text: str, show_state_label: bool = False
    ):
        row_frame = ttk.Frame(parent)
        row_frame.grid(row=row, column=0, sticky="ew", pady=2)
        row_frame.columnconfigure(0, weight=1)
        row_frame.columnconfigure(1, weight=0)

        label = ttk.Label(row_frame, text=label_text, style=SIDEBAR_LABEL_STYLE)
        label.grid(row=0, column=0, sticky="w")

        indicator = tk.Frame(
            row_frame,
            width=INDICATOR_SIZE,
            height=INDICATOR_SIZE,
            background="#aa0000",
            highlightthickness=1,
            highlightbackground="#333",
        )
        indicator.grid(row=0, column=1, sticky="e", padx=(8, 0))
        indicator.grid_propagate(False)

        state_label = None
        if show_state_label:
            state_label = ttk.Label(row_frame, text="", style=SIDEBAR_SMALL_STYLE)
            state_label.grid(row=1, column=0, columnspan=2, sticky="w")

        return indicator, state_label, row + 1

    def _add_sidebar_separator(self, parent, row: int) -> int:
        separator = ttk.Separator(parent, orient="horizontal")
        separator.grid(row=row, column=0, sticky="ew", pady=6)
        return row + 1

    def _create_main_panels(self, parent):
        main_frame = ttk.Frame(parent)
        main_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        main_frame.columnconfigure(0, weight=2)
        main_frame.columnconfigure(1, weight=4)
        main_frame.rowconfigure(0, weight=1)

        controller_frame = ttk.LabelFrame(
            main_frame, text="Controller Info", style=PANEL_STYLE
        )
        controller_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        controller_frame.columnconfigure(0, weight=1)
        controller_frame.rowconfigure(0, weight=1)

        controller_list = ttk.Frame(controller_frame)
        controller_list.grid(row=0, column=0, sticky="nsew")
        controller_list.columnconfigure(0, weight=1)
        controller_list.rowconfigure(0, weight=1)

        self.controller_text = tk.Text(
            controller_list, height=24, width=46, wrap=tk.WORD
        )
        controller_scroll = ttk.Scrollbar(
            controller_list, orient=tk.VERTICAL, command=self.controller_text.yview
        )
        self.controller_text.configure(yscrollcommand=controller_scroll.set)

        self.controller_text.grid(row=0, column=0, sticky="nsew")
        controller_scroll.grid(row=0, column=1, sticky="ns")

        self.module_frame = ttk.LabelFrame(
            main_frame, text="Module Info", style=PANEL_STYLE
        )
        self.module_frame.grid(row=0, column=1, sticky="nsew")
        self.module_frame.columnconfigure(0, weight=1)
        self.module_frame.rowconfigure(0, weight=1)

        module_list = ttk.Frame(self.module_frame)
        module_list.grid(row=0, column=0, sticky="nsew")
        module_list.columnconfigure(0, weight=1)
        module_list.rowconfigure(0, weight=1)

        self.module_text = tk.Text(module_list, height=24, wrap=tk.WORD)
        module_scroll = ttk.Scrollbar(
            module_list, orient=tk.VERTICAL, command=self.module_text.yview
        )
        self.module_text.configure(yscrollcommand=module_scroll.set)

        self.module_text.grid(row=0, column=0, sticky="nsew")
        module_scroll.grid(row=0, column=1, sticky="ns")

    def set_simulation_mode(self, is_simulation: bool):
        """
        Set simulation mode status and update the warning banner visibility.
        Call this after initialization to show/hide simulation banner based on actual connection status.

        Args:
            is_simulation: True if running in simulation mode (no real XBee connection)
        """
        self._show_simulation_banner = is_simulation
        self.simulation_mode = is_simulation
        if not is_simulation:
            self._module_view_override = None
        elif self._sim_view_var is not None:
            self._sim_view_var.set(
                self._get_module_view_label(self._get_active_module_view())
            )

        # Create or destroy the warning banner based on simulation status
        if is_simulation and self._warning_banner_frame is None:
            # Create the banner
            self._warning_banner_frame = self._create_warning_banner(
                self._warning_banner_parent
            )
        elif not is_simulation and self._warning_banner_frame is not None:
            # Destroy the banner
            self._warning_banner_frame.destroy()
            self._warning_banner_frame = None

    def _create_status_section(self, parent):
        """
        Create the status indicators section.
        """
        # Always use row 1 since banner may be added/removed dynamically
        row_offset = 1

        status_frame = ttk.LabelFrame(parent, text="System Status", padding="10")
        status_frame.grid(row=row_offset, column=0, sticky="new", padx=(0, 10))

        # Communication status
        self.comm_status_label = ttk.Label(
            status_frame, text="Communication: Disconnected", style="Status.TLabel"
        )
        self.comm_status_label.grid(row=0, column=0, sticky=tk.W, pady=2)

        # Mode indicators
        self.creep_status_label = ttk.Label(status_frame, text="Creep Mode: OFF")
        self.creep_status_label.grid(row=1, column=0, sticky=tk.W, pady=2)

        self.reverse_status_label = ttk.Label(status_frame, text="Reverse Mode: OFF")
        self.reverse_status_label.grid(row=2, column=0, sticky=tk.W, pady=2)

        # Update counter
        self.update_counter_label = ttk.Label(status_frame, text="Updates Sent: 0")
        self.update_counter_label.grid(row=3, column=0, sticky=tk.W, pady=2)

    def _create_controller_section(self, parent):
        """
        Create the controller information section.
        """
        # Always use row 1 since banner may be added/removed dynamically
        row_offset = 1

        controller_frame = ttk.LabelFrame(
            parent, text="Controller Status", padding="10"
        )
        controller_frame.grid(row=row_offset, column=1, sticky="nsew")
        controller_frame.columnconfigure(0, weight=1)

        # Controller list with scrollbar
        list_frame = ttk.Frame(controller_frame)
        list_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        list_frame.columnconfigure(0, weight=1)

        self.controller_text = tk.Text(list_frame, height=40, width=50, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.controller_text.yview
        )
        self.controller_text.configure(yscrollcommand=scrollbar.set)

        self.controller_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        list_frame.rowconfigure(0, weight=1)
        controller_frame.rowconfigure(0, weight=1)

    def _create_telemetry_section(self, parent):
        """
        Create the telemetry display section.
        """
        # Always use row 2 since banner may be added/removed dynamically
        row_offset = 2

        telemetry_frame = ttk.LabelFrame(parent, text="Telemetry Data", padding="10")
        telemetry_frame.grid(
            row=row_offset, column=0, columnspan=2, sticky="nsew", pady=(10, 0)
        )
        telemetry_frame.columnconfigure(0, weight=1)

        # Telemetry display with scrollbar
        tel_frame = ttk.Frame(telemetry_frame)
        tel_frame.grid(row=0, column=0, sticky="nsew")
        tel_frame.columnconfigure(0, weight=1)

        self.telemetry_text = tk.Text(tel_frame, height=8, wrap=tk.WORD)
        tel_scrollbar = ttk.Scrollbar(
            tel_frame, orient=tk.VERTICAL, command=self.telemetry_text.yview
        )
        self.telemetry_text.configure(yscrollcommand=tel_scrollbar.set)

        self.telemetry_text.grid(row=0, column=0, sticky="nsew")
        tel_scrollbar.grid(row=0, column=1, sticky="ns")

        tel_frame.rowconfigure(0, weight=1)
        telemetry_frame.rowconfigure(0, weight=1)
        parent.rowconfigure(row_offset, weight=1)

    def update_controller_display(
        self, controller_id: int, controller_data: Dict[str, Any]
    ):
        """
        Update controller display with new data.

        Args:
            controller_id: ID of the controller
            controller_data: Dictionary containing controller information
        """
        # Protect updates to controller data with a lock to avoid concurrent
        # modification while UI readers iterate or copy the data.
        with self._controller_lock:
            self.controllers[controller_id] = controller_data

    def update_controller_values(self, values: Dict[str, Any]):
        """
        Update controller values display.

        Args:
            values: Dictionary mapping controller type name to its values dict.
                    e.g., {"Xbox": {...}, "N64": {...}}
                    Also supports old flat format: {"ly": 0.5, ...} for compatibility.
        """
        # Protect updates to controller values with a lock to avoid concurrent
        # modification while UI readers iterate or copy the data.
        with self._controller_lock:
            # Handle both old (flat) and new (nested per-controller) format
            if values and isinstance(next(iter(values.values()), None), dict):
                # New nested format - deep copy each controller's values
                self.controller_values = {k: dict(v) for k, v in values.items()}
            else:
                # Old flat format - store as-is for backward compatibility
                self.controller_values = dict(values) if values else {}

    def update_modes(self, creep: bool = False, reverse: bool = False):
        """
        Update mode indicators.

        Args:
            creep: Whether creep mode is active
            reverse: Whether reverse mode is active
        """
        # Protect simultaneous updates by other threads (UI thread may read the flags)
        with self._mode_lock:
            self.creep_mode = creep
            self.reverse_mode = reverse

    def update_telemetry(self, telemetry: Dict[str, Any]):
        """
        Update telemetry data display.

        Args:
            telemetry: Dictionary containing telemetry data
        """
        # Protect telemetry updates with _telemetry_lock to avoid concurrent modification during UI reads.
        with self._telemetry_lock:
            self.telemetry_data.update(telemetry)

        self._update_module_view_from_telemetry(telemetry)

    def _update_module_view_from_telemetry(self, telemetry: Dict[str, Any]) -> None:
        """Update active module view based on telemetry hints (non-sim mode)."""
        if self.simulation_mode:
            return

        module_value = next(
            (
                telemetry[key]
                for key in ("active_module", "module", "module_view")
                if key in telemetry
            ),
            None,
        )
        if module_value is None:
            return

        if isinstance(module_value, str):
            self._set_module_view_from_string(module_value)
        elif isinstance(module_value, (int, float)):
            self._set_module_view_from_numeric(int(module_value))

    def _set_module_view_from_string(self, module_value: str) -> None:
        lowered = module_value.lower()
        if "life" in lowered:
            self._module_view = "life"
            return
        if "auto" in lowered or "lidar" in lowered:
            self._module_view = "auto"
            return
        if "arm" in lowered or "manip" in lowered:
            self._module_view = "arm"

    def _set_module_view_from_numeric(self, num_value: int) -> None:
        mapping = {1: "life", 2: "auto", 3: "arm"}
        self._module_view = mapping.get(num_value, self._module_view)

    def update_communication_status(self, connected: bool, message_count: int = 0):
        """
        Update communication status display.

        Args:
            connected: Whether communication is active
            message_count: Number of messages sent
        """
        if getattr(self, "comm_status_label", None):
            self.comm_status_label.config(text=self._format_comm_status(connected))

        if getattr(self, "update_counter_label", None):
            self.update_counter_label.config(text=f"Updates: {message_count}")

    def _format_comm_status(self, connected: bool) -> str:
        status = "Connected" if connected else "Disconnected"
        if self.simulation_mode:
            return f"Comm:\n{status}\n(SIMULATION)"
        return f"Comm:\n{status}"

    def _update_display_content(self):
        """
        Update all display content. Called from update loop.
        """
        # Update sidebar indicators
        self._update_sidebar_statuses()

        # Update controller display
        self._update_controller_text()

        # Update module display
        self._update_module_text()

    def _update_sidebar_statuses(self):
        """Update sidebar indicator colors based on current mode/telemetry."""
        creep_on, reverse_on = self._get_mode_flags()
        self._set_indicator_color(self.creep_indicator, creep_on)
        self._set_indicator_color(self.reverse_indicator, reverse_on)

        telemetry = self._snapshot_telemetry()
        self._update_auto_status_indicator(telemetry)
        self._update_auto_toggle_indicator(telemetry)
        self._update_rover_status_indicator(telemetry)
        self._update_life_toggle_indicator(telemetry)

    def _get_mode_flags(self) -> tuple[bool, bool]:
        with self._mode_lock:
            return bool(self.creep_mode), bool(self.reverse_mode)

    def _snapshot_telemetry(self) -> Dict[str, Any]:
        with self._telemetry_lock:
            return self.telemetry_data.copy()

    def _update_auto_status_indicator(self, telemetry: Dict[str, Any]) -> None:
        auto_state = self._resolve_auto_status(telemetry)
        self._auto_status_state = auto_state

        if auto_state == "autonomous":
            self._set_indicator_color(self.auto_status_indicator, True, on_color="#d22")
            if self.auto_status_text_label is not None:
                self.auto_status_text_label.config(text="Autonomous")
            return
        if auto_state == "arrived":
            flash_on = int(time.time() * 2) % 2 == 0
            color = "#26a269" if flash_on else "#ffffff"
            self._set_indicator_color(self.auto_status_indicator, True, on_color=color)
            if self.auto_status_text_label is not None:
                self.auto_status_text_label.config(text="Arrived")
            return

        self._set_indicator_color(self.auto_status_indicator, True, on_color="#1c71d8")
        if self.auto_status_text_label is not None:
            self.auto_status_text_label.config(text="Teleop")

    def _update_auto_toggle_indicator(self, telemetry: Dict[str, Any]) -> None:
        auto_toggle = self._resolve_boolean_flag(
            telemetry,
            ["auto_toggle", "auto_enabled", "autonomy_enabled"],
        )
        if auto_toggle is not None:
            self._set_indicator_color(self.auto_toggle_indicator, auto_toggle)

    def _update_rover_status_indicator(self, telemetry: Dict[str, Any]) -> None:
        estop = self._resolve_estop_status(telemetry)
        if estop is None:
            return
        ok_state = not estop
        self._set_indicator_color(self.rover_status_indicator, ok_state)
        if self.rover_status_text_label is not None:
            self.rover_status_text_label.config(text="OK" if ok_state else "ESTOPPED")

    def _update_life_toggle_indicator(self, telemetry: Dict[str, Any]) -> None:
        life_toggle = self._resolve_boolean_flag(
            telemetry,
            ["life_toggle", "life_enabled", "life_detection"],
        )
        if life_toggle is not None:
            self._set_indicator_color(self.life_toggle_indicator, life_toggle)

    def _set_indicator_color(self, indicator, is_on: bool, on_color: str = "#26a269"):
        if not indicator:
            return
        color = on_color if is_on else "#a51d2d"
        try:
            indicator.configure(background=color)
        except Exception:
            pass

    def _resolve_boolean_flag(self, telemetry: Dict[str, Any], keys: list[str]):
        for key in keys:
            if key not in telemetry:
                continue
            value = telemetry.get(key)
            if isinstance(value, str):
                lowered = value.lower()
                if lowered in ("1", "true", "yes", "on", "enabled", "active"):
                    return True
                if lowered in ("0", "false", "no", "off", "disabled", "inactive"):
                    return False
            return bool(value)
        return None

    def _resolve_estop_status(self, telemetry: Dict[str, Any]) -> Optional[bool]:
        estop_value = None
        for key in ("estop", "e_stop", "rover_status", "rover_estop"):
            if key in telemetry:
                estop_value = telemetry.get(key)
                break

        if estop_value is None:
            return None
        if isinstance(estop_value, str):
            lowered = estop_value.lower()
            if "estop" in lowered or "e-stop" in lowered:
                return True
            if lowered in ("ok", "nominal", "running"):
                return False
        if isinstance(estop_value, bool):
            return estop_value
        return bool(estop_value)

    def _resolve_auto_status(self, telemetry: Dict[str, Any]) -> str:
        value = next(
            (
                telemetry[key]
                for key in ("auto_status", "autonomy_status", "autonomous_status")
                if key in telemetry
            ),
            None,
        )
        if value is None:
            return self._auto_status_state
        if isinstance(value, bool):
            return "autonomous" if value else "teleop"
        if isinstance(value, (int, float)):
            return self._resolve_auto_status_numeric(value)
        if isinstance(value, str):
            return self._resolve_auto_status_string(value)
        return "teleop"

    def _resolve_auto_status_numeric(self, value: float) -> str:
        iv = int(value)
        if iv >= 2:
            return "arrived"
        if iv == 1:
            return "autonomous"
        return "teleop"

    def _resolve_auto_status_string(self, value: str) -> str:
        lowered = value.lower()
        if any(s in lowered for s in ("arriv", "success", "target")):
            return "arrived"
        if "auto" in lowered:
            return "autonomous"
        if "tele" in lowered or "manual" in lowered:
            return "teleop"
        return "teleop"

    def _update_controller_text(self):
        """
        Update the controller text display while preserving scroll position.
        """
        if not getattr(self, "controller_text", None):
            return

        scroll_pos = self._get_text_scroll_pos(self.controller_text)
        self.controller_text.delete(1.0, tk.END)

        (
            controllers_copy,
            controller_values_copy,
            nested_values,
        ) = self._snapshot_controller_state()
        if not controllers_copy:
            self.controller_text.insert(tk.END, "No controllers connected\n")
            return

        self._insert_controller_entries(
            controllers_copy, controller_values_copy, nested_values
        )

        self._restore_text_scroll_pos(self.controller_text, scroll_pos)

    def _snapshot_controller_state(
        self,
    ) -> tuple[Dict[int, Dict[str, Any]], Dict[str, Any], bool]:
        """Return copies of controller metadata and values for rendering."""
        with self._controller_lock:
            controllers_copy = self.controllers.copy()
            nested_values = False
            if self.controller_values and isinstance(
                next(iter(self.controller_values.values()), None), dict
            ):
                controller_values_copy = {
                    k: dict(v) for k, v in self.controller_values.items()
                }
                nested_values = True
            else:
                controller_values_copy = dict(self.controller_values)
        return controllers_copy, controller_values_copy, nested_values

    def _insert_controller_entries(
        self,
        controllers_copy: Dict[int, Dict[str, Any]],
        controller_values_copy: Dict[str, Any],
        nested_values: bool,
    ) -> None:
        for controller_id, data in controllers_copy.items():
            self._insert_controller_info(
                controller_id, data, controller_values_copy, nested_values
            )

    def _get_text_scroll_pos(self, widget) -> tuple[float, float]:
        try:
            return widget.yview()
        except Exception:
            return (0.0, 1.0)

    def _restore_text_scroll_pos(self, widget, scroll_pos: tuple[float, float]) -> None:
        try:
            widget.yview_moveto(scroll_pos[0])
        except Exception:
            pass

    def _insert_controller_info(
        self,
        controller_id: int,
        data: Dict[str, Any],
        controller_values_copy: Dict[str, Any],
        nested_values: bool,
    ):
        """Helper method to insert individual controller information."""
        _ = controller_id
        controller_name = data.get("name", "Unknown")
        self.controller_text.insert(tk.END, f"{controller_name}:\n")
        self.controller_text.insert(tk.END, f"  GUID: {data.get('guid', 'Unknown')}\n")

        resolved_values = self._resolve_controller_values_for_display(
            controller_name, data, controller_values_copy, nested_values
        )
        if resolved_values:
            self._insert_controller_values(resolved_values)

        self.controller_text.insert(tk.END, "\n")

    def _resolve_controller_values_for_display(
        self,
        controller_name: str,
        data: Dict[str, Any],
        controller_values_copy: Dict[str, Any],
        nested_values: bool,
    ) -> Optional[Dict[str, Any]]:
        if not nested_values:
            return controller_values_copy or None

        resolved_type = self._resolve_controller_type_for_display(
            controller_name, data, controller_values_copy
        )
        if resolved_type and resolved_type in controller_values_copy:
            return controller_values_copy[resolved_type]

        return self._match_controller_values_by_name(
            controller_values_copy, controller_name
        )

    def _resolve_controller_type_for_display(
        self,
        controller_name: str,
        data: Dict[str, Any],
        controller_values_copy: Dict[str, Any],
    ) -> Optional[str]:
        # Prefer explicit controller type passed in controller_data to avoid
        # name-based mismatches when controllers have generic names.
        controller_type = data.get("type")
        if isinstance(controller_type, str):
            for ctype in controller_values_copy:
                if isinstance(ctype, str) and ctype.lower() == controller_type.lower():
                    return ctype
            return controller_type.lower()

        # Fall back to name-based detection
        return self._detect_controller_type_from_name(controller_name)

    def _match_controller_values_by_name(
        self, controller_values_copy: Dict[str, Any], controller_name: str
    ) -> Optional[Dict[str, Any]]:
        if not controller_values_copy:
            return None
        for ctype in controller_values_copy:
            if (
                ctype.lower() in controller_name.lower()
                or controller_name.lower() in ctype.lower()
            ):
                return controller_values_copy[ctype]
        return None

    def _detect_controller_type_from_name(self, name: str) -> Optional[str]:
        """Detect controller type from its name string."""
        if not isinstance(name, str):
            return None
        lname = name.lower()
        if "xbox" in lname or "x-box" in lname:
            return CONSTANTS.XBOX.NAME
        if (
            "n64" in lname
            or "dinput" in lname
            or "directinput" in lname
            or "direct input" in lname
        ):
            return CONSTANTS.N64.NAME
        return None

    def _insert_controller_values(self, controller_values_copy: Dict[str, Any]):
        """Helper method to insert controller values, showing only string key aliases."""
        self.controller_text.insert(tk.END, "  Current Values:\n")
        for key, value in controller_values_copy.items():
            # Only show string keys (human-readable aliases), skip numeric keys
            if not isinstance(key, str):
                continue
            if isinstance(value, bytes):
                try:
                    # Empty bytes evaluate to False; interpret as 0.
                    value = int.from_bytes(value, "big") if value else 0
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to convert bytes value for {key}: {e}")
                    value = "<invalid>"
            self.controller_text.insert(tk.END, f"    {key}: {value}\n")

    def _update_telemetry_text(self):
        """
        Update the telemetry text display.
        """
        self._update_module_text()

    def _update_module_text(self):
        """Update module panel text for current active module view."""
        if not getattr(self, "module_text", None):
            return

        self.module_text.delete(1.0, tk.END)
        module_key, module_label = self._get_module_view_metadata()
        self._set_module_frame_label(module_label)

        td_copy = self._snapshot_telemetry()
        if not td_copy:
            self.module_text.insert(tk.END, f"{module_label} module data unavailable\n")
            return

        filtered = self._filter_telemetry_for_module(td_copy, module_key) or td_copy
        self._render_module_data(module_label, filtered)

    def _get_module_view_metadata(self) -> tuple[str, str]:
        module_key = self._get_active_module_view()
        return module_key, self._get_module_view_label(module_key)

    def _set_module_frame_label(self, module_label: str) -> None:
        if getattr(self, "module_frame", None):
            try:
                self.module_frame.config(text=f"{module_label} Module")
            except Exception:
                pass

    def _render_module_data(self, module_label: str, data: Dict[str, Any]) -> None:
        self.module_text.insert(
            tk.END,
            f"{module_label} Data (Updated: {time.strftime('%H:%M:%S')}):\n\n",
        )
        for key, value in data.items():
            self.module_text.insert(tk.END, f"{key}: {value}\n")

    def _get_active_module_view(self) -> str:
        if self.simulation_mode and self._module_view_override:
            return self._module_view_override
        return self._module_view

    def _filter_telemetry_for_module(
        self, telemetry: Dict[str, Any], module_key: str
    ) -> Dict[str, Any]:
        prefixes = {
            "life": ("life_", "life ", "victim_", "detection_"),
            "auto": ("auto_", "autonomy_", "lidar_", "nav_", "path_"),
            "arm": ("arm_", "servo_", "joint_", "encoder_", "gripper_"),
        }
        module_prefixes = prefixes.get(module_key, ())
        if not module_prefixes:
            return {}

        filtered = {
            key: value
            for key, value in telemetry.items()
            if isinstance(key, str) and key.lower().startswith(module_prefixes)
        }
        return filtered

    def _update_loop(self):
        """
        Main update loop for the display (runs in separate thread).
        """
        while self.running:
            try:
                # Schedule update on main thread (wrap to match expected signature)
                self.root.after_idle(lambda: self._update_display_content())  # type: ignore[arg-type]
                time.sleep(0.1)  # Update every 100ms
            except Exception:
                logger.exception("Display update error")
                break

    def run(self):
        """
        Start the tkinter main loop.
        """
        # Avoid launching the GUI mainloop during pytest runs to keep tests non-blocking
        try:
            import sys

            # Honor explicit test override via XBEE_TEST_OVERRIDE_GUI so tests can opt into
            # launching the real GUI when needed
            override_gui = (os.getenv("XBEE_TEST_OVERRIDE_GUI") or "").lower() in (
                "1",
                "true",
                "yes",
            )
            if "pytest" in sys.modules and not override_gui:
                logger.debug(
                    "Detected pytest: skipping tkinter mainloop to avoid blocking tests"
                )
                self.running = False
                return
        except Exception:
            # Best-effort check; don't let this break the normal execution path
            pass
        try:
            self.root.mainloop()
        finally:
            self.running = False

    def quit(self):
        """
        Quit the display system.
        """
        self.running = False
        if self.root:
            self.root.quit()
        # Try to join update thread on quit to ensure clean shutdown and avoid test race conditions
        try:
            if getattr(self, "update_thread", None) and self.update_thread.is_alive():
                self.update_thread.join(timeout=1.0)
        except Exception:
            logger.exception("Failed to join update thread during quit")


def create_display(prefer_gui: Optional[bool] = None) -> BaseDisplay:
    """Factory that returns the appropriate display object.

    prefer_gui: if True, try to create a Tkinter UI even if env var present. If False, force headless.
    If None, use environment variable XBEE_NO_GUI to determine behavior.

    This function centralizes the decision whether to return a HeadlessDisplay or a
    TkinterDisplay. Callers should use this function rather than instantiating
    TkinterDisplay directly; TkinterDisplay's constructor may raise exceptions
    when a GUI cannot be created or when headless mode is requested.
    """
    # Tests patch os.getenv, so use os.getenv here to honor the test harness.
    env_no_gui = (os.getenv("XBEE_NO_GUI") or "").lower() in ("1", "true", "yes")

    # When running under pytest, prefer headless mode by default to avoid
    # accidentally launching GUI mainloops that block tests. Individual tests
    # that need to run GUI code should explicitly set XBEE_TEST_OVERRIDE_GUI=1
    # so the default can be overridden for that test only.
    try:
        import sys

        override_gui = (os.getenv("XBEE_TEST_OVERRIDE_GUI") or "").lower() in (
            "1",
            "true",
            "yes",
        )
        if "pytest" in sys.modules and not override_gui:
            env_no_gui = True
    except Exception:
        # Best-effort; don't let this change the behavior in production
        pass

    # Force headless if explicitly requested, env var set, or Tk unavailable
    if prefer_gui is False or (prefer_gui is None and env_no_gui) or not TK_AVAILABLE:
        logger.info("Using HeadlessDisplay (GUI disabled or unavailable)")
        return HeadlessDisplay()

    try:
        return TkinterDisplay()
    except (ImportError, RuntimeError, ValueError) as e:
        # Expected error types that indicate GUI cannot be used in this environment.
        logger.warning(
            f"Failed to initialize TkinterDisplay ({e}). Using headless display."
        )
        return HeadlessDisplay()
    except Exception as e:
        # Fallback to HeadlessDisplay with a warning if Tkinter initialization fails
        logger.warning(
            f"Failed to initialize TkinterDisplay ({e}). Using headless display."
        )
        return HeadlessDisplay()


__all__ = ["BaseDisplay", "TkinterDisplay", "HeadlessDisplay", "create_display"]
