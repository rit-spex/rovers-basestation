# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : app.py
# purpose       : wire the inputs, rover link, and display together
#                 and run the 40 ms control loop
# created on    : 7/12/2026 - Ryan
# last modified : 11/9/2026 - Zach
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

import argparse
import logging
import signal
import threading
import time

from basestation.comms import Link
from basestation.gamepads import N64, XBOX, Gamepads
from basestation.gui import create_display
from basestation.keyboard import (ARM_STATE_SIGNALS, JUST_PRESSED,
                                  NOT_PRESSED, Keyboard)
from basestation.protocol import CONSTANTS, MSG, env_flag
from basestation.simulated_input_devices import SimulatedInputs
from basestation.spacemouse import SpaceMouse

log = logging.getLogger(__name__)

UPDATE_PERIOD = CONSTANTS.TIMING.UPDATE_FREQUENCY / CONSTANTS.CONVERSION.NS_PER_S
HEARTBEAT_PERIOD = CONSTANTS.HEARTBEAT.INTERVAL / CONSTANTS.CONVERSION.NS_PER_S
TIMESTAMP_SIGNAL = CONSTANTS.HEARTBEAT.TIMESTAMP_MESSAGE
AUTO_STATE_SIGNAL = CONSTANTS.AUTO_STATE.NAME
AXIS_LY = CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR
AXIS_RY = CONSTANTS.XBOX.JOYSTICK.AXIS_RY_STR
NEUTRAL_AXIS = CONSTANTS.XBOX.JOYSTICK.NEUTRAL_INT

# The radio is a shared half-duplex channel with one ACKed packet per frame.
# Re-sending idle state every 40 ms saturates it and the rover loses real
# commands, so idle states go quiet.  When a state returns to idle its idle
# value is repeated this many cycles so one dropped frame cannot leave the
# rover holding the last active value (the drive, a held jog, or a key).
RELEASE_BURST_FRAMES = 5

LOCK_ALL_ACTION = "lock_all_joints"
JOINT_LOCK_SIGNALS = tuple(
    ARM_STATE_SIGNALS[f"toggle_joint_lock:{index}"] for index in range(5))


def arm_wire_state(state: dict, locked_joints=None) -> dict:
    """Expand the local lock-all key into the per-joint lock commands.

    The rover understands ``toggle_joint_lock_N`` but not lock-all, and
    ``lock_all_joints`` is basestation-only so it must never reach the
    XBee.  This removes it and emits one pulse for every joint telemetry
    reports as unlocked, which leaves all five locked without ever
    unlocking one.  Without telemetry the macro is ignored rather than
    risk unlocking a joint.
    """
    state = dict(state)
    local_lock_all = state.pop(LOCK_ALL_ACTION, NOT_PRESSED)

    # Rebuild from the protocol field list so no local action can leak out.
    wire = {
        signal_name: state.get(signal_name, NOT_PRESSED)
        for signal_name in ARM_STATE_SIGNALS.values()
    }
    if local_lock_all != JUST_PRESSED:
        return wire
    if locked_joints is None:
        return wire

    locked = int(locked_joints)
    for index, signal_name in enumerate(JOINT_LOCK_SIGNALS):
        if not locked & (1 << index):
            wire[signal_name] = JUST_PRESSED
    return wire


def xbox_wire_values(state: dict, reverse: bool) -> dict:
    """Xbox state as sent on the wire; reverse mode swaps the sticks."""
    if not reverse:
        return state
    swapped = dict(state)
    swapped[AXIS_LY], swapped[AXIS_RY] = state[AXIS_RY], state[AXIS_LY]
    return swapped


class StreamGate:
    """Decide whether a state is transmitted with force this cycle.

    While the state is active it is sent every cycle.  When it returns to
    idle the idle value is repeated for ``RELEASE_BURST_FRAMES`` cycles, and
    then the stream goes quiet.  Unforced sends still go out when the payload
    changes, so edges and mode changes are sent once as they happen.
    """

    def __init__(self, burst: int = RELEASE_BURST_FRAMES):
        self._burst = burst
        self._was_active = False
        self._remaining = 0

    def should_force(self, active: bool) -> bool:
        if self._was_active and not active:
            self._remaining = self._burst
        self._was_active = active
        if active:
            return True
        if self._remaining > 0:
            self._remaining -= 1
            return True
        return False


