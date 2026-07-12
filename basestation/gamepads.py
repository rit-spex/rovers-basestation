# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : gamepads.py
# purpose       : read Xbox and N64 gamepads and keep their current
#                 state ready for protocol encoding
# created on    : 7/12/2026 - Ryan
# last modified : 7/12/2026 - Ryan
# ------------------------------------------------------------------
"""Gamepad input via the ``inputs`` library.

Each connected gamepad gets a reader thread doing blocking reads. A monitor
thread rescans devices every half second so controllers plugged in after
startup are found (the ``inputs`` library only scans once at import).

State is stored under the protocol signal names (AXIS_LY, A, DP_UP, ...) so
it can be handed straight to the encoder.
"""

import logging
import os
import threading
from math import floor

from basestation.protocol import CONSTANTS, MSG, MessageEncoder, env_flag

try:
    import inputs
except Exception:
    inputs = None

log = logging.getLogger(__name__)

XBOX = CONSTANTS.XBOX.NAME
N64 = CONSTANTS.N64.NAME
SPACEMOUSE = "spacemouse"

# Raw evdev code -> protocol signal name
XBOX_BUTTONS = {
    "BTN_SOUTH": CONSTANTS.XBOX.BUTTON.A_STR,
    "BTN_EAST": CONSTANTS.XBOX.BUTTON.B_STR,
    "BTN_WEST": CONSTANTS.XBOX.BUTTON.X_STR,
    "BTN_NORTH": CONSTANTS.XBOX.BUTTON.Y_STR,
    "BTN_TL": CONSTANTS.XBOX.BUTTON.LEFT_BUMPER_STR,
    "BTN_TR": CONSTANTS.XBOX.BUTTON.RIGHT_BUMPER_STR,
}
N64_BUTTONS = {
    "BTN_SOUTH": CONSTANTS.N64.BUTTON.A_STR,
    "BTN_EAST": CONSTANTS.N64.BUTTON.B_STR,
    "BTN_NORTH": CONSTANTS.N64.BUTTON.C_UP_STR,
    "BTN_WEST": CONSTANTS.N64.BUTTON.C_LEFT_STR,
    "BTN_TL": CONSTANTS.N64.BUTTON.L_STR,
    "BTN_TR": CONSTANTS.N64.BUTTON.R_STR,
    "BTN_SELECT": CONSTANTS.N64.BUTTON.Z_STR,
    "BTN_MODE": CONSTANTS.N64.BUTTON.Z_STR,
}
XBOX_STICKS = {
    "ABS_Y": CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR,
    "ABS_RY": CONSTANTS.XBOX.JOYSTICK.AXIS_RY_STR,
}
XBOX_TRIGGERS = {
    "ABS_Z": CONSTANTS.XBOX.TRIGGER.AXIS_LT_STR,
    "ABS_LT": CONSTANTS.XBOX.TRIGGER.AXIS_LT_STR,
    "ABS_RZ": CONSTANTS.XBOX.TRIGGER.AXIS_RT_STR,
    "ABS_RT": CONSTANTS.XBOX.TRIGGER.AXIS_RT_STR,
}
DPAD_CODES = ("ABS_HAT0X", "ABS_HAT0Y", "BTN_DPAD_UP", "BTN_DPAD_DOWN",
              "BTN_DPAD_LEFT", "BTN_DPAD_RIGHT")

NEUTRAL = CONSTANTS.XBOX.JOYSTICK.NEUTRAL_INT
AXIS_MIN = CONSTANTS.XBOX.JOYSTICK.MIN_VALUE
AXIS_MAX = CONSTANTS.XBOX.JOYSTICK.MAX_VALUE
DEADBAND = CONSTANTS.TIMING.DEADBAND_THRESHOLD
CREEP_MULTIPLIER = CONSTANTS.CONTROLLER_MODES.CREEP_MULTIPLIER

# Raw trigger value above which the trigger counts as pressed.
# ponytail: assumes 0..255 trigger range; some pads report 0..1023, still
# fine for a boolean but revisit if a trigger ever needs analog values.
TRIGGER_PRESS_RAW = float(os.environ.get("XBEE_TRIGGER_THRESHOLD", "0.05")) * 255

