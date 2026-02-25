"""
BaseStation application – the main orchestrator.

This module ties together the controller, communication, display, and
protocol subsystems into a single control loop.

STARTUP FLOW
-------------
main()  →  create_display()  →  BaseStation()  →  control_loop thread
    →  display.run() blocks on  main thread (GUI) or sleep (headless)

CONTROL LOOP (runs at ~TIMING.UPDATE_FREQUENCY)
------------------------------------------------
1.  poll_events()  from InputEventSource
2.  send_command()  routes each event to ControllerManager
3.  update_info()   sends heartbeat + controller data via CommunicationManager
4.  _update_display_data()  pushes state to the display
"""

import logging
import os
import threading
import time
from typing import Any, Dict, Optional

from xbee.communication.heartbeat import HeartbeatManager
from xbee.communication.manager import CommunicationManager
from xbee.config.constants import CONSTANTS
from xbee.controller.events import (
    JOYAXISMOTION,
    JOYBUTTONDOWN,
    JOYBUTTONUP,
    JOYDEVICEADDED,
    JOYDEVICEREMOVED,
    JOYHATMOTION,
    QUIT,
    InputEvent,
)
from xbee.controller.detection import detect_controller_type
from xbee.controller.input_source import InputEventSource, InputSourceError
from xbee.controller.manager import ControllerManager, InputProcessor
from xbee.controller.spacemouse import SpaceMouse
from xbee.display.base import BaseDisplay, create_display

logger = logging.getLogger(__name__)

_TRIGGER_AXES = frozenset(
    (CONSTANTS.XBOX.TRIGGER.AXIS_LT, CONSTANTS.XBOX.TRIGGER.AXIS_RT)
)
_HOTPLUG_EVENTS = (JOYDEVICEADDED, JOYDEVICEREMOVED)

# Sentinel controller ID used in the GUI's controllers dict for the
# SpaceMouse (which doesn't come via the ``inputs`` gamepad pipeline).
_SPACEMOUSE_DISPLAY_ID = -1

# ---------------------------------------------------------------------------
# XBee hardware (optional)
# ---------------------------------------------------------------------------

try:
    from digi.xbee.devices import (
        RemoteXBeeDevice,
        XBee64BitAddress,
        XBeeDevice,
        XBeeException,
    )

    XBEE_AVAILABLE = True
except ImportError:
    logger.info("XBee libraries not available – simulation mode will be used")
    XBEE_AVAILABLE = False
    XBeeDevice = None
    RemoteXBeeDevice = None
    XBee64BitAddress = None
    XBeeException = None

try:
    from serial import SerialException
except ImportError:
    SerialException = None


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------


def _get_log_every_updates_default() -> int:
    """Parse BASESTATION_LOG_EVERY_UPDATES env var (default 0 = debug only)."""
    raw = os.environ.get("BASESTATION_LOG_EVERY_UPDATES")
    if raw is None:
        return 0
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid BASESTATION_LOG_EVERY_UPDATES '%s' – using 0", raw)
        return 0


def _is_pytest_running() -> bool:
    """Return True when executing under pytest."""
    try:
        import sys

        return "pytest" in sys.modules
    except Exception:
        return False


BASESTATION_LOG_EVERY_UPDATES_DEFAULT = _get_log_every_updates_default()


# ---------------------------------------------------------------------------
# BaseStation
# ---------------------------------------------------------------------------