class BaseStation:
    """Owns the input readers, the rover link, and the telemetry cache."""

    def __init__(self, sim_inputs: bool = False,
                 real_spacemouse: bool = False):
        self._quit = threading.Event()
        self._telemetry_lock = threading.Lock()
        self._mode_listeners = []
        self._mode_applied = False
        self.telemetry = {}

        self.simulation = (
            SimulatedInputs(real_spacemouse) if sim_inputs else None)
        if self.simulation is not None:
            (self.gamepads, self.spacemouse,
             self.keyboard) = self.simulation.devices
        else:
            self.gamepads = Gamepads(on_quit=self.request_quit)
            self.spacemouse = SpaceMouse(on_disconnect=self.request_quit)
            self.keyboard = Keyboard(on_disconnect=self.request_quit)
        self.spacemouse.start()
        self.keyboard.start()
        self.link = Link(on_telemetry=self._store_telemetry)
        if self.simulation is not None:
            self.simulation.start_control(self)

        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True, name="heartbeat")
        self._heartbeat_thread.start()
        self.mode = "nothing"
        self._gates = {name: StreamGate() for name in (
            "xbox", "spacemouse", "keyboard", "arm_state", "auto_state")}
        self._last_auto_state = None

    @property
    def quitting(self) -> bool:
        return self._quit.is_set()

    def request_quit(self):
        self._quit.set()

    def set_mode(self, mode: str):
        """Follow the basestation's selected module mode.

        The mode can change from the Tk display, the Gazebo Sim Inputs
        panel, or a sim-control command.  Notify every listener so the
        other panels show the same mode instead of drifting apart.
        """
        if mode == self.mode and self._mode_applied:
            return
        self.mode = mode
        self._mode_applied = True
        self.keyboard.set_mode(mode)
        for listener in tuple(self._mode_listeners):
            try:
                listener(mode)
            except Exception:
                log.exception("Mode listener failed")

    def add_mode_listener(self, listener):
        if listener not in self._mode_listeners:
            self._mode_listeners.append(listener)
            listener(self.mode)

    def _store_telemetry(self, data: dict):
        data["_received_at"] = time.time()
        with self._telemetry_lock:
            self.telemetry.update(data)

    def telemetry_snapshot(self) -> dict:
        with self._telemetry_lock:
            return dict(self.telemetry)

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    def _heartbeat_loop(self):
        """Send the rover's liveness heartbeat on its own thread.

        The control loop also drives the GUI snapshot and every input
        device.  A slow Tk redraw or a loaded host can stall that loop for
        longer than the rover's heartbeat timeout, which latches a false
        E-STOP, so the heartbeat must not share its scheduling fate.
        """
        next_tick = time.monotonic()
        while not self._quit.is_set() and not self._heartbeat_stop.is_set():
            timestamp = int(time.time() * 1000) % 65536
            try:
                self.link.send(
                    MSG.HEARTBEAT_ID, {TIMESTAMP_SIGNAL: timestamp},
                    force=True)
            except Exception:
                log.exception("Heartbeat send failed")
            next_tick += HEARTBEAT_PERIOD
            delay = next_tick - time.monotonic()
            if delay > 0:
                self._heartbeat_stop.wait(delay)
            else:
                next_tick = time.monotonic()

    # ------------------------------------------------------------------
    # One control cycle
    # ------------------------------------------------------------------

    def _send_stream(self, name: str, message_id: int, values: dict,
                     active: bool):
        """Send one state through its gate; see StreamGate."""
        self.link.send(message_id, values,
                       force=self._gates[name].should_force(active))

    def cycle(self) -> dict:
        """Send everything due this cycle; return a display snapshot."""
        states, devices = self.gamepads.snapshot()
        xbox_state = xbox_wire_values(
            states[XBOX], self.gamepads.reverse_mode)
        drive_active = (
            xbox_state[AXIS_LY] != NEUTRAL_AXIS
            or xbox_state[AXIS_RY] != NEUTRAL_AXIS)
        self._send_stream(
            "xbox", MSG.XBOX_ID, xbox_state, drive_active)
        self.link.send(MSG.N64_ID, states[N64])

        auto_state = self.gamepads.auto_state
        # A mode change is a one-off edge: active for one cycle, then the
        # gate repeats the new value for the burst window.
        self._send_stream(
            "auto_state", MSG.AUTO_STATE_ID,
            {AUTO_STATE_SIGNAL: auto_state},
            auto_state != self._last_auto_state)
        self._last_auto_state = auto_state

        spacemouse_state = self.spacemouse.get_state()
        # Nav jog keys (Left/Right, PageUp/PageDown) synthesize SpaceMouse
        # axes.  The rover latches axes, so holding a key keeps the arm
        # moving until release.
        jog = self.keyboard.jog_axes()
        if jog:
            spacemouse_state = dict(spacemouse_state)
            spacemouse_state.update(jog)
        # Still sent when the device is disconnected: the reader's state is
        # zeroed then, and the release burst tells the rover to stop moving.
        self._send_stream(
            "spacemouse", MSG.SPACEMOUSE_ID, spacemouse_state,
            any(spacemouse_state.values()))

        keyboard_state = None
        if self.keyboard.is_connected():
            keyboard_state = self.keyboard.get_life_state()
            wire_keyboard = keyboard_state
        else:
            wire_keyboard = self.keyboard.life_zero_state()
            self.keyboard.release_all_arm()
        self._send_stream(
            "keyboard", MSG.KEYBOARD_ID, wire_keyboard,
            any(value != NOT_PRESSED for value in wire_keyboard.values()))

        # Arm actions travel as per-action states (0-3) rather than a key
        # bitmask; the basestation owns the key-to-action map.  Lock-all is
        # expanded here into the per-joint pulses the rover understands.
        telemetry = self.telemetry_snapshot()
        arm_state = arm_wire_state(
            self.keyboard.get_arm_state(include_local=True),
            telemetry.get("locked_joints"))
        self._send_stream(
            "arm_state", MSG.ARM_STATE_ID, arm_state,
            any(value != NOT_PRESSED for value in arm_state.values()))

        return {
            "devices": devices,
            "states": states,
            "spacemouse": spacemouse_state,
            "keyboard": keyboard_state,
            "arm_keyboard": self.keyboard.arm_pressed(),
            "drive_speed": self.gamepads.drive_speed,
            "reverse": self.gamepads.reverse_mode,
            "auto_state": self.gamepads.auto_state,
            "simulation": self.link.simulation,
            "telemetry": telemetry,
        }

    def shutdown(self, display):
        log.info("Shutting down...")
        self._heartbeat_stop.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=1.0)
            self._heartbeat_thread = None
        self.link.send_quit()
        if self.simulation is not None:
            self.simulation.stop()
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
    parser = argparse.ArgumentParser(description="SPEX rover basestation")
    parser.add_argument(
        "--sim-inputs", action="store_true",
        help="use on-screen simulated Xbox/N64/SpaceMouse/keyboard inputs")
    parser.add_argument(
        "--real-spacemouse", action="store_true",
        help="with --sim-inputs, read the physical SpaceMouse over HID")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    sim_inputs = args.sim_inputs or env_flag("BASESTATION_SIM_INPUTS")
    real_spacemouse = (args.real_spacemouse
                       or env_flag("BASESTATION_REAL_SPACEMOUSE"))
    station = BaseStation(sim_inputs=sim_inputs,
                          real_spacemouse=real_spacemouse)
    # systemd stops the service with SIGTERM.  Without a handler Python
    # terminates immediately and the control loop's finally block never
    # sends the QUIT message.  Setting the quit event lets the normal
    # shutdown path run.
    signal.signal(
        signal.SIGTERM,
        lambda _signum, _frame: station.request_quit())
    display = create_display(
        simulation=station.link.simulation,
        with_sim_inputs=station.simulation is not None)
    if display.root is not None:
        station.keyboard.bind_tkinter(display.root)
        display.add_mode_listener(station.set_mode)
        # Keep the display in step when the Gazebo Sim Inputs panel (or a
        # sim-control command) changes the mode.
        station.add_mode_listener(display.set_mode_from_control)
        if station.simulation is not None:
            station.simulation.attach(station, display)

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
