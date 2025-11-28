"""
Refactored XBee Control System for Base Station to be more modular.
"""

import logging
import os
import threading
import time
from typing import Any, Dict, Optional

import pygame
from pygame.event import Event

from .command_codes import CONSTANTS
from .communication import CommunicationManager
from .controller_manager import ControllerManager, InputProcessor
from .heartbeat import HeartbeatManager
from .tkinter_display import BaseDisplay, create_display

logger = logging.getLogger(__name__)

# Try to import XBee libraries
try:
    from digi.xbee.devices import (
        RemoteXBeeDevice,
        XBee64BitAddress,
        XBeeDevice,
        XBeeException,
    )

    XBEE_AVAILABLE = True
except ImportError:
    logger.info("XBee libraries not available - simulation mode will be used")
    XBEE_AVAILABLE = False
    # Create dummy classes for when XBee is not available
    XBeeDevice = None
    RemoteXBeeDevice = None
    XBee64BitAddress = None
    XBeeException = None

# Local imports already declared above
try:
    from serial import SerialException
except ImportError:
    SerialException = None
# Default gating for periodic info-level update logs.
# If 0, info-level periodic logs are disabled and only debug-level logs are emitted.


def _get_log_every_updates_default() -> int:
    """
    Parse environment variable defensively to avoid ValueError at import time.

    Returns:
        int: The parsed value or 0 if invalid/missing.
    """
    _env_value = os.environ.get("BASESTATION_LOG_EVERY_UPDATES", None)
    if _env_value is None:
        return 0
    try:
        return int(_env_value)
    except ValueError:
        logger.warning(
            "Invalid BASESTATION_LOG_EVERY_UPDATES value '%s' - using default 0",
            _env_value,
        )
        return 0


BASESTATION_LOG_EVERY_UPDATES_DEFAULT = _get_log_every_updates_default()