class BaseStation:
    """Central orchestrator that wires together controllers, comms, and display.

    Args:
        log_summary_every: How often to emit INFO-level update summaries.
            0 = debug only.  ``None`` reads from env.
        input_source: Override the default InputEventSource (useful in tests).
    """

    def __init__(
        self,
        log_summary_every: Optional[int] = None,
        input_source: Optional[InputEventSource] = None,
    ):
        self._quit_event = threading.Event()
        self.update_loop = 0

        # Controller subsystem
        self.controller_manager = ControllerManager()
        self.input_processor = InputProcessor(self.controller_manager)
        self.input_source = input_source or InputEventSource()

        # SpaceMouse (6DOF HID device – independent of gamepad input pipeline)
        self._spacemouse_disconnect_pending = threading.Event()
        self.spacemouse = SpaceMouse(
            on_disconnect=self._on_spacemouse_disconnect
        )
        self.spacemouse.start()

        # Communication subsystem
        self.simulation_mode = CONSTANTS.SIMULATION_MODE
        self.xbee_enabled = XBEE_AVAILABLE and not self.simulation_mode
        self._init_xbee_communication()

        # Timing
        self.frequency = CONSTANTS.TIMING.UPDATE_FREQUENCY
        self.last_message = bytearray()

        # Telemetry
        self.telemetry_data: Dict[str, Any] = {}
        self._last_telemetry_received_at: Optional[float] = None
        self._telemetry_lock = threading.RLock()
        self._setup_telemetry_handlers()

        # Log gating
        if log_summary_every is None:
            self.log_summary_every = max(0, BASESTATION_LOG_EVERY_UPDATES_DEFAULT)
        else:
            self.log_summary_every = max(0, int(log_summary_every))
        self._log_lock = threading.Lock()

    # ------------------------------------------------------------------
    # SpaceMouse callbacks
    # ------------------------------------------------------------------

    def _on_spacemouse_disconnect(self) -> None:
        """Called from the SpaceMouse background thread when the device is lost."""
        self._spacemouse_disconnect_pending.set()
        logger.info("SpaceMouse HID device disconnected")

    # ------------------------------------------------------------------
    # XBee initialization
    # ------------------------------------------------------------------

    def _create_xbee_device(self):
        if XBeeDevice is None:
            raise ImportError("XBeeDevice class not available")
        port = CONSTANTS.COMMUNICATION.DEFAULT_PORT
        baud_rate = CONSTANTS.COMMUNICATION.DEFAULT_BAUD_RATE
        device = XBeeDevice(port, baud_rate)
        device.open()
        return device

    def _should_skip_xbee_init(self) -> bool:
        port = CONSTANTS.COMMUNICATION.DEFAULT_PORT
        if not isinstance(port, str) or not port:
            logger.info("Skipping XBee init: invalid port (%r); using simulation", port)
            return True

        if _is_pytest_running():
            return False

        if os.name == "nt" and port.startswith("/dev/"):
            logger.info(
                "Skipping XBee init: %s not valid on Windows; using simulation", port
            )
            return True
        if port.startswith("/dev/") and not os.path.exists(port):
            logger.info("Skipping XBee init: %s not found; using simulation", port)
            return True
        return False

    def _create_remote_xbee(self):
        if RemoteXBeeDevice is None or XBee64BitAddress is None:
            raise ImportError("XBee classes not properly imported")
        return RemoteXBeeDevice(
            self.xbee_device,
            XBee64BitAddress.from_hex_string(
                CONSTANTS.COMMUNICATION.REMOTE_XBEE_ADDRESS
            ),
        )

    def _log_xbee_init_error(self, e):
        if XBeeException is not None and isinstance(e, XBeeException):
            logger.warning("XBee init failed (XBeeException): %s", e, exc_info=True)
        elif SerialException is not None and isinstance(e, SerialException):
            logger.warning("Serial port error during XBee init: %s", e, exc_info=True)
        elif isinstance(e, OSError):
            logger.warning("OS-level error during XBee init: %s", e, exc_info=True)
        else:
            logger.exception("Unexpected error during XBee init: %s", e)

    def _init_simulation_mode(self):
        if self.simulation_mode:
            logger.info("SIMULATION MODE – Using UDP communication")
        else:
            logger.info("XBee unavailable – running in simulation mode")
        self.communication_manager = CommunicationManager(
            xbee_device=None, remote_xbee=None, simulation_mode=True
        )
        self.heartbeat_manager = HeartbeatManager(self.communication_manager)

    def _init_xbee_communication(self):
        if not (self.xbee_enabled and XBEE_AVAILABLE and XBeeDevice is not None):
            self._init_simulation_mode()
            return
        if self._should_skip_xbee_init():
            self.xbee_enabled = False
            self._init_simulation_mode()
            return
        try:
            self.xbee_device = self._create_xbee_device()
            self.remote_xbee = self._create_remote_xbee()
            self.communication_manager = CommunicationManager(
                self.xbee_device, self.remote_xbee, simulation_mode=False
            )
            self.heartbeat_manager = HeartbeatManager(self.communication_manager)
            logger.info("XBee comms initialised successfully")
        except Exception as e:
            self._log_xbee_init_error(e)
            # If device opened but remote setup failed, close it before falling back.
            if getattr(self, "xbee_device", None) is not None:
                try:
                    self.xbee_device.close()
                except Exception:
                    logger.exception(
                        "Failed to close partially initialized XBee device"
                    )
            self.xbee_enabled = False
            self._init_simulation_mode()

    def _setup_telemetry_handlers(self):
        register_handler = getattr(
            self.communication_manager, "register_telemetry_handler", None
        )
        if register_handler:
            register_handler(self._handle_telemetry_data)

    # ------------------------------------------------------------------
    # Telemetry
    # ------------------------------------------------------------------

    def _handle_telemetry_data(self, telemetry: dict):
        received_at = time.time()
        with self._telemetry_lock:
            self.telemetry_data.update(telemetry)
            self._last_telemetry_received_at = received_at
            self.telemetry_data["_received_at"] = received_at

    def get_telemetry_data(self) -> dict:
        with self._telemetry_lock:
            return self.telemetry_data.copy()

    # ------------------------------------------------------------------
    # Quit flag
    # ------------------------------------------------------------------

    @property
    def quit(self) -> bool:
        return self._quit_event.is_set()

    @quit.setter
    def quit(self, value: bool):
        if value:
            self._quit_event.set()
        else:
            self._quit_event.clear()

    # ------------------------------------------------------------------
    # Log gating
    # ------------------------------------------------------------------

    def set_log_summary_every(self, n: int) -> None:
        with self._log_lock:
            self.log_summary_every = max(0, int(n))

    # ------------------------------------------------------------------
    # Event dispatch (called once per input event)
    # ------------------------------------------------------------------

    def send_command(self, event: InputEvent):
        """Route a single input event to the appropriate handler."""
        if (
            not self.controller_manager.has_joysticks()
            and event.type not in _HOTPLUG_EVENTS
        ):
            return

        if event.type == JOYDEVICEADDED:
            if self.controller_manager.handle_controller_added(event):
                self.quit = True
        elif event.type == JOYDEVICEREMOVED:
            if self.controller_manager.handle_controller_removed(event):
                self.quit = True
        elif event.type == JOYAXISMOTION:
            self.controller_manager.handle_axis_motion(event)
        elif event.type == JOYBUTTONDOWN:
            self.controller_manager.handle_button_down(event)
        elif event.type == JOYBUTTONUP:
            self.controller_manager.handle_button_up(event)
        elif event.type == JOYHATMOTION:
            self.controller_manager.handle_joypad(event)

    # ------------------------------------------------------------------
    # Internal event handlers (fallbacks)
    # ------------------------------------------------------------------

    def _handle_controller_hotplug(self, event: InputEvent):
        result = False
        handler = getattr(self.controller_manager, "handle_hotplug_event", None)
        if handler:
            result = handler(event)
        if result:
            logger.info("Controller hotplug triggered quit")
            self.quit = True

    def _handle_axis_motion(self, event: InputEvent):
        axis = getattr(event, "axis", None)
        if axis is None:
            return
        if axis in _TRIGGER_AXES:
            self.input_processor.process_trigger_axis(event)
        else:
            self.input_processor.process_joystick_axis(event)

    def _handle_button_event(self, event: InputEvent):
        self.input_processor.process_button(event)
        should_quit = getattr(self.controller_manager, "should_quit_on_button", None)
        if should_quit and should_quit(event):
            logger.info("Button event triggered quit")
            self.quit = True

    def _handle_joypad_motion(self, event: InputEvent):
        self.input_processor.process_joypad(event)

    # ------------------------------------------------------------------
    # Periodic update (called every cycle)
    # ------------------------------------------------------------------

    def update_info(self):
        """Send heartbeat + controller data to the rover."""
        with self._log_lock:
            self.update_loop += 1
        self._update_heartbeat_if_due()
        self._send_controller_data_if_available()
        self._send_auto_state_if_available()

    def _update_heartbeat_if_due(self):
        if not self.heartbeat_manager:
            return
        heartbeat_sent = self.heartbeat_manager.update()
        if not heartbeat_sent:
            return
        logger.debug("Heartbeat sent (update #%d)", self.update_loop)
        with self._log_lock:
            if (
                self.log_summary_every > 0
                and self.update_loop % self.log_summary_every == 0
            ):
                logger.info("Heartbeat sent (update #%d)", self.update_loop)

    def _send_controller_data_if_available(self):
        if not self.communication_manager:
            return
        xbox_values = self.controller_manager.controller_state.get_controller_values(
            CONSTANTS.XBOX.NAME
        )
        n64_values = self.controller_manager.controller_state.get_controller_values(
            CONSTANTS.N64.NAME
        )
        self.communication_manager.send_controller_data(
            xbox_values,
            n64_values,
            self.controller_manager.reverse_mode,
        )

        # SpaceMouse is sent independently of Xbox/N64 (different message ID)
        sm_connected = self.spacemouse.is_connected()
        if sm_connected:
            # Discard any stale disconnect flag (device reconnected before
            # we processed the disconnect in the control loop).
            self._spacemouse_disconnect_pending.clear()
            sm_state = self.spacemouse.get_state()
            self.communication_manager.send_spacemouse_data(sm_state)
        elif self._spacemouse_disconnect_pending.is_set():
            # SpaceMouse just disconnected – send all-zeros so the rover
            # stops whatever the SpaceMouse was controlling.
            self._spacemouse_disconnect_pending.clear()
            zero_state = SpaceMouse._zero_state()
            self.communication_manager.send_spacemouse_data(zero_state)
            # Clear dedup cache so the first real data after reconnect is
            # guaranteed to be sent even if it happens to equal all-zeros.
            self.communication_manager.clear_spacemouse_dedup()
            logger.info("SpaceMouse disconnected – sent zero state to rover")
        with self._log_lock:
            if (
                self.log_summary_every > 0
                and self.update_loop % self.log_summary_every == 0
            ):
                logger.info("Controller data sent (update #%d)", self.update_loop)

    def _send_auto_state_if_available(self):
        if not self.communication_manager:
            return
        auto_state = getattr(self.controller_manager, "auto_state", None)
        if auto_state is None:
            return
        try:
            self.communication_manager.send_auto_state(int(auto_state))
        except Exception:
            logger.exception("Failed to send auto-state message")

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def send_quit_message(self):
        if self.communication_manager:
            self.communication_manager.send_quit_message()

    def cleanup(self, display: Optional[BaseDisplay]):
        self._cleanup_xbee_device()
        self._cleanup_communication_manager()
        self._cleanup_display(display)
        self._cleanup_input_source()

    def _cleanup_xbee_device(self):
        xbee_device = getattr(self, "xbee_device", None)
        if xbee_device is None:
            return
        try:
            xbee_device.close()
            logger.info("XBee device closed")
        except Exception:
            logger.exception("Error closing XBee device")

    def _cleanup_communication_manager(self):
        cleanup_fn = getattr(self.communication_manager, "cleanup", None)
        if callable(cleanup_fn):
            try:
                cleanup_fn()
            except Exception:
                logger.exception("Error during communication manager cleanup")

    def _cleanup_display(self, display: Optional[BaseDisplay]):
        if display and hasattr(display, "quit"):
            try:
                display.quit()
            except Exception:
                logger.exception("Error quitting display")

    def _cleanup_input_source(self):
        if getattr(self, "input_source", None):
            try:
                self.input_source.stop()
            except Exception:
                logger.exception("Error stopping input source")
        if getattr(self, "spacemouse", None):
            try:
                self.spacemouse.stop()
            except Exception:
                logger.exception("Error stopping SpaceMouse")

    # ------------------------------------------------------------------
    # Mode properties
    # ------------------------------------------------------------------

    @property
    def creep_mode(self) -> bool:
        return self.controller_manager.creep_mode

    @property
    def reverse_mode(self) -> bool:
        return self.controller_manager.reverse_mode


