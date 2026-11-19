# NEED TO TEST STILL, i just want to get this stuff committed, im tired


# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : simulated_input_devices.py
# purpose       : synthetic Xbox/N64/SpaceMouse/keyboard inputs, the
#                 on-screen panel, and the local UDP control channel
# ------------------------------------------------------------------
"""Simulated basestation inputs (--sim-inputs).

The real readers in gamepads.py / spacemouse.py / keyboard.py talk to
evdev/HID devices. This module provides drop-in replacements with the
same small API, an on-screen tkinter panel to drive them, and a local
UDP JSON channel so the Gazebo Sim Inputs panel can drive the same
objects (keeping protocol encoding in one place).

Enable with ``python -m basestation --sim-inputs`` (or
``BASESTATION_SIM_INPUTS=1``). The radio link itself is already
simulated over UDP by comms.Link when no XBee is present.
"""

import json
import logging
import os
import socket
import threading
from math import floor

from basestation.gamepads import (AXIS_MAX, AXIS_MIN, DEADBAND, N64, NEUTRAL,
                                  XBOX, XBOX_STICKS, _defaults)
from basestation.keyboard import (ARM_KEY_MAP, ARM_NUMBER_MAP, LIFE_KEYS,
                                  Keyboard)
from basestation.keyboard import LIFE_SIGNALS
from basestation.protocol import CONSTANTS, MSG
from basestation.spacemouse import SpaceMouse

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:  # headless machine
    tk = None
    ttk = None

log = logging.getLogger(__name__)

SPACEMOUSE_AXES = CONSTANTS.SPACEMOUSE.ALL_AXES

# Keyboard key label -> protocol signal, for highlighting mapped keycaps.
KEYBOARD_LABELS = {label.upper(): signal
                   for signal, label in LIFE_KEYS.items()}

# Arm key label -> semantic action, from invKin202627 bindings.
ARM_KEYBOARD_LABELS = {code.removeprefix("KEY_").title(): action
                       for code, action in ARM_KEY_MAP.items()}
ARM_NUMBER_KEYS = {code.removeprefix("KEY_"): index
                   for code, index in ARM_NUMBER_MAP.items()
                   if code in ("KEY_1", "KEY_2", "KEY_3",
                               "KEY_4", "KEY_5")}

# On-screen nav keys that synthesize SpaceMouse axes for jogging.
# Up/Down are gripper actions and come from ARM_KEYBOARD_LABELS.
ARM_JOG_LABELS = {
    "Left": ("rz", 1),
    "Right": ("rz", -1),
    "PgUp": ("rx", 1),
    "PgDn": ("rx", -1),
}


def _clamp(value, low, high):
    return max(low, min(high, value))


