# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : keyboard.py
# purpose       : read keyboard keys that control the life detection
#                 module and track their press states
# created on    : 7/12/2026 - Ryan
# last modified : 7/14/2026 - Ryan
# ------------------------------------------------------------------
"""Keyboard input for life detection control.

Each mapped key carries a press state the rover consumes:
    0 = not pressed, 1 = just pressed, 2 = held, 3 = just released
get_state() returns the current snapshot and advances 1 -> 2 and 3 -> 0.

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

NOT_PRESSED, JUST_PRESSED, HELD, JUST_RELEASED = 0, 1, 2, 3

# inputs key code -> protocol signal name (see protocol.yaml "keyboard")
KEY_MAP = {
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
SIGNALS = list(KEY_MAP.values())

# tkinter keysym -> signal name, for the GUI fallback
TK_KEY_MAP = {code.removeprefix("KEY_").lower(): sig for code, sig in KEY_MAP.items()}

RELEASE_DEBOUNCE_SECONDS = 0.05


class Keyboard:
    """Background keyboard reader with press-state tracking."""

    def __init__(self, on_disconnect=None):
        self._on_disconnect = on_disconnect
        self._lock = threading.Lock()
        self._state = self.zero_state()
        self._down = dict.fromkeys(SIGNALS, False)
        self._pending_release = {}  # signal -> monotonic time release was seen
        self._present = False       # a physical keyboard is enumerated
        self._tk_active = False     # the GUI fallback has produced input
        self._stop = threading.Event()
        self._release_debounce = RELEASE_DEBOUNCE_SECONDS

    @staticmethod
    def zero_state() -> dict:
        return dict.fromkeys(SIGNALS, NOT_PRESSED)

    @staticmethod
    def key_for(signal: str) -> str:
        """Key letter bound to a signal, for display."""
        for code, sig in KEY_MAP.items():
            if sig == signal:
                return code.removeprefix("KEY_").lower()
        return "?"

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

    def get_state(self) -> dict:
        """Snapshot the key states and advance the transient ones."""
        with self._lock:
            self._commit_expired_releases()
            snapshot = dict(self._state)
            for signal in SIGNALS:
                if self._state[signal] == JUST_PRESSED:
                    self._state[signal] = HELD
                elif self._state[signal] == JUST_RELEASED:
                    self._state[signal] = NOT_PRESSED
            return snapshot

    def bind_tkinter(self, root):
        """Use the GUI window as a fallback key source when focused."""
        root.bind("<KeyPress>", self._on_tk_event(pressed=True))
        root.bind("<KeyRelease>", self._on_tk_event(pressed=False))

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def _commit_expired_releases(self):
        now = time.monotonic()
        for signal, seen_at in list(self._pending_release.items()):
            if now - seen_at >= self._release_debounce:
                del self._pending_release[signal]
                if self._down[signal]:
                    self._state[signal] = JUST_RELEASED
                    self._down[signal] = False

    def _press(self, signal):
        self._pending_release.pop(signal, None)  # cancels a bouncy release
        if not self._down[signal]:
            self._state[signal] = JUST_PRESSED
            self._down[signal] = True

    def _release(self, signal):
        if self._down[signal]:
            self._pending_release[signal] = time.monotonic()

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
                signal = KEY_MAP.get(event.code)
                if signal is None:
                    continue
                with self._lock:
                    if event.state == 0:
                        self._release(signal)
                    else:  # 1 = press, 2 = OS key repeat
                        self._press(signal)

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
            inputs.devices = inputs.DeviceManager()
            return bool(inputs.devices.keyboards)
        except Exception:
            return None

    def _on_tk_event(self, pressed):
        def _handler(event):
            signal = TK_KEY_MAP.get(event.keysym.lower())
            if signal is None:
                return
            with self._lock:
                self._tk_active = True
                if pressed:
                    self._press(signal)
                else:
                    self._release(signal)
        return _handler