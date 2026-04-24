"""
Keyboard input reader for life detection module control.

Reads keyboard key states using the ``inputs`` library and tracks
press states: just_pressed (1), held (2), just_released (3), not_pressed (0).

Runs a background thread that continuously polls keyboard events and
exposes the latest state in a thread-safe manner, following the same
pattern as the SpaceMouse HID reader.

Usage::

    kb = KeyboardInput()
    kb.start()
    ...
    state = kb.get_state()  # {"enable_science": 0, "move_auger_up": 2, ...}
    ...
    kb.stop()

Key Bindings (life detection):
    q -> enable_science
    w -> move_auger_up
    s -> move_auger_down
    h -> auger_home
    e -> enable_drill
    r -> slide_next
    1 -> pump_1
    2 -> pump_2
    3 -> pump_3
    4 -> pump_4
    z -> spec_slide_next
    x -> fluoro_slide_next
    c -> fluoro_micro_pump
    v -> enable_primer
    b -> enable_vibration
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)

try:
    import inputs as inputs_lib  # type: ignore

    INPUTS_AVAILABLE = True
except Exception:
    inputs_lib = None
    INPUTS_AVAILABLE = False

# Press state constants
NOT_PRESSED = 0
JUST_PRESSED = 1
HELD = 2
JUST_RELEASED = 3

# Map from inputs library key codes to protocol signal names
# inputs library uses KEY_<letter> format for key event codes
_KEY_MAP: Dict[str, str] = {
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

# All signal names (used for building zero state)
_ALL_SIGNALS = list(_KEY_MAP.values())

# Tkinter keysym -> signal name (for GUI-based key capture fallback)
_TK_KEY_MAP: Dict[str, str] = {
    k.replace("KEY_", "").lower(): v for k, v in _KEY_MAP.items()
}


class KeyboardInput:
    """Background keyboard reader for life detection control.

    Tracks key press states: 0=not_pressed, 1=just_pressed, 2=held, 3=just_released.
    State transitions per cycle:
        - Key down event: state becomes JUST_PRESSED (1)
        - Already JUST_PRESSED on next get_state(): becomes HELD (2)
        - Key up event: state becomes JUST_RELEASED (3)
        - Already JUST_RELEASED on next get_state(): becomes NOT_PRESSED (0)

    Parameters
    ----------
    poll_interval : float
        Seconds to sleep when no events are available (default 0.001).
    on_disconnect : callable, optional
        Callback when keyboard input is lost.
    """

    def __init__(
        self,
        *,
        poll_interval: float = 0.001,
        on_disconnect: Optional[Callable[[], None]] = None,
    ) -> None:
        self._poll_interval = poll_interval
        self._on_disconnect = on_disconnect

        # Release debounce window: when a key release arrives we hold it for
        # this long before committing.  If a press for the same key arrives
        # within the window the release is cancelled.  This filters the
        # spurious release/repeat sequences that some USB / wireless dongle
        # keyboards emit while a key is physically held.
        self._release_debounce_seconds = 0.05

        # Thread-safe state
        self._lock = threading.Lock()
        # Raw key-down tracking (True = currently physically held)
        self._keys_down: Dict[str, bool] = {sig: False for sig in _ALL_SIGNALS}
        # Pending release timestamps (signal -> monotonic time when release
        # was first seen).  Empty means no pending release.
        self._pending_release: Dict[str, float] = {}
        # Output state with press transitions
        self._state: Dict[str, int] = self._zero_state()
        self._connected = False
        # True once the ``inputs`` library successfully captures at least
        # one key event.  Used to distinguish a real USB-keyboard unplug
        # (Pi) from the library simply failing to start (Windows laptop).
        self._inputs_ever_connected = False
        # Set when bind_tkinter() is called so the device monitor knows the
        # GUI is acting as a fallback input source and shouldn't flip the
        # connected flag off.
        self._tkinter_bound = False

        # Background threads
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_interval = 0.5

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        if not INPUTS_AVAILABLE:
            logger.warning(
                "inputs library not available – keyboard input disabled. "
                "Install with: pip install inputs"
            )
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="keyboard-reader", daemon=True
        )
        self._thread.start()
        self._monitor_thread = threading.Thread(
            target=self._device_monitor_loop,
            name="keyboard-monitor",
            daemon=True,
        )
        self._monitor_thread.start()
        logger.info("Keyboard input reader started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=3.0)
            self._monitor_thread = None
        logger.info("Keyboard input reader stopped")

    def get_state(self) -> Dict[str, int]:
        """Return a snapshot of the current key states and advance transitions.

        After reading:
        - JUST_PRESSED (1) -> HELD (2) on next call
        - JUST_RELEASED (3) -> NOT_PRESSED (0) on next call
        """
        with self._lock:
            self._commit_expired_releases_unlocked()
            snapshot = self._state.copy()
            # Advance transient states
            for sig in _ALL_SIGNALS:
                if self._state[sig] == JUST_PRESSED:
                    self._state[sig] = HELD
                elif self._state[sig] == JUST_RELEASED:
                    self._state[sig] = NOT_PRESSED
            return snapshot

    def _commit_expired_releases_unlocked(self) -> None:
        """Finalize any release events whose debounce window has expired."""
        if not self._pending_release:
            return
        now = time.monotonic()
        expired = [
            sig
            for sig, ts in self._pending_release.items()
            if now - ts >= self._release_debounce_seconds
        ]
        for sig in expired:
            self._pending_release.pop(sig, None)
            if self._keys_down.get(sig):
                self._state[sig] = JUST_RELEASED
                self._keys_down[sig] = False

    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    @staticmethod
    def _zero_state() -> Dict[str, int]:
        return {sig: NOT_PRESSED for sig in _ALL_SIGNALS}

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main loop: read keyboard events continuously."""
        try:
            self._read_loop()
        except Exception:
            logger.exception("Keyboard reader thread error")

    def _is_keyboard_present(self) -> bool:
        """Return True if the OS reports at least one connected keyboard."""
        if inputs_lib is None:
            return False
        try:
            return len(list(inputs_lib.devices.keyboards)) > 0
        except Exception:
            return False

    def _device_monitor_loop(self) -> None:
        """Track physical keyboard presence and fire disconnect callback.

        Runs alongside the read loop so we notice unplugs even when the
        user never pressed a key, and so the connection state shown in the
        UI reflects the actual hardware (issue #25, #26).
        """
        if inputs_lib is None:
            return
        while not self._stop_event.is_set():
            try:
                inputs_lib.devices = inputs_lib.DeviceManager()
            except Exception:
                logger.debug("Failed to refresh input device manager", exc_info=True)
            present = self._is_keyboard_present()
            with self._lock:
                was_connected = self._connected
                self._connected = present
            if was_connected and not present:
                logger.info("Keyboard disconnected (no keyboard devices found)")
                if self._on_disconnect is not None:
                    try:
                        self._on_disconnect()
                    except Exception:
                        logger.warning(
                            "Keyboard on_disconnect callback error", exc_info=True
                        )
            self._stop_event.wait(self._monitor_interval)

    def _read_loop(self) -> None:
        consecutive_errors = 0
        max_consecutive_errors = 10  # ~5 s of errors before giving up

        while not self._stop_event.is_set():
            try:
                # inputs.get_key() blocks until an event is available.
                # We use a try/except to handle the case where no keyboard
                # is present or the library can't access it.
                events = inputs_lib.get_key()
                if not events:
                    time.sleep(self._poll_interval)
                    continue

                consecutive_errors = 0  # Reset on successful read
                self._inputs_ever_connected = True

                for event in events:
                    self._process_event(event)

            except (OSError, IOError):
                consecutive_errors += 1
                if (
                    self._inputs_ever_connected
                    and consecutive_errors >= max_consecutive_errors
                ):
                    logger.warning(
                        "Keyboard disconnected after %d consecutive read errors",
                        consecutive_errors,
                    )
                    break
                logger.warning("Keyboard read error – retrying")
                time.sleep(0.5)
            except Exception:
                consecutive_errors += 1
                if (
                    self._inputs_ever_connected
                    and consecutive_errors >= max_consecutive_errors
                ):
                    logger.warning("Keyboard disconnected (sustained errors)")
                    break
                logger.debug("Keyboard event read failed", exc_info=True)
                time.sleep(self._poll_interval)

    def _process_event(self, event) -> None:
        # inputs library event: event.code = 'KEY_Q', event.state = 1 (down) or 0 (up)
        # event.ev_type = 'Key'
        ev_type = getattr(event, "ev_type", None)
        if ev_type != "Key":
            return

        code = getattr(event, "code", None)
        state = getattr(event, "state", None)
        if code is None or state is None:
            return

        signal = _KEY_MAP.get(code)
        if signal is None:
            return  # Not a mapped key

        with self._lock:
            if state == 1:
                # Key pressed (or re-pressed within the release debounce
                # window – cancel the pending release and stay HELD).
                if signal in self._pending_release:
                    self._pending_release.pop(signal, None)
                    return
                if not self._keys_down[signal]:
                    self._state[signal] = JUST_PRESSED
                    self._keys_down[signal] = True
            elif state == 0:
                # Key released – defer commit so a follow-up press from a
                # noisy keyboard driver can cancel it.
                if self._keys_down[signal]:
                    self._pending_release[signal] = time.monotonic()
            elif state == 2:
                # Key repeat (held) on Linux – treat as still down and
                # cancel any pending release for this key.
                self._pending_release.pop(signal, None)
                if not self._keys_down[signal]:
                    self._state[signal] = JUST_PRESSED
                    self._keys_down[signal] = True

    # ------------------------------------------------------------------
    # Tkinter integration (fallback input when `inputs` library unavailable)
    # ------------------------------------------------------------------

    def bind_tkinter(self, root) -> None:
        """Bind tkinter key events as a fallback keyboard input source.

        When the GUI window is focused, key presses/releases will be
        captured by tkinter and injected into the state machine, even if
        the ``inputs`` library cannot capture global keyboard events.
        """
        root.bind("<KeyPress>", self._on_tk_key_press)
        root.bind("<KeyRelease>", self._on_tk_key_release)
        with self._lock:
            self._tkinter_bound = True
        logger.info("Keyboard input bound to tkinter window (fallback mode)")

    def _on_tk_key_press(self, event) -> None:
        signal = _TK_KEY_MAP.get(event.keysym.lower())
        if signal is None:
            return
        with self._lock:
            if not self._keys_down[signal]:
                self._state[signal] = JUST_PRESSED
                self._keys_down[signal] = True

    def _on_tk_key_release(self, event) -> None:
        signal = _TK_KEY_MAP.get(event.keysym.lower())
        if signal is None:
            return
        with self._lock:
            if self._keys_down[signal]:
                self._state[signal] = JUST_RELEASED
                self._keys_down[signal] = False

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def get_key_bindings() -> Dict[str, str]:
        # Invert for display: signal -> key name
        return {v: k.replace("KEY_", "").lower() for k, v in _KEY_MAP.items()}