class SimGamepads:
    """Gamepads-compatible object whose state comes from the GUI."""

    def __init__(self):
        self._lock = threading.Lock()
        self.states = {
            XBOX: _defaults(MSG.XBOX_ID),
            N64: _defaults(MSG.N64_ID),
        }
        self.devices = {
            "sim-xbox": {"name": "Simulated Xbox Controller", "type": XBOX},
            "sim-n64": {"name": "Simulated N64 Controller", "type": N64},
        }
        self.n64_enabled = False
        self.drive_speed = CONSTANTS.DRIVE_SPEED.DEFAULT
        self.reverse_mode = False
        self.auto_state = CONSTANTS.AUTO_STATE.MIN
        self._stick_values = {signal: 0.0 for signal in XBOX_STICKS.values()}

    # Gamepads API -----------------------------------------------------

    def snapshot(self):
        with self._lock:
            states = {
                name: dict(values) for name, values in self.states.items()
            }
            devices = dict(self.devices)
            if not self.n64_enabled:
                devices.pop("sim-n64", None)
                states[N64] = _defaults(MSG.N64_ID)
            return states, devices

    def set_n64_enabled(self, enabled):
        with self._lock:
            self.n64_enabled = bool(enabled)
            if not self.n64_enabled:
                self.states[N64] = _defaults(MSG.N64_ID)

    def stop(self):
        pass

    # UI API -----------------------------------------------------------

    def set_stick(self, signal, value):
        """Set a normalized (-1..1) stick value."""
        value = _clamp(float(value), -1.0, 1.0)
        if abs(value) < DEADBAND:
            value = 0.0
        with self._lock:
            self._stick_values[signal] = value
            self._recalc_sticks_locked()

    def set_button(self, signal, pressed):
        pressed = bool(pressed)
        with self._lock:
            self.states[XBOX][signal] = pressed
        if pressed and signal == CONSTANTS.XBOX.BUTTON.LEFT_BUMPER_STR:
            self.adjust_auto_state(-1)
        elif pressed and signal == CONSTANTS.XBOX.BUTTON.RIGHT_BUMPER_STR:
            self.adjust_auto_state(1)

    def set_trigger(self, signal, pressed):
        with self._lock:
            self.states[XBOX][signal] = bool(pressed)

    def set_n64_button(self, signal, pressed):
        with self._lock:
            if not self.n64_enabled:
                return
            self.states[N64][signal] = bool(pressed)

    def set_reverse(self, reverse):
        with self._lock:
            self.reverse_mode = bool(reverse)
            self._recalc_sticks_locked()

    def set_drive_speed(self, speed):
        with self._lock:
            self.drive_speed = int(_clamp(
                speed, CONSTANTS.DRIVE_SPEED.MIN, CONSTANTS.DRIVE_SPEED.MAX))
            self._recalc_sticks_locked()

    def set_auto_state(self, state):
        with self._lock:
            self.auto_state = int(_clamp(
                state, CONSTANTS.AUTO_STATE.MIN, CONSTANTS.AUTO_STATE.MAX))

    def adjust_auto_state(self, delta):
        with self._lock:
            self.auto_state = int(_clamp(
                self.auto_state + delta,
                CONSTANTS.AUTO_STATE.MIN, CONSTANTS.AUTO_STATE.MAX))

    def _recalc_sticks_locked(self):
        multiplier = self.drive_speed / 100
        if self.reverse_mode:
            multiplier = -multiplier
        for signal, value in self._stick_values.items():
            converted = floor(multiplier * value * 100 + NEUTRAL)
            self.states[XBOX][signal] = int(_clamp(
                converted, AXIS_MIN, AXIS_MAX))


class SimSpaceMouse:
    """SpaceMouse-compatible object driven by sliders."""

    def __init__(self):
        self._lock = threading.Lock()
        self._state = dict.fromkeys(SPACEMOUSE_AXES, 0) | {"buttons": 0}

    # SpaceMouse API ---------------------------------------------------

    def start(self):
        pass

    def stop(self):
        pass

    def is_connected(self):
        return True

    def get_state(self):
        with self._lock:
            return dict(self._state)

    # UI API -----------------------------------------------------------

    def set_axis(self, name, value):
        if name not in SPACEMOUSE_AXES:
            return
        with self._lock:
            self._state[name] = int(_clamp(value, -32768, 32767))

    def set_buttons(self, buttons):
        with self._lock:
            self._state["buttons"] = int(_clamp(buttons, 0, 65535))

    def zero(self):
        with self._lock:
            self._state = dict.fromkeys(SPACEMOUSE_AXES, 0) | {"buttons": 0}


class SimKeyboard(Keyboard):
    """Keyboard-compatible object whose keys are GUI buttons."""

    def __init__(self):
        super().__init__(on_disconnect=None)

    def start(self):
        pass  # no evdev reader

    def stop(self):
        pass

    def is_connected(self):
        return True

    def press(self, signal):
        with self._lock:
            self._tk_active = True
            self._press_life(signal)

    def release(self, signal):
        with self._lock:
            self._tk_active = True
            self._release_life(signal)


