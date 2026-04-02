"""
Tkinter GUI display for the rover basestation.

This is the main GUI class. For headless mode, see base.py.
For telemetry interpretation, see telemetry.py.
"""

import logging
import os
import threading
import time
from typing import Any, Callable, Dict, Optional

from xbee.config.constants import CONSTANTS
from xbee.controller.detection import detect_controller_type
from xbee.display.base import (
    BANNER_HEIGHT,
    DEFAULT_MODULE_VIEW_KEY,
    INDICATOR_SIZE,
    MODULE_VIEW_LABELS,
    MODULE_VIEW_ORDER,
    PANEL_LABEL_STYLE,
    PANEL_STYLE,
    SIDEBAR_LABEL_STYLE,
    SIDEBAR_SMALL_STYLE,
    SIDEBAR_WIDTH,
    TK_AVAILABLE,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    BaseDisplay,
    _GenericWidgetStub,
    _env_flag_enabled,
    tk,
    ttk,
)
from xbee.display.telemetry import (
    filter_telemetry_for_module,
    resolve_auto_status,
    resolve_boolean_flag,
    resolve_estop_status,
)

logger = logging.getLogger(__name__)


def _is_mock_object(value: Any) -> bool:
    """Return True when *value* is a unittest.mock object."""
    try:
        import unittest.mock as _mock

        return isinstance(value, _mock.Mock)
    except Exception:
        return False


