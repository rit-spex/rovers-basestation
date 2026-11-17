# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : keyboard.py
# purpose       : read keyboard keys for the active basestation mode
#                 (life detection or arm control)
# created on    : 7/12/2026 - Ryan
# last modified : 10/31/2026
# ------------------------------------------------------------------
"""Keyboard input for basestation modes.

Life Detection mode uses the original life-detection key map.  Arm mode
uses the bindings from ``invKin202627/src/interfaces/gui_constants.py``
for the actions that make sense on the rover.  Camera and test-overlay
keys stay local to the arm GUI and are not sent.

Life keys carry a press state the rover consumes:
    0 = not pressed, 1 = just pressed, 2 = held, 3 = just released
get_life_state() returns the current snapshot and advances 1 -> 2 and 3 -> 0.

Arm actions are edge-triggered on the rover, but the basestation owns the
key map and sends each action's press state (0-3) instead of a key
bitmask, so the rover only acts on "just pressed".

Key releases are debounced for 50 ms because some USB/wireless keyboards
emit spurious release+press pairs while a key is physically held.

Reads globally via the ``inputs`` library; when that cannot capture keys
(typical on dev laptops), bind_tkinter() makes the GUI window a fallback
input source.
"""

import logging
import sys
import threading
import time

log = logging.getLogger(__name__)

try:
    import inputs
except Exception:
    inputs = None

from basestation.inputs_compat import device_manager

NOT_PRESSED, JUST_PRESSED, HELD, JUST_RELEASED = 0, 1, 2, 3

# inputs key code -> protocol signal name (see protocol.yaml "keyboard")
LIFE_KEY_MAP = {
    "KEY_Q": "enable_science",
    "KEY_W": "move_auger_up",
    "KEY_S": "move_auger_down",
    "KEY_H": "auger_home",
    "KEY_E": "enable_drill",
    "KEY_R": "slide_next",
    "KEY_1": "pump_1",
    "KEY_2": "pump_2",
    "KEY_3": "pump_3",
    "KEY_4": "pump_4",
    "KEY_Z": "spec_slide_next",
    "KEY_X": "fluoro_slide_next",
    "KEY_C": "fluoro_micro_pump",
    "KEY_V": "enable_primer",
    "KEY_B": "enable_vibration",
}
LIFE_SIGNALS = list(LIFE_KEY_MAP.values())
LIFE_KEYS = {signal: code.removeprefix("KEY_").lower()
             for code, signal in LIFE_KEY_MAP.items()}

# tkinter keysym -> signal name, for the GUI fallback
TK_LIFE_KEY_MAP = {code.removeprefix("KEY_").lower(): sig
                   for code, sig in LIFE_KEY_MAP.items()}

# ---------------------------------------------------------------------------
# Arm keyboard actions (invKin202627 bindings, rover-relevant subset)
# ---------------------------------------------------------------------------
# Actions the basestation maps physical keys to; each is sent on the wire
# as a per-action press state.
ARM_ACTIONS = (
    "flip",
    "home",
    "position_drive",
    "joint_drive",
    "pnp_normal",
    "toggle_planar",
    "guide_orientation",
    "toggle_position_lock",
    "toggle_orientation_lock",
    "toggle_joint_lock:0",
    "toggle_joint_lock:1",
    "toggle_joint_lock:2",
    "toggle_joint_lock:3",
    "toggle_joint_lock:4",
    "home_joint:0",
    "home_joint:1",
    "home_joint:2",
    "home_joint:3",
    "home_joint:4",
    "solenoid_strike",
)
# Per-action wire signal name. Colons are not legal in ROS topic names,
# so the numbered actions use an underscore on the wire.
ARM_STATE_SIGNALS = {action: action.replace(":", "_")
                     for action in ARM_ACTIONS}