class SimulatorWindow:
    """Tk Toplevel with controls for every simulated device."""

    def __init__(self, root, gamepads, spacemouse, keyboard, parent=None):
        self.gamepads = gamepads
        self.spacemouse = spacemouse
        self.keyboard = keyboard
        self._mode = "nothing"
        self._xbox_vars = {}
        self._n64_vars = {}
        self._sm_scales = {}

        if parent is not None:
            self.window = parent
        else:
            self.window = tk.Toplevel(root)
            self.window.title("Simulated Input Devices")
            self.window.geometry("900x560")
        self.keyboard.bind_tkinter(self.window)

        options = ttk.Frame(self.window, padding=(8, 8, 8, 0))
        options.pack(fill="x")
        self._n64_var = tk.BooleanVar(
            value=getattr(gamepads, "n64_enabled", False))
        ttk.Checkbutton(
            options, text="Enable simulated N64", variable=self._n64_var,
            command=self._toggle_n64).pack(side="left")

        notebook = ttk.Notebook(self.window)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)
        self._notebook = notebook
        self._xbox_tab = self._build_xbox(notebook)
        notebook.add(self._xbox_tab, text="Xbox")
        self._n64_tab = self._build_n64(notebook)
        notebook.add(self._n64_tab, text="N64")
        if hasattr(spacemouse, "set_axis"):
            notebook.add(self._build_spacemouse(notebook), text="SpaceMouse")
        else:
            real = ttk.Frame(notebook, padding=8)
            ttk.Label(
                real,
                text="Using the physical SpaceMouse over HID.\n"
                     "Move the puck to send axes; press its buttons to "
                     "home / toggle joint drive.",
            ).pack(anchor="w")
            notebook.add(real, text="SpaceMouse")
        self._keyboard_tab = self._build_keyboard(notebook)
        notebook.add(self._keyboard_tab, text="Keyboard")
        self._apply_n64_state()
        self._apply_mode()

    # mode -------------------------------------------------------------

    def _toggle_n64(self):
        enabled = self._n64_var.get()
        if hasattr(self.gamepads, "set_n64_enabled"):
            self.gamepads.set_n64_enabled(enabled)
        self._apply_n64_state()

    def _apply_n64_state(self):
        enabled = getattr(self.gamepads, "n64_enabled", self._n64_var.get())
        state = "normal" if enabled else "disabled"
        try:
            self._notebook.tab(self._n64_tab, state=state)
        except tk.TclError:
            return
        if state == "disabled" and \
                self._notebook.select() == str(self._n64_tab):
            self._notebook.select(self._xbox_tab)

    def set_mode(self, mode):
        """Show keyboard settings for the selected mode."""
        self._mode = mode
        self.keyboard.set_mode(mode)
        self._apply_mode()

    def _apply_mode(self):
        state = "normal" if self._mode in ("life", "arm") else "disabled"
        try:
            self._notebook.tab(self._keyboard_tab, state=state)
        except tk.TclError:
            return
        if state == "disabled" and \
                self._notebook.select() == str(self._keyboard_tab):
            self._notebook.select(self._xbox_tab)
        self._refresh_keyboard_bindings()

    # helpers ----------------------------------------------------------

    @staticmethod
    def _scale(parent, label, low, high, command, resolution=0.05):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=8).pack(side="left")
        scale = tk.Scale(row, from_=low, to=high, orient="horizontal",
                         resolution=resolution, length=360, command=command)
        scale.set(0)
        scale.pack(side="left", fill="x", expand=True)
        return scale

    @staticmethod
    def _grid_scale(parent, label, low, high, command, row, column,
                    resolution=0.05, length=140):
        """One gridded label-over-slider cell."""
        cell = ttk.Frame(parent)
        cell.grid(row=row, column=column, sticky="ew", padx=4, pady=3)
        cell.columnconfigure(0, weight=1)
        ttk.Label(cell, text=label, anchor="center").grid(
            row=0, column=0, sticky="ew")
        scale = tk.Scale(
            cell, from_=low, to=high, orient="horizontal",
            resolution=resolution, length=length, command=command)
        scale.set(0)
        scale.grid(row=1, column=0, sticky="ew")
        return scale

    def _checkbutton(self, parent, text, command, store=None, key=None):
        var = tk.BooleanVar(value=False)
        if store is not None:
            store[key] = var
        ttk.Checkbutton(parent, text=text, variable=var, command=command).pack(
            side="left", padx=2)
        return var

    # Xbox -------------------------------------------------------------

    def _build_xbox(self, parent):
        frame = ttk.Frame(parent, padding=8)
        sticks = ttk.LabelFrame(frame, text="Sticks", padding=6)
        sticks.pack(fill="x")
        self._scale(sticks, "Left Y",
                    -1.0, 1.0, lambda v: self.gamepads.set_stick("AXIS_LY", v))
        self._scale(sticks, "Right Y",
                    -1.0, 1.0, lambda v: self.gamepads.set_stick("AXIS_RY", v))

        buttons = ttk.LabelFrame(frame, text="Buttons / triggers", padding=6)
        buttons.pack(fill="x", pady=(8, 0))
        for signal, label in (("A", "A"), ("B", "B"), ("X", "X"), ("Y", "Y"),
                              ("LEFT_BUMPER", "LB"), ("RIGHT_BUMPER", "RB")):
            self._checkbutton(
                buttons, label,
                lambda s=signal, v=None: self.gamepads.set_button(
                    s, self._xbox_vars[s].get()),
                self._xbox_vars, signal)
        for signal, label in (("AXIS_LT", "LT"), ("AXIS_RT", "RT")):
            self._checkbutton(
                buttons, label,
                lambda s=signal: self.gamepads.set_trigger(
                    s, self._xbox_vars[s].get()),
                self._xbox_vars, signal)

        modes = ttk.LabelFrame(frame, text="Drive mode", padding=6)
        modes.pack(fill="x", pady=(8, 0))
        reverse = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            modes, text="Reverse", variable=reverse,
            command=lambda: self.gamepads.set_reverse(reverse.get())
        ).grid(row=0, column=0, sticky="w", padx=4)
        ttk.Label(modes, text="Speed %").grid(row=0, column=1, sticky="e")
        speed = tk.Spinbox(modes, from_=0, to=100, increment=25, width=6,
                           command=lambda: self.gamepads.set_drive_speed(
                               int(float(speed.get()))))
        speed.delete(0, "end")
        speed.insert(0, str(self.gamepads.drive_speed))
        speed.grid(row=0, column=2, padx=4)
        ttk.Label(modes, text="Auto state").grid(row=1, column=0, sticky="w",
                                                 padx=4, pady=(6, 0))
        auto = tk.Spinbox(modes, from_=CONSTANTS.AUTO_STATE.MIN,
                          to=CONSTANTS.AUTO_STATE.MAX, width=6,
                          command=lambda: self.gamepads.set_auto_state(
                              int(float(auto.get()))))
        auto.delete(0, "end")
        auto.insert(0, str(self.gamepads.auto_state))
        auto.grid(row=1, column=2, padx=4, pady=(6, 0), sticky="w")
        return frame

    # N64 --------------------------------------------------------------

    def _build_n64(self, parent):
        frame = ttk.Frame(parent, padding=8)
        groups = (
            ("Face", ("A", "B")),
            ("Shoulders", ("L", "R", "Z")),
            ("C buttons", ("C_UP", "C_DOWN", "C_LEFT", "C_RIGHT")),
            ("D-pad", ("DP_UP", "DP_DOWN", "DP_LEFT", "DP_RIGHT")),
        )
        for title, signals in groups:
            box = ttk.LabelFrame(frame, text=title, padding=6)
            box.pack(fill="x", pady=4)
            for signal in signals:
                self._checkbutton(
                    box, signal,
                    lambda s=signal: self.gamepads.set_n64_button(
                        s, self._n64_vars[s].get()),
                    self._n64_vars, signal)
        return frame

    # SpaceMouse -------------------------------------------------------

    def _build_spacemouse(self, parent):
        frame = ttk.Frame(parent, padding=8)
        axes = ttk.LabelFrame(frame, text="6DOF axes (raw counts)", padding=6)
        axes.pack(fill="x")
        for column in range(3):
            axes.columnconfigure(column, weight=1)
        # 2x3 grid: translation (x, y, z) on top, rotation (rx, ry, rz) below.
        for index, axis in enumerate(SPACEMOUSE_AXES):
            row, column = divmod(index, 3)
            self._sm_scales[axis] = self._grid_scale(
                axes, axis, -1000, 1000,
                lambda v, a=axis: self.spacemouse.set_axis(a, int(float(v))),
                row, column, resolution=10)
        buttons = ttk.LabelFrame(frame, text="Buttons", padding=6)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Label(buttons, text="Bitmask (0-65535)").pack(side="left")
        mask = tk.Spinbox(buttons, from_=0, to=65535, width=8,
                          command=lambda: self.spacemouse.set_buttons(
                              int(float(mask.get()))))
        mask.delete(0, "end")
        mask.insert(0, "0")
        mask.pack(side="left", padx=6)
        ttk.Button(buttons, text="Zero all",
                   command=self._zero_spacemouse).pack(side="left", padx=6)
        return frame

    def _zero_spacemouse(self):
        self.spacemouse.zero()
        for scale in self._sm_scales.values():
            scale.set(0)

    # Keyboard ---------------------------------------------------------

    @staticmethod
    def _key_button(parent, label):
        """One neutral keycap; _refresh_keyboard_bindings() activates it."""
        return tk.Button(parent, text=label, takefocus=0, bd=2,
                         relief="raised", font=("TkDefaultFont", 8),
                         padx=1, pady=1, state="disabled", bg="#f2f2f2",
                         disabledforeground="#8a8a8a")

    def _add_key_row(self, parent, row, keys, mapped=True):
        """Lay out one row of (label, units[, rowspan]) keycaps."""
        column = 0
        for key in keys:
            label, units = key[0], key[1]
            rowspan = key[2] if len(key) > 2 else 1
            if label:
                button = self._key_button(parent, label)
                self._key_buttons.setdefault(label, []).append(button)
                button.grid(row=row, column=column, columnspan=units,
                            rowspan=rowspan, sticky="nsew", padx=1, pady=1)
            column += units

    @staticmethod
    def _clear_key_button(button):
        for sequence in ("<ButtonPress-1>", "<ButtonRelease-1>",
                         "<Shift-ButtonPress-1>",
                         "<Shift-ButtonRelease-1>"):
            button.unbind(sequence)
        button.configure(state="disabled", bg="#f2f2f2",
                         disabledforeground="#8a8a8a")

    @staticmethod
    def _enable_key_button(button):
        button.configure(state="normal", bg="#dcecff",
                         activebackground="#b8d8ff", fg="#083b66")

    def _refresh_keyboard_bindings(self):
        """Highlight and bind keys for the active mode."""
        if not hasattr(self, "_key_buttons"):
            return
        for buttons in self._key_buttons.values():
            for button in buttons:
                self._clear_key_button(button)

        if self._mode == "life":
            self._keyboard_hint.config(
                text="Blue keys send life-detection commands; grey keys "
                     "are visual placeholders.")
            for label, signal in KEYBOARD_LABELS.items():
                for button in self._key_buttons.get(label, ()):
                    self._enable_key_button(button)
                    button.bind(
                        "<ButtonPress-1>",
                        lambda _event, s=signal: self.keyboard.press(s))
                    button.bind(
                        "<ButtonRelease-1>",
                        lambda _event, s=signal: self.keyboard.release(s))
        elif self._mode == "arm":
            self._keyboard_hint.config(
                text="Blue keys send arm commands. "
                     "F flip, H home, I position, J joint, V PnP, P planar, "
                     "G guide, Q pos lock, O ori lock, L locks all joints, "
                     "R rest (future), S solenoid, Z zenith. Shift+1-5 homes "
                     "one joint; 1-5 toggles its lock. Hold Left/Right to "
                     "jog the base, PgUp/PgDn for the elbow; Up/Down drive "
                     "the gripper.")
            for label, action in ARM_KEYBOARD_LABELS.items():
                for button in self._key_buttons.get(label, ()):
                    self._enable_key_button(button)
                    button.bind(
                        "<ButtonPress-1>",
                        lambda _event, a=action: self.keyboard.press_arm(a))
                    button.bind(
                        "<ButtonRelease-1>",
                        lambda _event, a=action: self.keyboard.release_arm(a))
            for label, index in ARM_NUMBER_KEYS.items():
                for button in self._key_buttons.get(label, ()):
                    self._enable_key_button(button)
                    button.bind(
                        "<ButtonPress-1>",
                        lambda _event, i=index: self.keyboard.press_arm(
                            f"toggle_joint_lock:{i}"))
                    button.bind(
                        "<ButtonRelease-1>",
                        lambda _event, i=index: self.keyboard.release_arm(
                            f"toggle_joint_lock:{i}"))
                    button.bind(
                        "<Shift-ButtonPress-1>",
                        lambda _event, i=index: self.keyboard.press_arm(
                            f"home_joint:{i}"))
                    button.bind(
                        "<Shift-ButtonRelease-1>",
                        lambda _event, i=index: self.keyboard.release_arm(
                            f"home_joint:{i}"))
            for label, (axis, sign) in ARM_JOG_LABELS.items():
                for button in self._key_buttons.get(label, ()):
                    self._enable_key_button(button)
                    button.bind(
                        "<ButtonPress-1>",
                        lambda _event, a=axis, s=sign:
                            self.keyboard.press_jog(a, s))
                    button.bind(
                        "<ButtonRelease-1>",
                        lambda _event, a=axis, s=sign:
                            self.keyboard.release_jog(a, s))
        else:
            self._keyboard_hint.config(
                text="Select Arm or Life Detection mode to use the keyboard.")
        # Force a redraw so keycap labels appear when the tab is first shown.
        self.window.update_idletasks()

    def _build_keyboard(self, parent):
        frame = ttk.Frame(parent, padding=8)
        self._key_buttons = {}

        header = ttk.Frame(frame)
        header.pack(fill="x", pady=(0, 6))
        self._keyboard_hint = ttk.Label(header, text="")
        self._keyboard_hint.pack(side="left")
        ttk.Button(header, text="Release all",
                   command=self._release_all_keys).pack(side="right")

        body = ttk.Frame(frame)
        body.pack(fill="both", expand=True)
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        main = ttk.Frame(body)
        main.grid(row=0, column=0, sticky="nsew")
        for column in range(64):
            main.grid_columnconfigure(column, weight=1, uniform="mainkey")
        for row in range(6):
            main.grid_rowconfigure(row, weight=1)

        self._add_key_row(main, 0, (
            [("Esc", 4)]
            + [(f"F{n}", 4) for n in range(1, 13)]
            + [("PrtSc", 4), ("ScrLk", 4), ("Pause", 4)]
        ), mapped=False)

        self._add_key_row(main, 1, (
            [("`", 4)]
            + [(str(d), 4) for d in range(1, 10)]
            + [("0", 4), ("-", 4), ("=", 4), ("Backspace", 8)]
        ))
        self._add_key_row(main, 2, (
            [("Tab", 6)]
            + [(letter, 4) for letter in "QWERTYUIOP"]
            + [("[", 4), ("]", 4), ("\\", 6)]
        ))
        self._add_key_row(main, 3, (
            [("Caps", 7)]
            + [(letter, 4) for letter in "ASDFGHJKL"]
            + [(";", 4), ("'", 4), ("Enter", 9)]
        ))
        self._add_key_row(main, 4, (
            [("Shift", 8)]
            + [(letter, 4) for letter in "ZXCVBNM"]
            + [(",", 4), (".", 4), ("/", 4), ("Shift", 12)]
        ))
        self._add_key_row(main, 5, (
            [("Ctrl", 5), ("Win", 5), ("Alt", 5), ("Space", 25),
             ("Alt", 5), ("Win", 5), ("Menu", 5), ("Ctrl", 5)]
        ))

        nav = ttk.Frame(body)
        nav.grid(row=0, column=1, sticky="ns", padx=(12, 0))
        for column in range(3):
            nav.grid_columnconfigure(column, weight=1, uniform="navkey",
                                     minsize=36)
        for row in range(4):
            nav.grid_rowconfigure(row, weight=1)
        for row, keys in enumerate((
            [("Ins", 1), ("Home", 1), ("PgUp", 1)],
            [("Del", 1), ("End", 1), ("PgDn", 1)],
            [("", 1), ("Up", 1), ("", 1)],
            [("Left", 1), ("Down", 1), ("Right", 1)],
        )):
            self._add_key_row(nav, row, keys, mapped=False)

        numpad = ttk.Frame(body)
        numpad.grid(row=0, column=2, sticky="ns", padx=(12, 0))
        for column in range(4):
            numpad.grid_columnconfigure(column, weight=1, uniform="numpadkey",
                                        minsize=36)
        for row in range(5):
            numpad.grid_rowconfigure(row, weight=1)
        for row, keys in enumerate((
            [("NumLk", 1), ("/", 1), ("*", 1), ("-", 1)],
            [("7", 1), ("8", 1), ("9", 1), ("+", 1, 2)],
            [("4", 1), ("5", 1), ("6", 1)],
            [("1", 1), ("2", 1), ("3", 1), ("Enter", 1, 2)],
            [("0", 2), (".", 1)],
        )):
            self._add_key_row(numpad, row, keys, mapped=False)

        return frame

    def _release_all_keys(self):
        for signal in LIFE_SIGNALS:
            self.keyboard.release(signal)
        self.keyboard.release_all_arm()