# ---------------------------------------------------------------------------
# Control-loop helpers (module-level to keep BaseStation lean)
# ---------------------------------------------------------------------------


def _process_controller_events(base_station: BaseStation, display: BaseDisplay):
    for event in base_station.input_source.poll_events():
        if event.type == QUIT:
            logger.info("Input QUIT event received")
            base_station.quit = True
            continue
        base_station.send_command(event)
        if event.type == JOYDEVICEADDED:
            _update_display_on_controller_add(base_station, display, event)


def _update_display_on_controller_add(
    base_station: BaseStation,
    display: BaseDisplay,
    event: InputEvent,
):
    instance_id = getattr(event, "instance_id", None)
    if not isinstance(instance_id, int):
        return

    # If the OS enumerates the SpaceMouse as a gamepad, skip adding it
    # to the display here — it is managed by the dedicated HID reader
    # in _update_display_data() instead.
    event_name = getattr(event, "name", "") or ""
    if detect_controller_type(event_name) == CONSTANTS.SPACEMOUSE.NAME:
        return

    controller_info = {
        "name": event_name or "Unknown",
        "guid": getattr(event, "guid", "Unknown"),
        "id": instance_id,
    }

    ctype = None
    try:
        ctype = base_station.controller_manager.get_controller_type(instance_id)
    except Exception:
        pass
    if ctype:
        controller_info["type"] = ctype
    if callable(getattr(display, "update_controller_display", None)):
        display.update_controller_display(instance_id, controller_info)