class TkinterDisplay(BaseDisplay):
    def __init__(self):
        env_no_gui = _env_flag_enabled("XBEE_NO_GUI")
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
            logger.error("Tkinter initialization failed (%s).", e)
            raise

        # Controller data
        self.controllers = {}
        self.controller_values = {}
        self._controller_lock = threading.Lock()
        self._mode_lock = threading.Lock()

        # Keyboard state (life detection input)
        self._keyboard_state: Dict[str, int] = {}
        self._keyboard_connected: bool = False

        # Mode flags
        self.creep_mode = True
        self.reverse_mode = False
        self.simulation_mode = CONSTANTS.SIMULATION_MODE
        self._show_simulation_banner = False

        # Telemetry data
        self.telemetry_data = {}
        self._telemetry_lock = threading.Lock()

        # Widget references (initialized by _setup_ui)
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
        self.arm_toggle_indicator: Any = None
        self.rover_status_indicator: Any = None
        self.rover_status_text_label: Any = None
        self.life_toggle_indicator: Any = None

        # Simulation banner widgets
        self._warning_canvas: Any = None
        self._sim_view_var: Any = None
        self._sim_view_dropdown: Any = None
        self._warning_banner_frame: Any = None
        self._warning_banner_parent: Any = self.root

        # Module view state
        self._module_view = "nothing"
        self._module_view_override: Optional[str] = None
        self._auto_status_state: str = "teleop"

        self._setup_ui()
        self._setup_styles()

        # Start UI update thread
        self.running = True
        self._ui_update_pending = threading.Event()
        self._schedule_ui_pump()
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()

    # ------------------------------------------------------------------
    # Styles
    # ------------------------------------------------------------------

    def _setup_styles(self):
        self.style = ttk.Style()
        self.style.configure("Banner.TFrame", relief="raised", borderwidth=2)
        self.style.configure(PANEL_STYLE, padding=8)
        self.style.configure(PANEL_LABEL_STYLE, font=("Arial", 12, "bold"))
        self.style.configure(SIDEBAR_LABEL_STYLE, font=("Arial", 11, "bold"))
        self.style.configure(SIDEBAR_SMALL_STYLE, font=("Arial", 9))

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        # Skip UI setup if root is a test mock
        try:
            import unittest.mock as _unittest_mock

            mock_cls = getattr(_unittest_mock, "Mock", None)
        except Exception:
            mock_cls = None

        if mock_cls is not None and isinstance(self.root, mock_cls):
            logger.info("Detected mock tkinter root; skipping UI setup")
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
            self.arm_toggle_indicator = stub_widget
            self.rover_status_indicator = stub_widget
            self.rover_status_text_label = stub_widget
            self.life_toggle_indicator = stub_widget
            return

        # Main container
        main_frame = ttk.Frame(self.root, padding="8")
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        self._warning_banner_parent = main_frame

        content_frame = ttk.Frame(main_frame)
        content_frame.grid(row=1, column=0, sticky="nsew")
        content_frame.columnconfigure(1, weight=1)
        content_frame.rowconfigure(0, weight=1)

        self._create_sidebar(content_frame)
        self._create_main_panels(content_frame)

    # ------------------------------------------------------------------
    # Warning banner (simulation mode)
    # ------------------------------------------------------------------

    def _create_warning_banner(self, parent):
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

    # ------------------------------------------------------------------
    # Module view helpers
    # ------------------------------------------------------------------

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

    def _get_active_module_view(self) -> str:
        if self.simulation_mode and self._module_view_override:
            return self._module_view_override
        return self._module_view

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    def _create_sidebar(self, parent):
        sidebar = ttk.Frame(parent, padding=(4, 4))
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

        self.auto_status_indicator, self.auto_status_text_label, row = (
            self._add_indicator_row(sidebar, row, "Auto Status", show_state_label=True)
        )
        self.auto_toggle_indicator, _label, row = self._add_indicator_row(
            sidebar, row, "Auto Toggle"
        )
        row = self._add_sidebar_separator(sidebar, row)

        self.arm_toggle_indicator, _label, row = self._add_indicator_row(
            sidebar, row, "Arm Toggle"
        )
        row = self._add_sidebar_separator(sidebar, row)

        self.rover_status_indicator, self.rover_status_text_label, row = (
            self._add_indicator_row(sidebar, row, "Rover Status", show_state_label=True)
        )
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

    # ------------------------------------------------------------------
    # Main panels
    # ------------------------------------------------------------------

    def _create_main_panels(self, parent):
        main_frame = ttk.Frame(parent)
        main_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        main_frame.columnconfigure(0, weight=2)
        main_frame.columnconfigure(1, weight=4)
        main_frame.rowconfigure(0, weight=1)

        # Controller panel
        controller_frame = ttk.LabelFrame(
            main_frame, text="Input Devices", style=PANEL_STYLE
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
        self.controller_text.config(state="disabled")

        # Module panel
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
        self.module_text.config(state="disabled")

    # ------------------------------------------------------------------
    # BaseDisplay API implementation
    # ------------------------------------------------------------------

    def set_simulation_mode(self, is_simulation: bool):
        self._show_simulation_banner = is_simulation
        self.simulation_mode = is_simulation
        if not is_simulation:
            self._module_view_override = None
        elif self._sim_view_var is not None:
            self._sim_view_var.set(
                self._get_module_view_label(self._get_active_module_view())
            )

        if is_simulation and self._warning_banner_frame is None:
            self._warning_banner_frame = self._create_warning_banner(
                self._warning_banner_parent
            )
        elif not is_simulation and self._warning_banner_frame is not None:
            self._warning_banner_frame.destroy()
            self._warning_banner_frame = None

    def update_controller_display(
        self, controller_id: int, controller_data: Dict[str, Any]
    ):
        with self._controller_lock:
            self.controllers[controller_id] = controller_data

    def update_controller_values(self, values: Dict[str, Any]):
        with self._controller_lock:
            if values and isinstance(next(iter(values.values()), None), dict):
                self.controller_values = {k: dict(v) for k, v in values.items()}
            else:
                self.controller_values = dict(values) if values else {}

    def update_keyboard_state(
        self, state: Dict[str, int], connected: bool
    ) -> None:
        with self._controller_lock:
            self._keyboard_state = state.copy() if state else {}
            self._keyboard_connected = connected

    def update_modes(self, creep: bool = False, reverse: bool = False):
        with self._mode_lock:
            self.creep_mode = creep
            self.reverse_mode = reverse

    def update_telemetry(self, telemetry: Dict[str, Any]):
        with self._telemetry_lock:
            self.telemetry_data.update(telemetry)
        self._update_module_view_from_telemetry(telemetry)

    def update_communication_status(self, connected: bool, message_count: int = 0):
        def _apply_status_update():
            if getattr(self, "comm_status_label", None):
                self.comm_status_label.config(text=self._format_comm_status(connected))
            if getattr(self, "update_counter_label", None):
                self.update_counter_label.config(text=f"Updates: {message_count}")

        self._run_on_ui_thread(_apply_status_update)

    def run(self):
        try:
            import sys

            override_gui = _env_flag_enabled("XBEE_TEST_OVERRIDE_GUI")
            if "pytest" in sys.modules and not override_gui:
                logger.debug("Detected pytest: skipping tkinter mainloop")
                self.running = False
                return
        except Exception:
            pass
        try:
            self.root.mainloop()
        finally:
            self.running = False

    def quit(self):
        self.running = False
        self._request_root_quit()
        try:
            if getattr(self, "update_thread", None) and self.update_thread.is_alive():
                self.update_thread.join(timeout=1.0)
        except Exception:
            logger.exception("Failed to join update thread during quit")

    def _request_root_quit(self) -> None:
        """Request GUI shutdown, even from non-main threads."""
        if not self.root:
            return

        if threading.current_thread() is threading.main_thread():
            self.root.quit()
            return

        after_idle = getattr(self.root, "after_idle", None)
        if callable(after_idle):
            try:
                after_idle(self.root.quit)
                return
            except Exception:
                logger.exception("Failed scheduling root.quit on UI thread")

        # Best-effort fallback during teardown when scheduling is unavailable.
        try:
            self.root.quit()
        except Exception:
            logger.exception("Failed to call root.quit directly")

    # ------------------------------------------------------------------
    # Internal: display update loop
    # ------------------------------------------------------------------

    def _update_loop(self):
        while self.running:
            try:
                self._ui_update_pending.set()
                time.sleep(0.1)
            except Exception:
                logger.exception("Display update error")
                break

    def _run_on_ui_thread(self, callback: Callable[[], None]) -> None:
        """Run callback immediately on UI thread, otherwise schedule it."""
        if threading.current_thread() is threading.main_thread():
            callback()
            return

        after_idle = getattr(self.root, "after_idle", None)
        if callable(after_idle):
            try:
                after_idle(callback)
                return
            except Exception:
                logger.exception("Failed scheduling callback on UI thread")

        # Direct cross-thread widget calls can be unsafe on real Tk roots.
        # Allow direct fallback only for mock roots used in tests.
        if _is_mock_object(self.root):
            callback()
            return

        logger.debug("Skipping direct callback execution outside UI thread")

    def _schedule_ui_pump(self) -> None:
        """Pump queued UI updates from main thread on a recurring timer."""
        if not self.running:
            return

        if self._ui_update_pending.is_set():
            self._ui_update_pending.clear()
            self._update_display_content()

        if not self.running:
            return

        after = getattr(self.root, "after", None)
        if callable(after):
            after(100, self._schedule_ui_pump)
            return

        after_idle = getattr(self.root, "after_idle", None)
        if callable(after_idle):
            after_idle(self._schedule_ui_pump)

    def _update_display_content(self):
        self._update_sidebar_statuses()
        self._update_controller_text()
        self._update_module_text()

    # ------------------------------------------------------------------
    # Sidebar updates
    # ------------------------------------------------------------------

    def _update_sidebar_statuses(self):
        creep_on, reverse_on = self._get_mode_flags()
        self._set_indicator_color(self.creep_indicator, creep_on)
        self._set_indicator_color(self.reverse_indicator, reverse_on)

        telemetry = self._snapshot_telemetry()
        self._update_auto_status_indicator(telemetry)
        self._update_module_toggle_indicators(telemetry)
        self._update_rover_status_indicator(telemetry)

    def _get_mode_flags(self) -> tuple[bool, bool]:
        with self._mode_lock:
            return bool(self.creep_mode), bool(self.reverse_mode)

    def _snapshot_telemetry(self) -> Dict[str, Any]:
        with self._telemetry_lock:
            return self.telemetry_data.copy()

    def _update_auto_status_indicator(self, telemetry: Dict[str, Any]) -> None:
        auto_state = resolve_auto_status(telemetry, self._auto_status_state)
        self._auto_status_state = auto_state

        if auto_state == "autonomous":
            self._set_indicator_color(self.auto_status_indicator, True, on_color="#d22")
            if self.auto_status_text_label is not None:
                self.auto_status_text_label.config(text="Autonomous")
        elif auto_state == "arrived":
            flash_on = int(time.time() * 2) % 2 == 0
            color = "#26a269" if flash_on else "#ffffff"
            self._set_indicator_color(self.auto_status_indicator, True, on_color=color)
            if self.auto_status_text_label is not None:
                self.auto_status_text_label.config(text="Arrived")
        else:
            self._set_indicator_color(
                self.auto_status_indicator, True, on_color="#1c71d8"
            )
            if self.auto_status_text_label is not None:
                self.auto_status_text_label.config(text="Teleop")

    def _update_module_toggle_indicators(self, telemetry: Dict[str, Any]) -> None:
        """Update Auto/Arm/Life toggle colors based on rover-reported enabled state.

        Green when the subsystem is enabled on the rover, red when disabled.
        Only updates once subsystem enablement data has been received so
        toggles remain in their default (red) state until the rover sends
        its first ``subsystem_enabled`` heartbeat.
        """
        has_subsystem_info = any(
            key in telemetry
            for key in ("arm_enabled", "auto_enabled", "life_enabled")
        )
        if not has_subsystem_info:
            return

        module_indicators: Dict[str, tuple] = {
            "auto": (self.auto_toggle_indicator, "auto_enabled"),
            "arm": (self.arm_toggle_indicator, "arm_enabled"),
            "life": (self.life_toggle_indicator, "life_enabled"),
        }
        for module_key, (indicator, telemetry_key) in module_indicators.items():
            is_enabled = resolve_boolean_flag(telemetry, [telemetry_key])
            self._set_indicator_color(indicator, is_enabled)

    def _update_rover_status_indicator(self, telemetry: Dict[str, Any]) -> None:
        estop = resolve_estop_status(telemetry)
        if estop is None:
            return
        ok_state = not estop
        self._set_indicator_color(self.rover_status_indicator, ok_state)
        if self.rover_status_text_label is not None:
            self.rover_status_text_label.config(text="OK" if ok_state else "ESTOPPED")

    def _set_indicator_color(self, indicator, is_on: bool, on_color: str = "#26a269"):
        if not indicator:
            return
        color = on_color if is_on else "#a51d2d"
        try:
            indicator.configure(background=color)
        except Exception:
            pass

    def _format_comm_status(self, connected: bool) -> str:
        status = "Connected" if connected else "Disconnected"
        if self.simulation_mode:
            return f"Comm:\n{status}\n(SIMULATION)"
        return f"Comm:\n{status}"

    # ------------------------------------------------------------------
    # Telemetry / module view
    # ------------------------------------------------------------------

    def _update_module_view_from_telemetry(self, telemetry: Dict[str, Any]) -> None:
        if self.simulation_mode:
            return

        arm_enabled = resolve_boolean_flag(telemetry, ["arm_enabled"])
        auto_enabled = resolve_boolean_flag(telemetry, ["auto_enabled"])
        life_enabled = resolve_boolean_flag(telemetry, ["life_enabled"])
        if arm_enabled:
            self._module_view = "arm"
            return
        if auto_enabled:
            self._module_view = "auto"
            return
        if life_enabled:
            self._module_view = "life"
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
        elif "auto" in lowered or "lidar" in lowered:
            self._module_view = "auto"
        elif "arm" in lowered or "manip" in lowered:
            self._module_view = "arm"

    def _set_module_view_from_numeric(self, num_value: int) -> None:
        mapping = {1: "life", 2: "auto", 3: "arm"}
        self._module_view = mapping.get(num_value, self._module_view)

    def _update_module_text(self):
        if not getattr(self, "module_text", None):
            return

        module_key = self._get_active_module_view()
        module_label = self._get_module_view_label(module_key)

        if getattr(self, "module_frame", None):
            try:
                self.module_frame.config(text=f"{module_label} Module")
            except Exception:
                pass

        # "Nothing" state — no heartbeats ever received
        if module_key == "nothing":
            new_data_content = ""
            freshness_text = ""
        else:
            td_copy = self._snapshot_telemetry()
            if not td_copy:
                new_data_content = ""
                freshness_text = ""
            else:
                received_at = td_copy.get("_received_at")
                freshness_text = self._format_telemetry_freshness(received_at)

                filtered = filter_telemetry_for_module(td_copy, module_key)
                filtered = {
                    key: value
                    for key, value in filtered.items()
                    if not (isinstance(key, str) and key.startswith("_"))
                }

                if not filtered:
                    new_data_content = (
                        f"{module_label} Data:\n\n"
                        "Waiting for module data…\n"
                    )
                else:
                    lines = [f"{module_label} Data:"]
                    for key, value in filtered.items():
                        lines.append(f"{key}: {value}")
                    new_data_content = "\n".join(lines) + "\n"

        # Compare only data values (not freshness timestamp) to decide
        # whether a full rewrite is needed, preventing visible flickering
        # from delete-then-insert on every cycle.
        last_data = getattr(self, "_last_module_data_content", None)
        if new_data_content != last_data:
            self._last_module_data_content = new_data_content
            # Build full content with freshness for display
            if freshness_text:
                display_content = new_data_content.replace(
                    f"{module_label} Data:",
                    f"{module_label} Data ({freshness_text}):",
                    1,
                )
            else:
                display_content = new_data_content
            self.module_text.config(state="normal")
            self.module_text.delete("1.0", tk.END)
            self.module_text.insert(tk.END, display_content)
            self.module_text.config(state="disabled")
        elif freshness_text:
            # Data unchanged – only update the freshness text in the first line
            # to avoid a full rewrite.
            try:
                first_line = self.module_text.get("1.0", "1.end")
                # Replace the parenthetical freshness in the first line
                header_prefix = f"{module_label} Data ("
                if header_prefix in first_line:
                    new_first_line = f"{module_label} Data ({freshness_text}):"
                    self.module_text.config(state="normal")
                    self.module_text.delete("1.0", "1.end")
                    self.module_text.insert("1.0", new_first_line)
                    self.module_text.config(state="disabled")
            except Exception:
                pass

    def _format_telemetry_freshness(self, received_at: Any) -> str:
        if not isinstance(received_at, (int, float)):
            return "last packet unknown"

        now = time.time()
        age_seconds = max(0.0, now - float(received_at))
        timestamp_text = time.strftime("%H:%M:%S", time.localtime(float(received_at)))
        if age_seconds < 1.0:
            return f"last packet {timestamp_text} (live)"
        return f"last packet {timestamp_text} ({age_seconds:.1f}s ago)"

    # ------------------------------------------------------------------
    # Controller text display
    # ------------------------------------------------------------------

    def _update_controller_text(self):
        if not getattr(self, "controller_text", None):
            return

        scroll_pos = self._get_text_scroll_pos(self.controller_text)
        self.controller_text.config(state="normal")
        self.controller_text.delete(1.0, tk.END)

        controllers_copy, controller_values_copy, nested_values = (
            self._snapshot_controller_state()
        )

        has_any_input = False

        if controllers_copy:
            has_any_input = True
            for controller_id, data in controllers_copy.items():
                self._insert_controller_info(
                    controller_id, data, controller_values_copy, nested_values
                )

        # Keyboard state
        with self._controller_lock:
            kb_connected = self._keyboard_connected
            kb_state = self._keyboard_state.copy() if self._keyboard_state else {}

        if kb_connected and kb_state:
            has_any_input = True
            self._insert_keyboard_state(kb_state)

        if not has_any_input:
            self.controller_text.insert(tk.END, "No input devices connected\n")

        self.controller_text.config(state="disabled")
        self._restore_text_scroll_pos(self.controller_text, scroll_pos)

    def _snapshot_controller_state(
        self,
    ) -> tuple[Dict[int, Dict[str, Any]], Dict[str, Any], bool]:
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

    def _insert_controller_info(
        self, _controller_id, data, controller_values_copy, nested_values
    ):
        controller_name = data.get("name", "Unknown")
        self.controller_text.insert(tk.END, f"{controller_name}:\n")
        self.controller_text.insert(tk.END, f"  GUID: {data.get('guid', 'Unknown')}\n")

        resolved_values = self._resolve_controller_values_for_display(
            controller_name, data, controller_values_copy, nested_values
        )
        if resolved_values:
            self._insert_controller_values(resolved_values)
        self.controller_text.insert(tk.END, "\n")

    _KB_STATE_LABELS = {0: "-", 1: "PRESS", 2: "HOLD", 3: "REL"}

    def _insert_keyboard_state(self, kb_state: Dict[str, int]) -> None:
        from xbee.controller.keyboard import KeyboardInput

        bindings = KeyboardInput.get_key_bindings()  # signal -> key letter
        self.controller_text.insert(tk.END, "Keyboard (Life Detection): Connected\n")
        for sig, state in kb_state.items():
            label = self._KB_STATE_LABELS.get(state, str(state))
            key = bindings.get(sig, "?").upper()
            self.controller_text.insert(tk.END, f"  [{key}] {sig}: {label}\n")
        self.controller_text.insert(tk.END, "\n")

    def _resolve_controller_values_for_display(
        self, controller_name, data, controller_values_copy, nested_values
    ):
        if not nested_values:
            return controller_values_copy or None

        return (
            self._match_by_type(data, controller_values_copy)
            or self._match_by_detection(controller_name, controller_values_copy)
            or self._match_by_fuzzy_name(controller_name, controller_values_copy)
        )

    def _match_by_type(self, data, controller_values_copy):
        resolved_type = data.get("type")
        if not isinstance(resolved_type, str):
            return None
        for ctype in controller_values_copy:
            if isinstance(ctype, str) and ctype.lower() == resolved_type.lower():
                return controller_values_copy[ctype]
        return None

    def _match_by_detection(self, controller_name, controller_values_copy):
        detected = detect_controller_type(controller_name)
        if detected and detected in controller_values_copy:
            return controller_values_copy[detected]
        return None

    def _match_by_fuzzy_name(self, controller_name, controller_values_copy):
        if not controller_values_copy:
            return None
        name_lower = controller_name.lower()
        for ctype in controller_values_copy:
            ctype_lower = ctype.lower()
            if ctype_lower in name_lower or name_lower in ctype_lower:
                return controller_values_copy[ctype]
        return None

    def _insert_controller_values(self, controller_values_copy: Dict[str, Any]):
        self.controller_text.insert(tk.END, "  Current Values:\n")
        for key, value in controller_values_copy.items():
            if not isinstance(key, str):
                continue
            if isinstance(value, bytes):
                try:
                    value = int.from_bytes(value, "big") if value else 0
                except (ValueError, TypeError) as e:
                    logger.warning("Failed to convert bytes value for %s: %s", key, e)
                    value = "<invalid>"
            self.controller_text.insert(tk.END, f"    {key}: {value}\n")

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


__all__ = ["TkinterDisplay"]
