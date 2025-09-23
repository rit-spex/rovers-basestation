"""
Refactored XBee Control System for Base Station to be more modular.
"""

import os
import time
import pygame
from pygame.event import Event
from digi.xbee.devices import XBeeDevice, RemoteXBeeDevice, XBee64BitAddress # idk if i know what this is

# Import from parent dir (shared modules)
from .CommandCodes import CONSTANTS
from .JoystickFeedback import Display

# Import from current dir (core modules)
from .heartbeat import HeartbeatManager
from .controller_manager import ControllerManager, InputProcessor
from .communication import CommunicationManager

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
        
        # Init XBee comms
        self.xbee_enabled = True
        self._init_xbee_communication()
        
        # Timing config
        self.frequency = CONSTANTS.TIMING.UPDATE_FREQUENCY
        self.last_message = bytearray()
        
    def _init_xbee_communication(self):
        """
        Initialize XBee comms components.
        """

        if self.xbee_enabled:
            try:
                port = CONSTANTS.COMMUNICATION.DEFAULT_PORT
                baud_rate = CONSTANTS.COMMUNICATION.DEFAULT_BAUD_RATE
                
                self.xbee_device = XBeeDevice(port, baud_rate)
                self.xbee_device.open()
                
                self.remote_xbee = RemoteXBeeDevice(
                    self.xbee_device, 
                    XBee64BitAddress.from_hex_string(CONSTANTS.COMMUNICATION.REMOTE_XBEE_ADDRESS)
                )
                
                # Init managers with XBee devices
                self.heartbeat_manager = HeartbeatManager(self.xbee_device, self.remote_xbee)
                self.communication_manager = CommunicationManager(self.xbee_device, self.remote_xbee)
                
                print("XBee comms init success")
                
            except Exception as e:
                print(f"Failed to init XBee communication: {e}")
                # Should just like poof everything
                self.xbee_enabled = False # this better work D -------------------------------------------
                self.heartbeat_manager = HeartbeatManager()
                self.communication_manager = CommunicationManager()
        else:
            # print("Bruh") D -----------------------------
            self.heartbeat_manager = HeartbeatManager()
            self.communication_manager = CommunicationManager()
    
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

def main():
    """
    Main for XBee control system.
    """
    # Allow controllers to work in background
    os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"
    
    # Init pygame
    pygame.init()
    
    # Create display and control sys
    display = Display()
    xbee_control = XbeeControlRefactored()
    
    print("XBee Control System started - is waiting for input...")
    print(f"Update frequency: {xbee_control.frequency / CONSTANTS.CONVERSION.NS_PER_MS:.1f}ms")
    print(f"Heartbeat interval: {xbee_control.heartbeat_manager.heartbeat_interval / CONSTANTS.CONVERSION.NS_PER_S:.1f}s")

    timer = time.time_ns()
    
    try:
        while not xbee_control.quit:
            # Check if it's time to process an update
            if timer + xbee_control.frequency > time.time_ns():
                # Process events only if we are in the update window
                for event in pygame.event.get():
                    xbee_control.send_command(event)
                    if event.type == pygame.QUIT:
                        xbee_control.quit = True

            # If this literally blows up cpu uncomment:
            # time.sleep(0.001)
            
            # Send updates and handle heartbeat
            xbee_control.update_info()
            
            # Update display
            display.Update_Display2(
                creep=xbee_control.creep_mode, 
                reverse=xbee_control.reverse_mode
            )
            
            # Reset timer for next cycle
            timer = time.time_ns()
            
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

if __name__ == "__main__":
    main()