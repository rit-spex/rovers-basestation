# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : app.py
# purpose       : wire the inputs, rover link, and display together
#                 and run the 40 ms control loop
# created on    : 7/12/2026 - Ryan
# last modified : 7/12/2026 - Ryan
# ------------------------------------------------------------------
"""Basestation application.

main() starts the control loop on a background thread and blocks on the
display (tkinter needs the main thread). Every cycle the loop snapshots
the input devices, sends any changed messages to the rover, and hands the
display a snapshot to draw.

Quit paths: Xbox HOME / N64 START button, any input device disconnecting,
closing the GUI window, or Ctrl+C. All of them end with a QUIT message so
the rover stops.
"""

import logging
import threading
import time

from basestation.comms import Link
from basestation.gamepads import N64, XBOX, Gamepads
from basestation.gui import create_display
from basestation.keyboard import Keyboard
from basestation.protocol import CONSTANTS, MSG
from basestation.spacemouse import SpaceMouse

log = logging.getLogger(__name__)

UPDATE_PERIOD = CONSTANTS.TIMING.UPDATE_FREQUENCY / CONSTANTS.CONVERSION.NS_PER_S
HEARTBEAT_PERIOD = CONSTANTS.HEARTBEAT.INTERVAL / CONSTANTS.CONVERSION.NS_PER_S
TIMESTAMP_SIGNAL = CONSTANTS.HEARTBEAT.TIMESTAMP_MESSAGE
AUTO_STATE_SIGNAL = CONSTANTS.AUTO_STATE.NAME
AXIS_LY = CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR
AXIS_RY = CONSTANTS.XBOX.JOYSTICK.AXIS_RY_STR


def xbox_wire_values(state: dict, reverse: bool) -> dict:
    """Xbox state as sent on the wire; reverse mode swaps the sticks."""
    if not reverse:
        return state
    swapped = dict(state)
    swapped[AXIS_LY], swapped[AXIS_RY] = state[AXIS_RY], state[AXIS_LY]
    return swapped


class BaseStation:
    """Owns the input readers, the rover link, and the telemetry cache."""

    def __init__(self):
        self._quit = threading.Event()
        self._telemetry_lock = threading.Lock()
        self.telemetry = {}

        self.gamepads = Gamepads(on_quit=self.request_quit)
        self.spacemouse = SpaceMouse(on_disconnect=self.request_quit)
        self.keyboard = Keyboard(on_disconnect=self.request_quit)
        self.spacemouse.start()
        self.keyboard.start()
        self.link = Link(on_telemetry=self._store_telemetry)

        self._next_heartbeat = 0.0

    @property
    def quitting(self) -> bool:
        return self._quit.is_set()

    def request_quit(self):
        self._quit.set()

    def _store_telemetry(self, data: dict):
        data["_received_at"] = time.time()
        with self._telemetry_lock:
            self.telemetry.update(data)

    def telemetry_snapshot(self) -> dict:
        with self._telemetry_lock:
            return dict(self.telemetry)

    # ------------------------------------------------------------------
    # One control cycle
    # ------------------------------------------------------------------

    def cycle(self) -> dict:
        """Send everything due this cycle; return a display snapshot."""
        now = time.monotonic()
        if now >= self._next_heartbeat:
            self._next_heartbeat = now + HEARTBEAT_PERIOD
            timestamp = int(time.time() * 1000) % 65536
            self.link.send(MSG.HEARTBEAT_ID, {TIMESTAMP_SIGNAL: timestamp},
                           force=True)

        states, devices = self.gamepads.snapshot()
        self.link.send(MSG.XBOX_ID,
                       xbox_wire_values(states[XBOX], self.gamepads.reverse_mode))
        self.link.send(MSG.N64_ID, states[N64])
        self.link.send(MSG.AUTO_STATE_ID,
                       {AUTO_STATE_SIGNAL: self.gamepads.auto_state})

        spacemouse_state = None
        if self.spacemouse.is_connected():
            spacemouse_state = self.spacemouse.get_state()
            self.link.send(MSG.SPACEMOUSE_ID, spacemouse_state)

        keyboard_state = None
        if self.keyboard.is_connected():
            keyboard_state = self.keyboard.get_state()
            self.link.send(MSG.KEYBOARD_ID, keyboard_state)

        return {
            "devices": devices,
            "states": states,
            "spacemouse": spacemouse_state,
            "keyboard": keyboard_state,
            "creep": self.gamepads.creep_mode,
            "reverse": self.gamepads.reverse_mode,
            "auto_state": self.gamepads.auto_state,
            "simulation": self.link.simulation,
            "telemetry": self.telemetry_snapshot(),
        }

    def shutdown(self, display):
        log.info("Shutting down...")
        self.link.send_quit()
        self.gamepads.stop()
        self.spacemouse.stop()
        self.keyboard.stop()
        self.link.close()
        display.quit()
        log.info("Shutdown complete")


def control_loop(station: BaseStation, display):
    updates = 0
    next_tick = time.monotonic()
    try:
        while not station.quitting:
            try:
                snapshot = station.cycle()
                updates += 1
                snapshot["updates"] = updates
                display.update(snapshot)
            except Exception:
                log.exception("Control loop error (continuing)")
                time.sleep(0.1)
            next_tick += UPDATE_PERIOD
            delay = next_tick - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            else:
                next_tick = time.monotonic()  # fell behind, don't burst
    finally:
        station.shutdown(display)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    station = BaseStation()
    display = create_display(simulation=station.link.simulation)
    if display.root is not None:
        station.keyboard.bind_tkinter(display.root)

    log.info("Basestation started (update period %.0f ms)", UPDATE_PERIOD * 1000)
    thread = threading.Thread(target=control_loop, args=(station, display),
                              daemon=True, name="control-loop")
    thread.start()

    try:
        display.run(lambda: station.quitting)
    except KeyboardInterrupt:
        log.info("Interrupted by user")
    finally:
        station.request_quit()
        thread.join(timeout=5.0)


if __name__ == "__main__":
    main()