class BaseStation:
    """
    BaseStation control system with modular architecture.
    Separates concerns into specific managers for better organization.
    """

    def __init__(self, log_summary_every: Optional[int] = None):
        """
        Initializes the BaseStation control sys with all its modules.

        Args:
            log_summary_every (Optional[int]): Configure how often INFO-level
                update summary messages should be emitted; default is read from
                environment variable BASESTATION_LOG_EVERY_UPDATES or the
                module-level default. If 0, only DEBUG-level messages are
                emitted for per-update logs.
        """

        # Use Event to coordinate quit across threads for memory-safety and atomic semantics.
        # visibility issues across threads.
        self._quit_event = threading.Event()
        self.update_loop = 0

        # Init modular components
        self.controller_manager = ControllerManager()
        self.input_processor = InputProcessor(self.controller_manager)

        # Init XBee comms - disabled if in simulation mode
        self.simulation_mode = CONSTANTS.SIMULATION_MODE
        self.xbee_enabled = XBEE_AVAILABLE and not self.simulation_mode
        self._init_xbee_communication()

        # Timing config
        self.frequency = CONSTANTS.TIMING.UPDATE_FREQUENCY
        self.last_message = bytearray()

        # Telemetry system
        self.telemetry_data: Dict[str, Any] = {}
        self._telemetry_lock = threading.RLock()
        self._setup_telemetry_handlers()
        # Log gating: controls INFO-level update summary frequency (BASESTATION_LOG_EVERY_UPDATES); 0 disables periodic INFO logs.
        if log_summary_every is None:
            # Use module-level default, which may be configured by env var
            self.log_summary_every = max(0, BASESTATION_LOG_EVERY_UPDATES_DEFAULT)
        else:
            self.log_summary_every = max(0, int(log_summary_every))

        # Lock to protect log gating counters and avoid races with the control loop thread.
        self._log_lock = threading.Lock()

    def _create_xbee_device(self):
        """Create and open XBee device."""
        if XBeeDevice is None:
            raise ImportError("XBeeDevice class not available")

        port = CONSTANTS.COMMUNICATION.DEFAULT_PORT
        baud_rate = CONSTANTS.COMMUNICATION.DEFAULT_BAUD_RATE

        device = XBeeDevice(port, baud_rate)
        device.open()
        return device

    def _create_remote_xbee(self):
        """Create remote XBee device reference."""
        if RemoteXBeeDevice is None or XBee64BitAddress is None:
            raise ImportError("XBee classes not properly imported")

        return RemoteXBeeDevice(
            self.xbee_device,
            XBee64BitAddress.from_hex_string(
                CONSTANTS.COMMUNICATION.REMOTE_XBEE_ADDRESS
            ),
        )

    def _log_xbee_init_error(self, e):
        """Log XBee initialization error with appropriate detail level."""
        if XBeeException is not None and isinstance(e, XBeeException):
            logger.warning(
                "XBee initialization failed (XBeeException); falling back to simulation: %s",
                e,
                exc_info=True,
            )
        elif SerialException is not None and isinstance(e, SerialException):
            logger.warning(
                "Serial port error while initializing XBee (SerialException) - check port and permissions: %s",
                e,
                exc_info=True,
            )
        elif isinstance(e, OSError):
            logger.warning(
                "OS-level error while initializing XBee (e.g., timeout/permission/port not found): %s",
                e,
                exc_info=True,
            )
        else:
            logger.exception("Unexpected error during XBee initialization: %s", e)

    def _init_simulation_mode(self):
        """Initialize communication in simulation mode."""
        if self.simulation_mode:
            logger.info("SIMULATION MODE - Using UDP communication for testing")
        else:
            logger.info("XBee libraries not available - running in simulation mode")

        self.communication_manager = CommunicationManager(
            xbee_device=None, remote_xbee=None, simulation_mode=True
        )
        self.heartbeat_manager = HeartbeatManager(self.communication_manager)

    def _init_xbee_communication(self):
        """
        Initialize XBee comms components.
        """
        if not (self.xbee_enabled and XBEE_AVAILABLE and XBeeDevice is not None):
            self._init_simulation_mode()
            return

        try:
            self.xbee_device = self._create_xbee_device()
            self.remote_xbee = self._create_remote_xbee()

            self.communication_manager = CommunicationManager(
                self.xbee_device, self.remote_xbee, simulation_mode=False
            )
            self.heartbeat_manager = HeartbeatManager(self.communication_manager)
            logger.info("XBee comms init success")

        except Exception as e:
            self._log_xbee_init_error(e)
            self.xbee_enabled = False
            self._init_simulation_mode()

    def _setup_telemetry_handlers(self):
        """
        Setup telemetry data handlers for simulation mode.
        """
        # Only simulation communication manager has this method
        try:
            # Use getattr with default to avoid type checker issues
            register_handler = getattr(
                self.communication_manager, "register_telemetry_handler", None
            )
            if register_handler:
                register_handler(self._handle_telemetry_data)
        except (AttributeError, TypeError):
            # Regular CommunicationManager doesn't have telemetry handlers
            pass

    def set_log_summary_every(self, n: int) -> None:
        """Configure the periodic gating for INFO-level update summaries.

        Args:
            n: If > 0, an INFO-level log will be emitted every n updates; if 0,
               only DEBUG-level logs are used.
        """
        with self._log_lock:
            self.log_summary_every = max(0, int(n))

    def _handle_telemetry_data(self, telemetry: dict):
        """
        Handle received telemetry data.

        Args:
            telemetry: Telemetry data dictionary
        """
        with self._telemetry_lock:
            self.telemetry_data.update(telemetry)

    def get_telemetry_data(self) -> dict:
        """
        Get current telemetry data.

        Returns:
            Dictionary of telemetry data
        """
        with self._telemetry_lock:
            return self.telemetry_data.copy()

    @property
    def quit(self) -> bool:
        return self._quit_event.is_set()

    @quit.setter
    def quit(self, value: bool):
        if value:
            self._quit_event.set()
        else:
            self._quit_event.clear()

    def _has_handler(self, obj, method_name):
        """Check if object has a callable handler method."""
        return hasattr(obj, method_name) and callable(getattr(obj, method_name))

    def _dispatch_hotplug_event(self, event):
        """Dispatch controller hotplug events (add/remove)."""
        if event.type == pygame.JOYDEVICEADDED:
            if self._has_handler(self.controller_manager, "handle_controller_added"):
                self.controller_manager.handle_controller_added(event)
            else:
                self._handle_controller_hotplug(event)
        elif event.type == pygame.JOYDEVICEREMOVED:
            if self._has_handler(self.controller_manager, "handle_controller_removed"):
                self.controller_manager.handle_controller_removed(event)
            else:
                self._handle_controller_hotplug(event)

    def _dispatch_axis_event(self, event):
        """Dispatch axis motion event."""
        if self._has_handler(self.controller_manager, "handle_axis_motion"):
            self.controller_manager.handle_axis_motion(event)
        else:
            self._handle_axis_motion(event)

    def _dispatch_button_event(self, event):
        """Dispatch button press/release event."""
        if event.type == pygame.JOYBUTTONDOWN and self._has_handler(
            self.controller_manager, "handle_button_down"
        ):
            self.controller_manager.handle_button_down(event)
        elif event.type == pygame.JOYBUTTONUP and self._has_handler(
            self.controller_manager, "handle_button_up"
        ):
            self.controller_manager.handle_button_up(event)
        else:
            self._handle_button_event(event)

    def _dispatch_joypad_event(self, event):
        """Dispatch joypad/D-pad motion event."""
        if self._has_handler(self.controller_manager, "handle_joypad"):
            self.controller_manager.handle_joypad(event)
        else:
            self._handle_joypad_motion(event)

    def send_command(self, new_event: Event):
        """
        Process controller events and update sys state.

        Args:
            new_event: Pygame event that you wanna process
        """
        # Skip if no controllers are connected and not a device event
        if (
            not self.controller_manager.has_joysticks()
            and new_event.type != pygame.JOYDEVICEADDED
        ):
            return None

        # Route events to ControllerManager if possible, otherwise fall back to internal handlers or InputProcessor; map event types to dispatch functions.
        event_handlers = {
            pygame.JOYDEVICEADDED: self._dispatch_hotplug_event,
            pygame.JOYDEVICEREMOVED: self._dispatch_hotplug_event,
            pygame.JOYAXISMOTION: self._dispatch_axis_event,
            pygame.JOYBUTTONDOWN: self._dispatch_button_event,
            pygame.JOYBUTTONUP: self._dispatch_button_event,
            pygame.JOYHATMOTION: self._dispatch_joypad_event,
        }

        handler = event_handlers.get(new_event.type)
        if handler:
            handler(new_event)
        return None

    # _ before the name cause internal use im so good at organization dawg CHECK -------------
    def _handle_controller_hotplug(self, event: Event):
        """
        Handle controller connection/disconnection.
        """
        should_quit = self.controller_manager.handle_hotplug_event(event)
        if should_quit:
            logger.info("Controller hotplug event triggered quit")
            self.quit = True  # would be a good meme REM ---------

    def _handle_axis_motion(self, event: Event):
        """
        Handle joystick axis motion events.
        """
        # Check if is either joystick axis or trigger axis
        if event.axis in [
            CONSTANTS.XBOX.JOYSTICK.AXIS_LX,
            CONSTANTS.XBOX.JOYSTICK.AXIS_LY,
            CONSTANTS.XBOX.JOYSTICK.AXIS_RX,
            CONSTANTS.XBOX.JOYSTICK.AXIS_RY,
        ]:
            self.input_processor.process_joystick_axis(event)
        else:
            self.input_processor.process_trigger_axis(event)

    def _handle_button_event(self, event: Event):
        """
        Handle button press/release events.
        """
        self.input_processor.process_button(event)

        # If quit button then death
        if self.controller_manager.should_quit_on_button(event):
            logger.info("Quit button pressed on controller %s", event.instance_id)
            self.quit = True

    def _handle_joypad_motion(self, event: Event):
        """
        Handle Dpad/joypad motion events.
        """
        self.input_processor.process_joypad(event)

    def update_info(self):
        """
        Update and send controller information to the rover.
        Handles heartbeat, controller data sending, and sys updates.
        """
        with self._log_lock:
            self.update_loop += 1
        self._update_heartbeat_if_due()
        self._send_controller_data_if_available()

    def _update_heartbeat_if_due(self):
        """Update heartbeat via the HeartbeatManager and optionally log.

        Kept as a short helper to isolate heartbeat logic and reduce the cognitive
        complexity of update_info.
        """
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
        """Send controller data via the CommunicationManager and optionally log.

        Isolating this logic makes update_info simpler and reduces overall
        cognitive complexity.
        """
        if not self.communication_manager:
            return

        xbox_values = self.controller_manager.controller_state.get_controller_values(
            CONSTANTS.XBOX.NAME
        )
        n64_values = self.controller_manager.controller_state.get_controller_values(
            CONSTANTS.N64.NAME
        )

        message_sent = self.communication_manager.send_controller_data(
            xbox_values,
            n64_values,
            self.controller_manager.reverse_mode,
        )

        if not message_sent:
            return

        logger.debug("Controller data sent (update #%d)", self.update_loop)
        with self._log_lock:
            if (
                self.log_summary_every > 0
                and self.update_loop % self.log_summary_every == 0
            ):
                logger.info("Controller data sent (update #%d)", self.update_loop)

    def send_quit_message(self):
        """
        Send quit message to the rover when shutting down.
        """
        if self.communication_manager:
            self.communication_manager.send_quit_message()

    def cleanup(self, display: Optional[BaseDisplay]):
        """
        Clean up resources when shutting down.
        """
        self._cleanup_xbee_device()
        self._cleanup_communication_manager()
        self._cleanup_display(display)

    def _cleanup_xbee_device(self):
        """Close the XBee device (if present) with robust error handling."""
        if not (self.xbee_enabled and hasattr(self, "xbee_device")):
            return
        try:
            self.xbee_device.close()
            logger.info("XBee device closing success")
        except Exception:
            logger.exception("Error closing XBee device")

    def _cleanup_communication_manager(self):
        """Call cleanup on the communication manager if it supports one."""
        cleanup_fn = getattr(self.communication_manager, "cleanup", None)
        if not callable(cleanup_fn):
            return
        try:
            cleanup_fn()
        except Exception:
            logger.exception("Error during communication manager cleanup")

    def _cleanup_display(self, display: Optional[BaseDisplay]):
        """Quit the display cleanly if it's present and supports quit()."""
        if not display or not hasattr(display, "quit"):
            return
        try:
            display.quit()
        except Exception:
            logger.exception("Error quitting display")

    @property  # For readonly and make it accessible like an attribute
    def creep_mode(self) -> bool:
        """
        Get the current creep mode state.
        """
        return self.controller_manager.creep_mode

    @property
    def reverse_mode(self) -> bool:
        """
        Get the current reverse mode state.
        """
        return self.controller_manager.reverse_mode


