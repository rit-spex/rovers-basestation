# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : gui.py
# purpose       : tkinter status display for the basestation, with a
#                 headless fallback for services and tests
# created on    : 7/12/2026 - Ryan
# last modified : 7/12/2026 - Ryan
# ------------------------------------------------------------------
"""Basestation display.

The control loop hands the display one snapshot dict per cycle via
update(); the GUI redraws from the latest snapshot on a 100 ms timer on
the tkinter main thread. Use create_display() to get the GUI, or the
headless fallback when XBEE_NO_GUI is set or tkinter is unavailable.
"""

import logging
import threading
import time

from basestation.keyboard import Keyboard
from basestation.protocol import MessageEncoder, env_flag

log = logging.getLogger(__name__)

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    tk = None

WINDOW_SIZE = "800x560"
SIDEBAR_WIDTH = 140
INDICATOR_SIZE = 30
RED, GREEN, BLUE = "#a51d2d", "#26a269", "#1c71d8"

# Which telemetry signals each module view shows, from the protocol itself
_MESSAGES = MessageEncoder().get_messages().values()
_SIGNALS = {m["name"]: set(m["values"]) for m in _MESSAGES}
MODULE_SIGNALS = {
    "life": _SIGNALS["life_detection"],
    "arm": _SIGNALS["arm_encoders"],
    "auto": _SIGNALS["drive_imu"] | _SIGNALS["control_mode"],
}
MODULE_LABELS = {"nothing": "Nothing", "life": "Life Detection",
                 "auto": "Autonomous", "arm": "Arm"}

KEY_STATE_LABELS = {0: "-", 1: "PRESS", 2: "HOLD", 3: "REL"}


def create_display(simulation: bool = False):
    """The tkinter display, or the headless one when GUI is unavailable."""
    if env_flag("XBEE_NO_GUI") or tk is None:
        log.info("Using headless display")
        return HeadlessDisplay()
    try:
        return Display(simulation)
    except Exception as exc:
        log.warning("GUI unavailable (%s) - using headless display", exc)
        return HeadlessDisplay()


class HeadlessDisplay:
    """No-op display for systemd services and tests."""

    root = None

    def update(self, snapshot: dict):
        pass

    def run(self, should_quit):
        while not should_quit():
            time.sleep(0.1)

    def quit(self):
        pass