ARM_KEY_MAP = {
    "KEY_F": "flip",
    "KEY_H": "home",
    "KEY_I": "position_drive",
    "KEY_J": "joint_drive",
    "KEY_V": "pnp_normal",
    "KEY_X": "toggle_planar",
    "KEY_G": "guide_orientation",
    "KEY_L": "toggle_position_lock",
    "KEY_O": "toggle_orientation_lock",
    "KEY_S": "solenoid_strike",
}
ARM_NUMBER_MAP = {
    "KEY_1": 0, "KEY_2": 1, "KEY_3": 2, "KEY_4": 3, "KEY_5": 4,
    "KEY_KP1": 0, "KEY_KP2": 1, "KEY_KP3": 2, "KEY_KP4": 3, "KEY_KP5": 4,
}
ARM_KEYS = {action: code.removeprefix("KEY_").lower()
            for code, action in ARM_KEY_MAP.items()}
for _code, _index in ARM_NUMBER_MAP.items():
    _label = _code.removeprefix("KEY_").lower()
    ARM_KEYS.setdefault(f"toggle_joint_lock:{_index}", _label)
    ARM_KEYS.setdefault(f"home_joint:{_index}", f"shift+{_label}")

# tkinter fallback maps
TK_ARM_KEY_MAP = {code.removeprefix("KEY_").lower(): action
                  for code, action in ARM_KEY_MAP.items()}
TK_ARM_NUMBER_MAP = {
    "1": 0, "2": 1, "3": 2, "4": 3, "5": 4,
    "kp_1": 0, "kp_2": 1, "kp_3": 2, "kp_4": 3, "kp_5": 4,
}
# Shift+number keysyms as delivered by tkinter.
TK_ARM_SHIFT_NUMBER_MAP = {
    "exclam": 0, "at": 1, "numbersign": 2, "dollar": 3, "percent": 4,
}

# Arrow/nav keys synthesize SpaceMouse axes so they can jog the arm while
# held.  The rover already consumes these axes for both drive modes, so no
# protocol change is needed.
JOG_MAGNITUDE = 60
ARM_JOG_KEYS = {
    "KEY_LEFT": ("rz", 1),
    "KEY_RIGHT": ("rz", -1),
    "KEY_UP": ("ry", 1),
    "KEY_DOWN": ("ry", -1),
    "KEY_PAGEUP": ("rx", 1),
    "KEY_PAGE_UP": ("rx", 1),
    "KEY_PAGEDOWN": ("rx", -1),
    "KEY_PAGE_DOWN": ("rx", -1),
}
TK_ARM_JOG_KEYS = {
    "left": ("rz", 1),
    "right": ("rz", -1),
    "up": ("ry", 1),
    "down": ("ry", -1),
    "prior": ("rx", 1),
    "next": ("rx", -1),
}

RELEASE_DEBOUNCE_SECONDS = 0.05