def _process_controller_events(base_station, display):
    """
    Process pygame controller events and update display.
    """
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            logger.info("Pygame QUIT event received")
            base_station.quit = True
        else:
            base_station.send_command(event)

            # Update display with controller info
            if event.type == pygame.JOYDEVICEADDED:
                controller = pygame.joystick.Joystick(event.device_index)
                controller.init()
                controller_info = {
                    "name": controller.get_name(),
                    "guid": controller.get_guid(),
                    "id": controller.get_instance_id(),
                }
                display.update_controller_display(
                    controller.get_instance_id(), controller_info
                )


def _update_display_data(base_station, display, update_count):
    """
    Update all display data with current system state.
    """
    # Update display with current status
    display.update_modes(
        creep=base_station.creep_mode, reverse=base_station.reverse_mode
    )
    display.update_communication_status(base_station.xbee_enabled, update_count)

    # Update controller values if available
    if hasattr(base_station.controller_manager, "controller_state"):
        xbox_values = (
            base_station.controller_manager.controller_state.get_controller_values(
                CONSTANTS.XBOX.NAME
            )
        )
        display.update_controller_values(xbox_values)

    # Update telemetry display
    telemetry = base_station.get_telemetry_data()
    if telemetry:
        display.update_telemetry(telemetry)