class Display:
    """Tkinter GUI: mode/status sidebar, input devices, module telemetry."""

    def __init__(self, simulation: bool):
        self.simulation = simulation
        self._lock = threading.Lock()
        self._snapshot = {}
        self._module_view = "nothing"
        self._view_override = None  # dropdown selection in simulation mode

        self.root = tk.Tk()
        self.root.title("SPEX Rover Basestation Control")
        self.root.geometry(WINDOW_SIZE)
        self._build_ui()

    # ------------------------------------------------------------------
    # Display API (called from the control thread)
    # ------------------------------------------------------------------

    def update(self, snapshot: dict):
        with self._lock:
            self._snapshot = snapshot

    def run(self, should_quit):
        self.root.after(100, self._refresh)
        self.root.mainloop()

    def quit(self):
        try:
            self.root.after_idle(self.root.quit)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=8)
        main.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        if self.simulation:
            self._build_sim_banner(main)

        content = ttk.Frame(main)
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)
        self._build_sidebar(content)
        self._build_panels(content)

    def _build_sim_banner(self, parent):
        banner = tk.Frame(parent, background="#d22")
        banner.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        banner.columnconfigure(0, weight=1)
        tk.Label(banner, text="SIMULATION MODE", background="#d22",
                 foreground="white", font=("Arial", 16, "bold"), pady=12,
                 ).grid(row=0, column=0, sticky="w", padx=16)
        self._view_var = tk.StringVar(value=MODULE_LABELS["nothing"])
        dropdown = ttk.Combobox(banner, textvariable=self._view_var,
                                values=list(MODULE_LABELS.values()),
                                state="readonly", width=18)
        dropdown.grid(row=0, column=1, padx=12)
        dropdown.bind("<<ComboboxSelected>>", self._on_view_selected)

    def _build_sidebar(self, parent):
        sidebar = ttk.Frame(parent, padding=4, width=SIDEBAR_WIDTH)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)

        self._indicators = {}
        self._indicator_labels = {}
        row = 0
        for name, with_label in (("Creep Mode", False), ("Reverse", False),
                                 ("Auto Status", True), ("Auto Toggle", False),
                                 ("Arm Toggle", False), ("Rover Status", True),
                                 ("Life Toggle", False)):
            row = self._add_indicator(sidebar, row, name, with_label)

        self.comm_label = ttk.Label(sidebar, text="Comm:\n-", justify="left")
        self.comm_label.grid(row=row, column=0, sticky="w", pady=(6, 0))
        self.updates_label = ttk.Label(sidebar, text="Updates: 0")
        self.updates_label.grid(row=row + 1, column=0, sticky="w")

    def _add_indicator(self, parent, row, name, with_label):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, sticky="ew", pady=2)
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text=name, font=("Arial", 11, "bold")).grid(
            row=0, column=0, sticky="w")
        box = tk.Frame(frame, width=INDICATOR_SIZE, height=INDICATOR_SIZE,
                       background=RED, highlightthickness=1,
                       highlightbackground="#333")
        box.grid(row=0, column=1, sticky="e", padx=(8, 0))
        box.grid_propagate(False)
        self._indicators[name] = box
        if with_label:
            label = ttk.Label(frame, text="", font=("Arial", 9))
            label.grid(row=1, column=0, columnspan=2, sticky="w")
            self._indicator_labels[name] = label
        ttk.Separator(parent).grid(row=row + 1, column=0, sticky="ew", pady=4)
        return row + 2

    def _build_panels(self, parent):
        panels = ttk.Frame(parent)
        panels.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        panels.columnconfigure(0, weight=2)
        panels.columnconfigure(1, weight=4)
        panels.rowconfigure(0, weight=1)

        self.devices_text = self._text_panel(panels, "Input Devices", 0)
        self.module_frame, self.module_text = self._text_panel(
            panels, "Module Info", 1, return_frame=True)

    def _text_panel(self, parent, title, column, return_frame=False):
        frame = ttk.LabelFrame(parent, text=title, padding=8)
        frame.grid(row=0, column=column, sticky="nsew",
                   padx=(0, 8) if column == 0 else 0)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        text = tk.Text(frame, height=24, width=40, wrap="word", state="disabled")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        return (frame, text) if return_frame else text

    # ------------------------------------------------------------------
    # Redraw (tkinter main thread)
    # ------------------------------------------------------------------

    def _refresh(self):
        with self._lock:
            snap = self._snapshot
        if snap:
            try:
                self._draw_sidebar(snap)
                self._set_text(self.devices_text, self._devices_content(snap))
                self._draw_module_panel(snap.get("telemetry", {}))
            except Exception:
                log.exception("GUI refresh error")
        self.root.after(100, self._refresh)

    def _draw_sidebar(self, snap):
        telemetry = snap.get("telemetry", {})
        self._set_indicator("Creep Mode", snap.get("creep"))
        self._set_indicator("Reverse", snap.get("reverse"))

        auto_on = bool(telemetry.get("auto_enabled"))
        self._set_indicator("Auto Status", True, "#d22" if auto_on else BLUE)
        self._indicator_labels["Auto Status"].config(
            text="Autonomous" if auto_on else "Teleop")

        self._set_indicator("Auto Toggle", telemetry.get("auto_enabled"))
        self._set_indicator("Arm Toggle", telemetry.get("arm_enabled"))
        self._set_indicator("Life Toggle", telemetry.get("life_enabled"))

        if "rover_estop" in telemetry:
            estopped = bool(telemetry["rover_estop"])
            self._set_indicator("Rover Status", not estopped)
            self._indicator_labels["Rover Status"].config(
                text="ESTOPPED" if estopped else "OK")

        mode = " (SIMULATION)" if snap.get("simulation") else ""
        self.comm_label.config(text=f"Comm:\nConnected{mode}")
        self.updates_label.config(text=f"Updates: {snap.get('updates', 0)}")

    def _set_indicator(self, name, on, on_color=GREEN):
        self._indicators[name].configure(background=on_color if on else RED)

    def _devices_content(self, snap):
        lines = []
        states = snap.get("states", {})
        for info in snap.get("devices", {}).values():
            lines.append(f"{info['name']}:")
            for signal, value in states.get(info["type"], {}).items():
                lines.append(f"    {signal}: {value}")
            lines.append("")
        if snap.get("spacemouse") is not None:
            lines.append("SpaceMouse:")
            lines += [f"    {axis}: {value}"
                      for axis, value in snap["spacemouse"].items()]
            lines.append("")
        if snap.get("keyboard") is not None:  # shown only while connected (#25)
            lines.append("Keyboard (Life Detection):")
            for signal, state in snap["keyboard"].items():
                key = Keyboard.key_for(signal).upper()
                lines.append(f"    [{key}] {signal}: {KEY_STATE_LABELS[state]}")
            lines.append("")
        return "\n".join(lines) if lines else "No input devices connected\n"

    def _draw_module_panel(self, telemetry):
        view = self._pick_module_view(telemetry)
        label = MODULE_LABELS[view]
        self.module_frame.config(text=f"{label} Module")
        if view == "nothing":
            self._set_text(self.module_text, "")
            return
        rows = [f"{key}: {value}" for key, value in telemetry.items()
                if key in MODULE_SIGNALS[view]]
        body = "\n".join(rows) if rows else "Waiting for module data..."
        header = f"{label} Data ({self._freshness(telemetry)}):"
        self._set_text(self.module_text, f"{header}\n\n{body}\n")

    def _pick_module_view(self, telemetry):
        if self.simulation and self._view_override:
            return self._view_override
        # Follow whichever subsystem the rover reports as enabled
        for view, key in (("arm", "arm_enabled"), ("auto", "auto_enabled"),
                          ("life", "life_enabled")):
            if telemetry.get(key):
                self._module_view = view
                break
        return self._module_view

    def _on_view_selected(self, _event):
        selected = self._view_var.get()
        self._view_override = next(
            (key for key, label in MODULE_LABELS.items() if label == selected),
            None)

    @staticmethod
    def _freshness(telemetry):
        received_at = telemetry.get("_received_at")
        if not isinstance(received_at, (int, float)):
            return "no packets yet"
        age = max(0.0, time.time() - received_at)
        stamp = time.strftime("%H:%M:%S", time.localtime(received_at))
        return f"last packet {stamp} (live)" if age < 1.0 else \
               f"last packet {stamp} ({age:.1f}s ago)"

    def _set_text(self, widget, content):
        """Rewrite a text widget only when content changed, keeping scroll."""
        if getattr(widget, "_last_content", None) == content:
            return
        widget._last_content = content
        scroll = widget.yview()
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", content)
        widget.config(state="disabled")
        widget.yview_moveto(scroll[0])