# ---------------------------------------------------------------------------
# Local UDP control channel (used by the Gazebo Sim Inputs panel)
# ---------------------------------------------------------------------------

DEFAULT_PORT = 47813
HOST = "127.0.0.1"


class SimControlServer:
    """Receive JSON commands and apply them to a BaseStation."""

    def __init__(self, station, port=None):
        self.station = station
        self.port = int(port or os.environ.get(
            "BASESTATION_SIM_CONTROL_PORT", DEFAULT_PORT))
        self._stop = threading.Event()
        self._socket = None
        self._thread = None

    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((HOST, self.port))
        sock.settimeout(0.2)
        self._socket = sock
        self._thread = threading.Thread(
            target=self._run, name="sim-control", daemon=True)
        self._thread.start()
        log.info("Sim input control listening on udp://%s:%d",
                 HOST, self.port)

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def _run(self):
        while not self._stop.is_set():
            try:
                data, address = self._socket.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                command = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                log.warning("Ignoring malformed sim control packet")
                continue
            try:
                self._apply(command)
                self._socket.sendto(b'{"ok":true}', address)
            except Exception:
                log.exception("Sim control command failed: %s", command)

    def _apply(self, command):
        station = self.station
        gamepads = station.gamepads
        spacemouse = station.spacemouse
        keyboard = station.keyboard
        action = command.get("cmd")

        if action == "xbox_stick":
            gamepads.set_stick(command["signal"], command["value"])
        elif action == "xbox_button":
            gamepads.set_button(
                command["signal"], command.get("pressed", False))
        elif action == "xbox_trigger":
            gamepads.set_trigger(
                command["signal"], command.get("pressed", False))
        elif action == "drive_speed":
            gamepads.set_drive_speed(command["value"])
        elif action == "reverse":
            gamepads.set_reverse(command.get("value", False))
        elif action == "auto_state":
            gamepads.set_auto_state(command["value"])
        elif action == "n64_enabled":
            gamepads.set_n64_enabled(command.get("value", False))
        elif action == "n64_button":
            gamepads.set_n64_button(
                command["signal"], command.get("pressed", False))
        elif action == "spacemouse_axis":
            if hasattr(spacemouse, "set_axis"):
                spacemouse.set_axis(command["name"], command["value"])
        elif action == "spacemouse_buttons":
            if hasattr(spacemouse, "set_buttons"):
                spacemouse.set_buttons(command["value"])
        elif action == "spacemouse_zero":
            if hasattr(spacemouse, "zero"):
                spacemouse.zero()
        elif action == "mode":
            station.set_mode(command["value"])
        elif action == "key_press":
            keyboard.press(command["signal"])
        elif action == "key_release":
            keyboard.release(command["signal"])
        elif action == "arm_press":
            keyboard.press_arm(command["action"])
        elif action == "arm_release":
            keyboard.release_arm(command["action"])
        elif action == "release_all":
            for signal in LIFE_SIGNALS:
                keyboard.release(signal)
            keyboard.release_all_arm()
        elif action == "quit":
            station.request_quit()
        elif action == "ping":
            pass
        else:
            log.warning("Unknown sim control command: %s", action)