def _update_display_data(
    base_station: BaseStation,
    display: BaseDisplay,
    update_count: int,
):
    display.update_modes(
        creep=base_station.creep_mode,
        reverse=base_station.reverse_mode,
    )
    xbee_enabled = getattr(base_station, "xbee_enabled", False)
    simulation_mode = getattr(base_station, "simulation_mode", False)
    comm_connected = (xbee_enabled if isinstance(xbee_enabled, bool) else False) or (
        simulation_mode if isinstance(simulation_mode, bool) else False
    )
    display.update_communication_status(comm_connected, update_count)

    if hasattr(base_station.controller_manager, "controller_state"):
        xbox = base_station.controller_manager.controller_state.get_controller_values(
            CONSTANTS.XBOX.NAME
        )
        n64 = base_station.controller_manager.controller_state.get_controller_values(
            CONSTANTS.N64.NAME
        )
        controller_vals: Dict[str, Any] = {
            CONSTANTS.XBOX.NAME: xbox,
            CONSTANTS.N64.NAME: n64,
        }

        # SpaceMouse: add/remove from both the controller list (so the name
        # appears in Controller Info) and the values dict (so 6DOF data is
        # shown instead of Xbox-style axes).
        sm_connected = base_station.spacemouse.is_connected()
        if sm_connected:
            controller_vals[CONSTANTS.SPACEMOUSE.NAME] = (
                base_station.spacemouse.get_state()
            )
            if callable(getattr(display, "update_controller_display", None)):
                display.update_controller_display(
                    _SPACEMOUSE_DISPLAY_ID,
                    {
                        "name": CONSTANTS.SPACEMOUSE.NAME,
                        "guid": "HID",
                        "type": CONSTANTS.SPACEMOUSE.NAME,
                    },
                )
        else:
            # Remove stale SpaceMouse entry from the GUI controller list.
            _remove_spacemouse_from_display(display)

        display.update_controller_values(controller_vals)

    telemetry = base_station.get_telemetry_data()
    if telemetry:
        display.update_telemetry(telemetry)


