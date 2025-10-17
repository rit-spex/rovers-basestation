"""
Refactored XBee Control System for Base Station to be more modular.
"""

import os
import time
import pygame
from pygame.event import Event
import threading

# Try to import XBee libraries
try:
    from digi.xbee.devices import XBeeDevice, RemoteXBeeDevice, XBee64BitAddress
    XBEE_AVAILABLE = True
except ImportError:
    print("XBee libraries not available - simulation mode will be used")
    XBEE_AVAILABLE = False
    # Create dummy classes for when XBee is not available
    XBeeDevice = None
    RemoteXBeeDevice = None
    XBee64BitAddress = None

# Import from parent dir (shared modules)
from .CommandCodes import CONSTANTS
from .tkinter_display import TkinterDisplay

# Import from current dir (core modules)
from .heartbeat import HeartbeatManager
from .controller_manager import ControllerManager, InputProcessor
from .communication import CommunicationManager
from .udp_communication import SimulationCommunicationManager
from .message_system import message_codec

class XbeeControlRefactored:
    """
    XBee control system but like modular.
    Separates concerns into specific managers cause organization.
    """

    def __init__(self):
        """
        Initializes the XBee control sys with all its modules.
        """

        # Core flags
        self.quit = False
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
        self.telemetry_data = {}
        self._setup_telemetry_handlers()

    def _init_xbee_communication(self):
        """
        Initialize XBee comms components.
        """

        if self.xbee_enabled and XBEE_AVAILABLE and XBeeDevice is not None:
            try:
                port = CONSTANTS.COMMUNICATION.DEFAULT_PORT
                baud_rate = CONSTANTS.COMMUNICATION.DEFAULT_BAUD_RATE

                self.xbee_device = XBeeDevice(port, baud_rate)
                self.xbee_device.open()

                if RemoteXBeeDevice is not None and XBee64BitAddress is not None:
                    self.remote_xbee = RemoteXBeeDevice(
                        self.xbee_device,
                        XBee64BitAddress.from_hex_string(CONSTANTS.COMMUNICATION.REMOTE_XBEE_ADDRESS)
                    )
                else:
                    raise ImportError("XBee classes not properly imported")

                # Init managers with XBee devices
                self.heartbeat_manager = HeartbeatManager(self.xbee_device, self.remote_xbee)
                self.communication_manager = CommunicationManager(self.xbee_device, self.remote_xbee)

                print("XBee comms init success")

            except Exception as e:
                print(f"Failed to init XBee communication: {e}")
                # Fall back to simulation mode
                self.xbee_enabled = False
                self.heartbeat_manager = HeartbeatManager()
                self.communication_manager = SimulationCommunicationManager()
        else:
            if self.simulation_mode:
                print("SIMULATION MODE - Using UDP communication for testing")
            else:
                print("XBee libraries not available - running in simulation mode")
            self.heartbeat_manager = HeartbeatManager()
            self.communication_manager = SimulationCommunicationManager()

    def _setup_telemetry_handlers(self):
        """
        Setup telemetry data handlers for simulation mode.
        """

        # Only simulation communication manager has this method
        try:
            # Use getattr with default to avoid type checker issues
            register_handler = getattr(self.communication_manager, 'register_telemetry_handler', None)
            if register_handler:
                register_handler(self._handle_telemetry_data)
        except (AttributeError, TypeError):
            # Regular CommunicationManager doesn't have telemetry handlers
            pass

    def _handle_telemetry_data(self, telemetry: dict):
        """
        Handle received telemetry data.

        Args:
            telemetry: Telemetry data dictionary
        """

        self.telemetry_data.update(telemetry)

    def get_telemetry_data(self) -> dict:
        """
        Get current telemetry data.

        Returns:
            Dictionary of telemetry data
        """

        return self.telemetry_data.copy()

    def send_command(self, new_event: Event):
        """
        Process controller events and update sys state.

        Args:
            new_event: Pygame event that you wanna process
        """

        # Skip if no controllers are connected and not a device event
        if (len(self.controller_manager.joysticks.keys()) == 0 and
            new_event.type != pygame.JOYDEVICEADDED):
            return None

        # Route the event to corsponding handler
        event_handlers = {
            pygame.JOYDEVICEADDED: self._handle_controller_hotplug,
            pygame.JOYDEVICEREMOVED: self._handle_controller_hotplug,
            pygame.JOYAXISMOTION: self._handle_axis_motion,
            pygame.JOYBUTTONDOWN: self._handle_button_event,
            pygame.JOYBUTTONUP: self._handle_button_event,
            pygame.JOYHATMOTION: self._handle_joypad_motion,
        }

        handler = event_handlers.get(new_event.type)
        if handler:
            handler(new_event)

    # _ before the name cause internal use im so good at organization dawg CHECK -------------
    def _handle_controller_hotplug(self, event: Event):
        """
        Handle controller connection/disconnection.
        """

        should_quit = self.controller_manager.handle_hotplug_event(event)
        if should_quit:
            print("Controller hotplug event triggered quit")
            self.quit = True # would be a good meme REM ---------

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
            print(f"Quit button pressed on controller {event.instance_id}")
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

        self.update_loop += 1

        # Handle heartbeat
        if self.xbee_enabled and self.heartbeat_manager:
            heartbeat_sent = self.heartbeat_manager.update()
            if heartbeat_sent:
                print(f"Heartbeat sent (update #{self.update_loop})")

        # Send the controller data
        if self.xbee_enabled and self.communication_manager:
            xbox_values = self.controller_manager.controller_state.get_controller_values("xbox")
            n64_values = self.controller_manager.controller_state.get_controller_values("n64")

            message_sent = self.communication_manager.send_controller_data(
                xbox_values,
                n64_values,
                self.controller_manager.reverse_mode
            )

            if message_sent:
                print(f"Controller data sent (update #{self.update_loop})")

    def send_quit_message(self):
        """
        Send quit message to the rover when shutting down.
        """

        if self.xbee_enabled and self.communication_manager:
            self.communication_manager.send_quit_message()

    def cleanup(self):
        """
        Clean up resources when shutting down.
        """

        if self.xbee_enabled and hasattr(self, 'xbee_device'):
            try:
                self.xbee_device.close()
                print("XBee device closing success")
            except Exception as e:
                print(f"Error closing XBee device: {e}")

    @property # For readonly and make it accessible like an attribute
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