class SimulatedInputs:
    """All the fake input readers plus their control server and panel.

    ``BaseStation`` treats this as one object: ``devices`` covers the
    readers, ``start_control``/``attach``/``stop`` cover the simulation-only
    extras. Real-device setup never touches this class.
    """

    def __init__(self, real_spacemouse: bool = False):
        self.gamepads = SimGamepads()
        self.keyboard = SimKeyboard()
        # Keep the other devices simulated but read the physical
        # SpaceMouse. Reconnect silently instead of quitting the whole
        # simulation when the puck is unplugged.
        if real_spacemouse:
            self.spacemouse = SpaceMouse(on_disconnect=None)
        else:
            self.spacemouse = SimSpaceMouse()
        self.control = None
        self.panel = None

    @property
    def devices(self):
        return self.gamepads, self.spacemouse, self.keyboard

    def start_control(self, station):
        """Serve the local UDP channel used by the Gazebo panel."""
        self.control = SimControlServer(station)
        try:
            self.control.start()
        except OSError as exc:
            log.warning("Sim input control unavailable: %s", exc)
            self.control = None

    def attach(self, station, display):
        """Add the on-screen controls to the display's Sim Inputs tab."""
        if display.sim_inputs_frame is None:
            return
        self.panel = SimulatorWindow(
            display.root, self.gamepads, self.spacemouse, self.keyboard,
            parent=display.sim_inputs_frame)
        display.add_mode_listener(self.panel.set_mode)
        station.add_mode_listener(self.panel.set_mode)

    def stop(self):
        if self.control is not None:
            self.control.stop()
            self.control = None