def _should_run_update(current_time, timer, frequency):
    """Check if enough time has passed for the next update."""
    return current_time >= timer + frequency


def _run_update_cycle(base_station, display, update_count):
    """Run a single update cycle and return new update count."""
    # Process controller events
    _process_controller_events(base_station, display)

    # Send updates and handle heartbeat
    base_station.update_info()
    update_count += 1

    # Update display
    _update_display_data(base_station, display, update_count)

    return update_count


def _handle_recoverable_error(exc):
    """Handle recoverable control loop errors."""
    logger.warning(
        "Recoverable control loop error (continuing): %s",
        exc,
        exc_info=True,
    )
    # Back off briefly to avoid hot loop if errors repeat
    time.sleep(0.1)


def _handle_fatal_error(base_station):
    """Handle fatal control loop errors."""
    logger.exception("Fatal error during control loop update; initiating shutdown")
    base_station.quit = True


def _handle_shutdown_signal(base_station):
    """Handle shutdown signals (KeyboardInterrupt, SystemExit)."""
    logger.info("Shutdown requested by user/system")
    base_station.quit = True


def _handle_fatal_loop_error(base_station):
    """Handle fatal errors that escape inner exception handlers."""
    logger.exception("Fatal error in control loop; initiating shutdown")
    base_station.quit = True