class Keyboard:
    """Background keyboard reader with mode-aware press-state tracking."""

    def __init__(self, on_disconnect=None):
        self._on_disconnect = on_disconnect
        self._lock = threading.Lock()
        self._mode = "life"
        self._life_state = self.life_zero_state()
        self._life_down = dict.fromkeys(LIFE_SIGNALS, False)
        # signal -> monotonic time release was seen
        self._life_pending_release = {}
        self._arm_down = set()
        self._arm_pending = set()
        self._arm_state = dict.fromkeys(ARM_ACTIONS, NOT_PRESSED)
        self._arm_release_at = {}  # action -> monotonic time release was seen
        self._jog_axes = {}
        self._shift_down = False
        self._present = False       # a physical keyboard is enumerated
        self._tk_active = False     # the GUI fallback has produced input
        self._stop = threading.Event()
        self._release_debounce = RELEASE_DEBOUNCE_SECONDS

    @staticmethod
    def life_zero_state() -> dict:
        return dict.fromkeys(LIFE_SIGNALS, NOT_PRESSED)

    @staticmethod
    def key_for_life(signal: str) -> str:
        """Key letter bound to a life-detection signal, for display."""
        return LIFE_KEYS.get(signal, "?")

    @staticmethod
    def key_for_arm(action: str) -> str:
        """Key bound to an arm action, for display."""
        return ARM_KEYS.get(action, "?")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        if inputs is None:
            log.warning("inputs library unavailable - keyboard limited to GUI window")
            return
        # Global key capture only on Linux (the Pi). On Windows the inputs
        # library spawns a non-daemon child process for it that hangs the
        # interpreter at exit; the tkinter fallback covers dev machines.
        if sys.platform.startswith("linux"):
            threading.Thread(target=self._read_loop, daemon=True,
                             name="keyboard-reader").start()
        threading.Thread(target=self._monitor, daemon=True,
                         name="keyboard-monitor").start()

    def stop(self):
        self._stop.set()
        self._on_disconnect = None

    def is_connected(self) -> bool:
        with self._lock:
            return self._present or self._tk_active

    def set_mode(self, mode: str):
        """Select which key map is active: life, arm, or neither."""
        with self._lock:
            if mode == self._mode:
                return
            self._mode = mode
            self._reset_life_locked()
            self._reset_arm_locked()
            self._shift_down = False

    def get_life_state(self) -> dict:
        """Snapshot the life-detection key states and advance transients."""
        with self._lock:
            self._commit_life_releases()
            if self._mode != "life":
                return self.life_zero_state()
            snapshot = dict(self._life_state)
            for signal in LIFE_SIGNALS:
                if self._life_state[signal] == JUST_PRESSED:
                    self._life_state[signal] = HELD
                elif self._life_state[signal] == JUST_RELEASED:
                    self._life_state[signal] = NOT_PRESSED
            return snapshot

    def get_arm_state(self) -> dict:
        """Snapshot the per-action arm press states and advance transients.

        Each action uses the same 0-3 encoding as the life-detection keys:
        not pressed, just pressed, held, just released.  The rover acts
        only on "just pressed", so it never needs the key map.
        """
        with self._lock:
            self._commit_arm_releases()
            if self._mode != "arm":
                self._arm_pending.clear()
                self._arm_state = dict.fromkeys(ARM_ACTIONS, NOT_PRESSED)
                return dict.fromkeys(ARM_STATE_SIGNALS.values(), NOT_PRESSED)

            snapshot = dict(self._arm_state)
            # A tap shorter than one control cycle must still report a press.
            for action in self._arm_pending:
                snapshot[action] = JUST_PRESSED
            self._arm_pending.clear()

            for action in ARM_ACTIONS:
                if self._arm_state[action] == JUST_PRESSED:
                    self._arm_state[action] = HELD
                elif self._arm_state[action] == JUST_RELEASED:
                    self._arm_state[action] = NOT_PRESSED

            return {
                ARM_STATE_SIGNALS[action]: snapshot[action]
                for action in ARM_ACTIONS
            }

    def arm_pressed(self) -> dict:
        """Per-action pressed state, for the basestation display."""
        with self._lock:
            self._commit_arm_releases()
            active = self._arm_down if self._mode == "arm" else ()
            return {action: action in active for action in ARM_ACTIONS}

    def release_all_arm(self):
        with self._lock:
            self._reset_arm_locked()

    def jog_axes(self) -> dict:
        """Signed SpaceMouse axes synthesized by held jog keys."""
        with self._lock:
            if self._mode != "arm":
                return {}
            return dict(self._jog_axes)

    def press_jog(self, axis: str, sign: int):
        """Simulated jog-key press for the on-screen keyboard."""
        with self._lock:
            self._tk_active = True
            self._press_jog(axis, sign)

    def release_jog(self, axis: str, sign: int):
        """Simulated jog-key release for the on-screen keyboard."""
        with self._lock:
            self._tk_active = True
            self._release_jog(axis, sign)

    def press_arm(self, action: str):
        """Simulated arm-key press for the on-screen keyboard."""
        with self._lock:
            self._tk_active = True
            self._arm_press(action)

    def release_arm(self, action: str):
        """Simulated arm-key release for the on-screen keyboard."""
        with self._lock:
            self._tk_active = True
            self._arm_key_release(action)

    def bind_tkinter(self, root):
        """Use the GUI window as a fallback key source when focused."""
        root.bind("<KeyPress>", self._on_tk_event(pressed=True))
        root.bind("<KeyRelease>", self._on_tk_event(pressed=False))

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def _reset_life_locked(self):
        self._life_state = self.life_zero_state()
        self._life_down = dict.fromkeys(LIFE_SIGNALS, False)
        self._life_pending_release.clear()

    def _reset_arm_locked(self):
        self._arm_down.clear()
        self._arm_pending.clear()
        self._arm_release_at.clear()
        self._arm_state = dict.fromkeys(ARM_ACTIONS, NOT_PRESSED)
        self._jog_axes.clear()

    def _commit_life_releases(self):
        now = time.monotonic()
        for signal, seen_at in list(self._life_pending_release.items()):
            if now - seen_at >= self._release_debounce:
                del self._life_pending_release[signal]
                if self._life_down[signal]:
                    self._life_state[signal] = JUST_RELEASED
                    self._life_down[signal] = False

    def _press_life(self, signal):
        # a fresh press cancels a bouncy release
        self._life_pending_release.pop(signal, None)
        if not self._life_down[signal]:
            self._life_state[signal] = JUST_PRESSED
            self._life_down[signal] = True

    def _release_life(self, signal):
        if self._life_down[signal]:
            self._life_pending_release[signal] = time.monotonic()

    def _arm_press(self, action):
        self._arm_release_at.pop(action, None)  # cancels a bouncy release
        if action not in self._arm_down:
            self._arm_state[action] = JUST_PRESSED
            self._arm_pending.add(action)
        self._arm_down.add(action)

    def _arm_release(self, action):
        if action in self._arm_down:
            self._arm_release_at[action] = time.monotonic()

    def _commit_arm_releases(self):
        """Drop arm actions whose release has been stable for the debounce.

        Some USB/wireless keyboards emit a spurious release+press while a
        key is physically held.  Releasing immediately would make the rover
        see a falling then rising edge and run a toggle twice.  Holding the
        action for one debounce window absorbs the bounce.
        """
        now = time.monotonic()
        for action, seen_at in list(self._arm_release_at.items()):
            if now - seen_at >= self._release_debounce:
                if action in self._arm_pending:
                    continue  # report the press before the release
                del self._arm_release_at[action]
                if action in self._arm_down:
                    self._arm_down.discard(action)
                    self._arm_state[action] = JUST_RELEASED

    def _press_jog(self, axis, sign):
        self._jog_axes[axis] = JOG_MAGNITUDE * sign

    def _release_jog(self, axis, sign):
        if self._jog_axes.get(axis) == JOG_MAGNITUDE * sign:
            self._jog_axes.pop(axis, None)

    def _arm_key_release(self, action):
        """Release both number-key variants (lock and home)."""
        self._arm_release(action)
        if action.startswith(("toggle_joint_lock:", "home_joint:")):
            index = action.rsplit(":", 1)[1]
            self._arm_release(f"toggle_joint_lock:{index}")
            self._arm_release(f"home_joint:{index}")

    # ------------------------------------------------------------------
    # Input sources
    # ------------------------------------------------------------------

    def _read_loop(self):
        while not self._stop.is_set():
            try:
                events = inputs.get_key()  # blocks until key events arrive
            except Exception:
                self._stop.wait(0.5)
                continue
            for event in events or ():
                if event.ev_type != "Key":
                    continue
                if event.code in ("KEY_LEFTSHIFT", "KEY_RIGHTSHIFT"):
                    with self._lock:
                        self._shift_down = event.state != 0
                    continue

                with self._lock:
                    mode = self._mode
                    if mode == "life":
                        signal = LIFE_KEY_MAP.get(event.code)
                        if signal is None:
                            continue
                        if event.state == 0:
                            self._release_life(signal)
                        else:  # 1 = press, 2 = OS key repeat
                            self._press_life(signal)
                    elif mode == "arm":
                        jog = ARM_JOG_KEYS.get(event.code)
                        if jog is not None:
                            axis, sign = jog
                            if event.state == 0:
                                self._release_jog(axis, sign)
                            else:
                                self._press_jog(axis, sign)
                            continue
                        action = ARM_KEY_MAP.get(event.code)
                        if action is None:
                            index = ARM_NUMBER_MAP.get(event.code)
                            if index is not None:
                                action = (
                                    f"home_joint:{index}"
                                    if self._shift_down
                                    else f"toggle_joint_lock:{index}")
                        if action is None:
                            continue
                        if event.state == 0:
                            self._arm_key_release(action)
                        else:
                            self._arm_press(action)

    def _monitor(self):
        """Track physical keyboard presence (issues #25/#26)."""
        while not self._stop.is_set():
            present = self._scan_keyboards()
            if present is None:  # enumeration fail so keep last known state
                self._stop.wait(0.5)
                continue
            with self._lock:
                was_present = self._present
                self._present = present
            if was_present and not present:
                log.info("Keyboard disconnected")
                if self._on_disconnect is not None:
                    self._on_disconnect()
            self._stop.wait(0.5)

    @staticmethod
    def _scan_keyboards():
        """True/False = keyboard present; None = enumeration failed.

        A DeviceManager rebuild can fail for a bit mid hotplug and that must
        not be mistaken for the keyboard disconnecting (which quits the app).
        """
        try:
            # inputs.devices is refreshed by the gamepad monitor so rebuild
            # here too so this works even with gamepads disabled
            inputs.devices = device_manager(inputs)
            return bool(inputs.devices.keyboards)
        except Exception:
            return None

    def _on_tk_event(self, pressed):
        def _handler(event):
            with self._lock:
                if self._mode == "life":
                    signal = TK_LIFE_KEY_MAP.get(event.keysym.lower())
                    if signal is None:
                        return
                    self._tk_active = True
                    if pressed:
                        self._press_life(signal)
                    else:
                        self._release_life(signal)
                elif self._mode == "arm":
                    keysym = event.keysym.lower()
                    jog = TK_ARM_JOG_KEYS.get(keysym)
                    if jog is not None:
                        # Do not steal arrows while editing a spinbox or
                        # dropdown; those widgets use them for navigation.
                        try:
                            widget_class = event.widget.winfo_class()
                        except Exception:
                            widget_class = ""
                        if widget_class in ("Entry", "Spinbox", "TSpinbox",
                                            "TCombobox"):
                            return
                        self._tk_active = True
                        axis, sign = jog
                        if pressed:
                            self._press_jog(axis, sign)
                        else:
                            self._release_jog(axis, sign)
                        return
                    action = self._tk_arm_action(event)
                    if action is None:
                        return
                    self._tk_active = True
                    if pressed:
                        self._arm_press(action)
                    else:
                        self._arm_key_release(action)
        return _handler

    @staticmethod
    def _tk_arm_action(event):
        keysym = event.keysym.lower()
        action = TK_ARM_KEY_MAP.get(keysym)
        if action is not None:
            return action
        index = TK_ARM_NUMBER_MAP.get(keysym)
        if index is not None:
            shifted = bool(event.state & 0x0001)
            return (f"home_joint:{index}" if shifted
                    else f"toggle_joint_lock:{index}")
        index = TK_ARM_SHIFT_NUMBER_MAP.get(keysym)
        if index is not None:
            return f"home_joint:{index}"
        return None