def _remove_spacemouse_from_display(display: BaseDisplay) -> None:
    """Remove the SpaceMouse entry from the GUI controllers dict, if present."""
    controllers = getattr(display, "controllers", None)
    if not isinstance(controllers, dict):
        return
    if _SPACEMOUSE_DISPLAY_ID not in controllers:
        return
    lock = getattr(display, "_controller_lock", None)
    # Guard against mock objects or displays that lack a real lock.
    try:
        if lock is not None and hasattr(lock, "__enter__"):
            with lock:
                controllers.pop(_SPACEMOUSE_DISPLAY_ID, None)
        else:
            controllers.pop(_SPACEMOUSE_DISPLAY_ID, None)
    except (TypeError, AttributeError):
        controllers.pop(_SPACEMOUSE_DISPLAY_ID, None)


def _should_run_update(current_time, timer, frequency):
    return current_time >= timer + frequency


def _run_update_cycle(
    base_station: BaseStation,
    display: BaseDisplay,
    update_count: int,
) -> int:
    _process_controller_events(base_station, display)
    base_station.update_info()
    update_count += 1
    _update_display_data(base_station, display, update_count)
    return update_count


def _handle_recoverable_error(exc):
    logger.warning(
        "Recoverable control loop error (continuing): %s",
        exc,
        exc_info=True,
    )
    time.sleep(0.1)