def _process_controller_events(xbee_control, display):
    """
    Process pygame controller events and update display.
    """

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            print("Pygame QUIT event received")
            xbee_control.quit = True
        else:
            xbee_control.send_command(event)

            # Update display with controller info
            if event.type == pygame.JOYDEVICEADDED:
                controller = pygame.joystick.Joystick(event.device_index)
                controller.init()
                controller_info = {
                    'name': controller.get_name(),
                    'guid': controller.get_guid(),
                    'id': controller.get_instance_id()
                }
                display.update_controller_display(controller.get_instance_id(), controller_info)

def _update_display_data(xbee_control, display, update_count):
    """
    Update all display data with current system state.
    """

    # Update display with current status
    display.update_modes(
        creep=xbee_control.creep_mode,
        reverse=xbee_control.reverse_mode
    )
    display.update_communication_status(xbee_control.xbee_enabled, update_count)

    # Update controller values if available
    if hasattr(xbee_control.controller_manager, 'controller_state'):
        xbox_values = xbee_control.controller_manager.controller_state.get_controller_values("xbox")
        display.update_controller_values(xbox_values)

    # Update telemetry display
    telemetry = xbee_control.get_telemetry_data()
    if telemetry:
        display.update_telemetry(telemetry)

def _create_control_loop(xbee_control, display):
    """
    Create the main control loop function.
    """

    def control_loop():
        timer = time.time_ns()
        update_count = 0

        try:
            while not xbee_control.quit:
                current_time = time.time_ns()

                # Check if enough time has passed for the next update
                if current_time >= timer + xbee_control.frequency:
                    # Process controller events
                    _process_controller_events(xbee_control, display)

                    # Send updates and handle heartbeat
                    xbee_control.update_info()
                    update_count += 1

                    # Update display
                    _update_display_data(xbee_control, display, update_count)

                    # Reset timer for next cycle
                    timer = current_time

                # Small sleep to prevent CPU spinning
                time.sleep(0.001)

        except KeyboardInterrupt:
            print("\nShutdown by user")
            xbee_control.quit = True

        except Exception as e:
            print(f"\nUnexpected error: {e}")
            xbee_control.quit = True

        finally:
            print("Quitting - Now cleaning...")
            xbee_control.send_quit_message()
            xbee_control.cleanup()
            pygame.quit()
            print("Cleanup complete")

    return control_loop

def main():
    """
    Main for XBee control system with tkinter display.
    """
    # Allow controllers to work in background
    os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"

    # Init pygame for only the controller inputs
    pygame.init()

    # Create display and control sys
    display = TkinterDisplay()
    xbee_control = XbeeControlRefactored()

    print("XBee Control System started - is waiting for input...")
    print(f"Update frequency: {xbee_control.frequency / CONSTANTS.CONVERSION.NS_PER_MS:.1f}ms")
    print(f"Heartbeat interval: {xbee_control.heartbeat_manager.heartbeat_interval / CONSTANTS.CONVERSION.NS_PER_S:.1f}s")

    # Set initial display state
    display.update_communication_status(xbee_control.xbee_enabled, 0)

    # Create and start control loop in separate thread
    control_loop = _create_control_loop(xbee_control, display)
    control_thread = threading.Thread(target=control_loop, daemon=True)
    control_thread.start()

    # Run tkinter main loop (blocks until window is closed)
    try:
        display.run()
    except KeyboardInterrupt:
        xbee_control.quit = True

    # Wait for control thread to finish
    control_thread.join(timeout=2.0)

if __name__ == "__main__":
    main()