def _cleanup_on_exit(base_station, display):
    """Perform cleanup on loop exit."""
    logger.info("Quitting - Now cleaning...")
    base_station.send_quit_message()
    base_station.cleanup(display)
    pygame.quit()
    logger.info("Cleanup complete")


def _process_single_iteration(base_station, display, timer, update_count):
    """Process a single control loop iteration. Returns (new_timer, new_update_count, should_break)."""
    current_time = time.time_ns()

    # Check if enough time has passed for the next update
    if not _should_run_update(current_time, timer, base_station.frequency):
        time.sleep(0.001)
        return (timer, update_count, False)

    # Run the core update operations in a guarded block
    try:
        update_count = _run_update_cycle(base_station, display, update_count)
        return (current_time, update_count, False)
    except (OSError, pygame.error) as exc:
        _handle_recoverable_error(exc)
        return (timer, update_count, False)
    except Exception:
        _handle_fatal_error(base_station)
        return (timer, update_count, True)


def _create_control_loop(base_station, display):
    """
    Create the main control loop function.
    """

    def control_loop():
        timer = time.time_ns()
        update_count = 0

        try:
            while not base_station.quit:
                timer, update_count, should_break = _process_single_iteration(
                    base_station, display, timer, update_count
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


def main():
    """
    Main entry point for XBee control system with tkinter display.
    """
    # Allow controllers to work in background
    os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"

    # Init pygame for only the controller inputs
    pygame.init()

    # Create display and control sys. This may return a headless display if running without a GUI.
    display = create_display()
    base_station = BaseStation()

    logger.info("BaseStation Control System started - is waiting for input...")
    logger.info(
        "Update frequency: %.1fms",
        base_station.frequency / CONSTANTS.CONVERSION.NS_PER_MS,
    )
    logger.info(
        "Heartbeat interval: %.1fs",
        base_station.heartbeat_manager.get_interval() / CONSTANTS.CONVERSION.NS_PER_S,
    )

    # Set initial display state
    if hasattr(display, "update_communication_status"):
        display.update_communication_status(base_station.xbee_enabled, 0)
    # Update display with initial mode flags (show creep mode enabled on startup)
    if hasattr(display, "update_modes"):
        display.update_modes(
            creep=base_station.creep_mode, reverse=base_station.reverse_mode
        )

    # Create and start control loop in separate thread
    control_loop = _create_control_loop(base_station, display)
    control_thread = threading.Thread(target=control_loop, daemon=True)
    control_thread.start()
    # Run GUI main loop (blocks) or wait in headless mode
    # Run GUI main loop (blocks) or wait in headless mode
    try:
        if getattr(display, "headless", False):
            # If headless, keep the main thread alive until quit
            try:
                while not base_station.quit:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                # Re-raise to ensure the interpreter exits as expected
                base_station.quit = True
                raise
        else:
            # GUI blocking call
            display.run()
    except (KeyboardInterrupt, SystemExit) as exc:
        # Re-raise SystemExit/KeyboardInterrupt after logging to allow normal interpreter exit; finally block ensures graceful shutdown.
        logger.info("Shutdown requested by main thread: %s", exc)
        base_station.quit = True
        raise
    except Exception:
        # For other exceptions, log and re-raise after signalling quit; finally block will join threads and allow propagation.
        logger.exception("Unhandled exception in main GUI loop; shutting down")
        base_station.quit = True
        raise
    finally:
        # Wait for control thread to finish, but use a timeout to avoid indefinite blocking
        join_timeout_seconds = 3.0
        control_thread.join(timeout=join_timeout_seconds)
        if control_thread.is_alive():
            logger.warning(
                "Control thread did not exit within %.1f seconds; proceeding with shutdown",
                join_timeout_seconds,
            )
        # Any exceptions are re-raised in their except handlers above; no
        # deferred re-raise is necessary here.


if __name__ == "__main__":
    main()