def _set_quit_with_exception(base_station, message: str) -> None:
    logger.exception(message)
    base_station.quit = True


def _handle_fatal_error(base_station):
    _set_quit_with_exception(
        base_station,
        "Fatal error during control loop update; initiating shutdown",
    )


def _handle_shutdown_signal(base_station):
    logger.info("Shutdown requested by user/system")
    base_station.quit = True


def _handle_fatal_loop_error(base_station):
    _set_quit_with_exception(
        base_station,
        "Fatal error in control loop; initiating shutdown",
    )


def _cleanup_on_exit(base_station, display):
    logger.info("Quitting - Now cleaning...")
    base_station.send_quit_message()
    base_station.cleanup(display)
    logger.info("Cleanup complete")


def _process_single_iteration(base_station, display, timer, update_count):
    """Returns (new_timer, new_update_count, should_break)."""
    current_time = int(time.time_ns())
    if not _should_run_update(current_time, timer, base_station.frequency):
        time.sleep(0.001)
        return (timer, update_count, False)

    try:
        update_count = _run_update_cycle(base_station, display, update_count)
        return (current_time, update_count, False)
    except (OSError, InputSourceError) as exc:
        _handle_recoverable_error(exc)
        return (timer, update_count, False)
    except Exception:
        _handle_fatal_error(base_station)
        return (timer, update_count, True)


def _create_control_loop(base_station: BaseStation, display: BaseDisplay):
    def control_loop():
        timer = time.time_ns()
        update_count = 0
        try:
            while not base_station.quit:
                timer, update_count, should_break = _process_single_iteration(
                    base_station,
                    display,
                    timer,
                    update_count,
                )
                if should_break:
                    break
        except (KeyboardInterrupt, SystemExit):
            _handle_shutdown_signal(base_station)
            raise
        except Exception:
            _handle_fatal_loop_error(base_station)
        finally:
            _cleanup_on_exit(base_station, display)

    return control_loop


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    """Launch the basestation (GUI or headless)."""
    display = create_display()
    base_station = BaseStation()

    logger.info("BaseStation started – waiting for input…")
    logger.info(
        "Update frequency: %.1fms",
        base_station.frequency / CONSTANTS.CONVERSION.NS_PER_MS,
    )
    logger.info(
        "Heartbeat interval: %.1fs",
        base_station.heartbeat_manager.get_interval() / CONSTANTS.CONVERSION.NS_PER_S,
    )

    if hasattr(display, "update_communication_status"):
        display.update_communication_status(base_station.xbee_enabled, 0)
    if hasattr(display, "update_modes"):
        display.update_modes(
            creep=base_station.creep_mode, reverse=base_station.reverse_mode
        )
    if hasattr(display, "set_simulation_mode"):
        display.set_simulation_mode(not base_station.xbee_enabled)

    control_loop = _create_control_loop(base_station, display)
    control_thread = threading.Thread(target=control_loop, daemon=True)
    control_thread.start()

    try:
        if getattr(display, "headless", False):
            try:
                while not base_station.quit:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                base_station.quit = True
                raise
        else:
            display.run()
            # GUI closed normally: request control-loop shutdown.
            base_station.quit = True
    except (KeyboardInterrupt, SystemExit) as exc:
        logger.info("Shutdown from main thread: %s", exc)
        base_station.quit = True
        raise
    except Exception:
        logger.exception("Unhandled exception in main loop; shutting down")
        base_station.quit = True
        raise
    finally:
        control_thread.join(timeout=3.0)
        if control_thread.is_alive():
            logger.warning("Control thread did not exit within 3s")


if __name__ == "__main__":
    main()