_ENCODER = MessageEncoder()


def _defaults(message_id: int) -> dict:
    """Neutral state for a message, straight from protocol.yaml defaults."""
    signals = _ENCODER.get_messages()[message_id]["values"]
    return {name: signal.default_value for name, signal in signals.items()}


def detect_type(name: str):
    """Controller type from the OS device name, or None if unrecognized."""
    lower = (name or "").lower()
    if any(m in lower for m in ("spacemouse", "space mouse", "3dconnexion")):
        return SPACEMOUSE
    if "xbox" in lower or "x-box" in lower:
        return XBOX
    if any(m in lower for m in ("n64", "dinput", "directinput", "direct input")):
        return N64
    return None


class Gamepads:
    """Tracks connected gamepads, their input state, and drive mode flags.

    Mode controls (Xbox):
        hold SELECT + D-pad up/down  -> reverse mode on/off
        hold START  + D-pad up/down  -> creep mode on/off
        LEFT/RIGHT bumper press      -> autonomous state -1/+1
        HOME button                  -> quit
    """

    def __init__(self, on_quit=None, scan: bool = True):
        self._on_quit = on_quit or (lambda: None)
        self._lock = threading.Lock()
        self.states = {XBOX: _defaults(MSG.XBOX_ID), N64: _defaults(MSG.N64_ID)}
        self.devices = {}  # device key -> {"name": str, "type": str}
        self.creep_mode = env_flag("XBEE_DEFAULT_CREEP", default=True)
        self.reverse_mode = False
        self.auto_state = CONSTANTS.AUTO_STATE.MIN
        self._held = {"BTN_SELECT": False, "BTN_START": False}
        # ponytail: sticks assumed signed 16-bit; set XBEE_JOYSTICK_RAW_MODE=
        # unsigned for adapters that report 0..255 instead
        raw_mode = (os.environ.get("XBEE_JOYSTICK_RAW_MODE") or "").strip().lower()
        self._unsigned_sticks = raw_mode == "unsigned"
        self._stop = threading.Event()
        self._readers = {}  # device key -> reader thread

        if not scan:
            return
        if inputs is None:
            log.warning("inputs library unavailable - gamepads disabled")
            return
        threading.Thread(target=self._monitor, daemon=True,
                         name="gamepad-monitor").start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def snapshot(self):
        """Copies of (controller states, connected devices)."""
        with self._lock:
            states = {name: dict(values) for name, values in self.states.items()}
            return states, dict(self.devices)

    def stop(self):
        self._stop.set()

    # ------------------------------------------------------------------
    # Device management
    # ------------------------------------------------------------------

    def _monitor(self):
        while not self._stop.is_set():
            try:
                inputs.devices = inputs.DeviceManager()  # rescan for hotplug
                found = {}
                for device in inputs.devices.gamepads:
                    key = getattr(device, "device_path", None) or device.name
                    found[key] = device
                for key, device in found.items():
                    reader = self._readers.get(key)
                    if reader is None or not reader.is_alive():
                        self._add_device(key, device)
                for key in list(self.devices):
                    if key not in found:
                        self._remove_device(key)
            except Exception:
                log.exception("Gamepad monitor error")
            self._stop.wait(0.5)

    def _add_device(self, key, device):
        ctype = detect_type(device.name)
        if ctype == SPACEMOUSE:
            return  # handled by the dedicated HID reader (spacemouse.py)
        if ctype is None:
            log.warning("Unknown controller '%s'; treating as xbox", device.name)
            ctype = XBOX
        with self._lock:
            self.devices[key] = {"name": device.name, "type": ctype}
        reader = threading.Thread(target=self._reader, args=(device, key, ctype),
                                  daemon=True, name=f"gamepad-{ctype}")
        self._readers[key] = reader
        reader.start()
        log.info("Controller connected: %s (%s)", device.name, ctype)

    def _remove_device(self, key):
        with self._lock:
            info = self.devices.pop(key, None)
        if info:
            log.info("Controller disconnected: %s - quitting", info["name"])
            self._on_quit()

    def _reader(self, device, key, ctype):
        while not self._stop.is_set():
            try:
                events = device.read()  # blocks until events arrive
            except Exception:
                self._remove_device(key)
                return
            for event in events or ():
                try:
                    self.handle_event(ctype, event.code, event.state)
                except Exception:
                    log.exception("Bad gamepad event: %s", event.code)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def handle_event(self, ctype, code, state):
        """Apply one raw input event to the controller state."""
        if code in DPAD_CODES:
            self._handle_dpad(ctype, code, int(state))
        elif code in XBOX_TRIGGERS and ctype == XBOX:
            with self._lock:
                self.states[XBOX][XBOX_TRIGGERS[code]] = state > TRIGGER_PRESS_RAW
        elif code in XBOX_STICKS and ctype == XBOX:
            self._handle_stick(XBOX_STICKS[code], state)
        elif code.startswith("BTN"):
            self._handle_button(ctype, code, bool(state))

    def _handle_button(self, ctype, code, pressed):
        if ctype == XBOX:
            if code == "BTN_MODE":
                if pressed:
                    log.info("Xbox home button pressed - quitting")
                    self._on_quit()
                return
            if code in self._held:  # SELECT/START are mode-combo modifiers
                self._held[code] = pressed
                return
            signal = XBOX_BUTTONS.get(code)
            if signal is None:
                return
            if pressed and code == "BTN_TL":
                self._adjust_auto_state(-1)
            elif pressed and code == "BTN_TR":
                self._adjust_auto_state(1)
            with self._lock:
                self.states[XBOX][signal] = pressed
        else:
            if code == "BTN_START":
                if pressed:
                    log.info("N64 start button pressed - quitting")
                    self._on_quit()
                return
            signal = N64_BUTTONS.get(code)
            if signal is not None:
                with self._lock:
                    self.states[N64][signal] = pressed

    def _handle_dpad(self, ctype, code, value):
        # evdev hats report -1 for up/left and +1 for down/right
        if ctype == N64:
            with self._lock:
                n64 = self.states[N64]
                if code == "ABS_HAT0X":
                    n64["DP_LEFT"], n64["DP_RIGHT"] = value == -1, value == 1
                elif code == "ABS_HAT0Y":
                    n64["DP_UP"], n64["DP_DOWN"] = value == -1, value == 1
                else:  # BTN_DPAD_UP etc.
                    n64["DP_" + code.rsplit("_", 1)[1]] = bool(value)
            return

        # Xbox: D-pad + held SELECT/START toggles a drive mode
        up = (code == "ABS_HAT0Y" and value == -1) or (code == "BTN_DPAD_UP" and value)
        down = (code == "ABS_HAT0Y" and value == 1) or (code == "BTN_DPAD_DOWN" and value)
        if not (up or down):
            return
        if self._held["BTN_SELECT"]:
            self.reverse_mode = bool(up)
            log.info("Reverse mode %s", "on" if self.reverse_mode else "off")
        if self._held["BTN_START"]:
            self.creep_mode = bool(up)
            log.info("Creep mode %s", "on" if self.creep_mode else "off")

    def _handle_stick(self, signal, raw):
        if self._unsigned_sticks:
            value = (float(raw) - 127.5) / 127.5
        else:
            value = float(raw) / 32767.0
        value = max(-1.0, min(1.0, value))
        if abs(value) < DEADBAND:
            value = 0.0
        multiplier = CREEP_MULTIPLIER if self.creep_mode else 1.0
        if self.reverse_mode:
            multiplier = -multiplier
        converted = floor(multiplier * value * 100 + NEUTRAL)
        with self._lock:
            self.states[XBOX][signal] = max(AXIS_MIN, min(AXIS_MAX, converted))

    def _adjust_auto_state(self, delta):
        clamped = max(CONSTANTS.AUTO_STATE.MIN,
                      min(CONSTANTS.AUTO_STATE.MAX, self.auto_state + delta))
        if clamped != self.auto_state:
            self.auto_state = clamped
            log.info("Auto state -> %d", self.auto_state)