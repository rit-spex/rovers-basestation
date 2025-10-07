"""
Controller management module for handling diff controller types and their inputs.
Seperates controller logic from main XBee comms class.
"""

import pygame
from typing import Dict, Optional
from pygame.event import Event

from .command_codes import CONSTANTS

class ControllerState:
    """
    Manages the state of controller inputs.
    """
    
    def __init__(self):
        """
        Init controller state with default vals.
        """

        self.values = {
            "xbox": {
                # Axis
                CONSTANTS.XBOX.JOYSTICK.AXIS_LX: CONSTANTS.XBOX.JOYSTICK.NEUTRAL_HEX,
                CONSTANTS.XBOX.JOYSTICK.AXIS_LY: CONSTANTS.XBOX.JOYSTICK.NEUTRAL_HEX,
                CONSTANTS.XBOX.JOYSTICK.AXIS_RX: CONSTANTS.XBOX.JOYSTICK.NEUTRAL_HEX,
                CONSTANTS.XBOX.JOYSTICK.AXIS_RY: CONSTANTS.XBOX.JOYSTICK.NEUTRAL_HEX,
                # Buttons
                CONSTANTS.XBOX.TRIGGER.AXIS_LT: CONSTANTS.XBOX.BUTTONS.OFF,
                CONSTANTS.XBOX.TRIGGER.AXIS_RT: CONSTANTS.XBOX.BUTTONS.OFF,
                CONSTANTS.XBOX.BUTTONS.A + 6: CONSTANTS.XBOX.BUTTONS.OFF,
                CONSTANTS.XBOX.BUTTONS.B + 6: CONSTANTS.XBOX.BUTTONS.OFF,
                CONSTANTS.XBOX.BUTTONS.X + 6: CONSTANTS.XBOX.BUTTONS.OFF,
                CONSTANTS.XBOX.BUTTONS.Y + 6: CONSTANTS.XBOX.BUTTONS.OFF,
                CONSTANTS.XBOX.BUTTONS.LEFT_BUMPER + 6: CONSTANTS.XBOX.BUTTONS.OFF,
                CONSTANTS.XBOX.BUTTONS.RIGHT_BUMPER + 6: CONSTANTS.XBOX.BUTTONS.OFF,
                CONSTANTS.XBOX.BUTTONS.START + 6: CONSTANTS.XBOX.BUTTONS.OFF,
                CONSTANTS.XBOX.BUTTONS.SELECT + 6: CONSTANTS.XBOX.BUTTONS.OFF,
            },
            "n64": {
                # Buttons
                CONSTANTS.N64.BUTTONS.A: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.B: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.C_UP: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.C_DOWN: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.C_LEFT: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.C_RIGHT: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.L: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.R: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.Z: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.DP_UP: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.DP_DOWN: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.DP_LEFT: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.DP_RIGHT: CONSTANTS.N64.BUTTONS.OFF,
            }
        }
        
    def get_controller_values(self, controller_type: str) -> Dict:
        """
        Get the current values for a controller type.
        
        Args:
            controller_type: Either "xbox" or "n64"
            
        Returns:
            Dict: Current controller vals
        """

        return self.values.get(controller_type, {})
        
    def update_value(self, controller_type: str, key: int, value) -> None:
        """
        Updates specific controller val.
        
        Args:
            controller_type: "xbox" or "n64"
            key: The input key/axis ID
            value: New val to set
        """

        if controller_type in self.values:
            self.values[controller_type][key] = value


class ControllerManager:
    """
    Manages controller connections and input processing.
    """
    
    def __init__(self):
        """
        Init the controller manager.
        """

        self.joysticks = {}
        self.instance_id_values_map = {}
        self.controller_state = ControllerState()
        
        # Mode flags
        self.creep_mode = False
        self.reverse_mode = False
        
    def handle_hotplug_event(self, event: Event) -> bool:
        """
        Handle controller connection/disconnection events.
        
        Args:
            event: Pygame event
            
        Returns:
            bool: True if should quit (controller dc), False otherwise
        """

        # If new device is added
        if event.type == pygame.JOYDEVICEADDED:
            joy = pygame.joystick.Joystick(event.device_index)
            self.joysticks[joy.get_instance_id()] = joy
            
            # Map controller type based on name
            if "xbox" in joy.get_name().lower():
                self.instance_id_values_map[joy.get_instance_id()] = "xbox"
            elif "dinput" in joy.get_name().lower():
                self.instance_id_values_map[joy.get_instance_id()] = "n64"
                
            print(f"Joystick {joy.get_instance_id()} connected")
            return False
            
        # If a device is removed
        if event.type == pygame.JOYDEVICEREMOVED:
            if event.instance_id in self.joysticks:
                del self.joysticks[event.instance_id]
            if event.instance_id in self.instance_id_values_map:
                del self.instance_id_values_map[event.instance_id]
            print(f"Joystick {event.instance_id} disconnected")
            return True
            
        return False
        
    def should_quit_on_button(self, event: Event) -> bool:
        """
        Check if the home/start button was pressed to quit.
        
        Args:
            event: Button event
            
        Returns:
            bool: True if should quit, False otherwise
        """

        if event.instance_id not in self.instance_id_values_map:
            return False
            
        controller_type = self.instance_id_values_map[event.instance_id]
        
        if ((controller_type == "xbox" and event.button == CONSTANTS.XBOX.BUTTONS.HOME) or
            (controller_type == "n64" and event.button == CONSTANTS.N64.BUTTONS.START)):
            return True
            
        return False
        
    def get_controller_type(self, instance_id: int) -> Optional[str]:
        """
        Get the controller type for a given instance ID.
        
        Args:
            instance_id: The controller instance ID
            
        Returns:
            str: "xbox", "n64", or None if not found
        """

        return self.instance_id_values_map.get(instance_id)
        
    def update_mode_flags(self, joypad_direction: tuple, controller_type: str) -> None:
        """
        Updates creep and reverse mode flags based on joypad input.
        
        Args:
            joypad_direction: Joypad direction tuple
            controller_type: Type of controller
        """
        if controller_type != "xbox":
            return
            
        # Check button states
        select_pressed = (self.controller_state.values['xbox'].get(
            CONSTANTS.XBOX.BUTTONS.SELECT + 6) == CONSTANTS.XBOX.BUTTONS.ON)
        start_pressed = (self.controller_state.values['xbox'].get(
            CONSTANTS.XBOX.BUTTONS.START + 6) == CONSTANTS.XBOX.BUTTONS.ON)
            
        # Handle mode changes based on joypad direction
        if joypad_direction == CONSTANTS.XBOX.JOYPAD.DOWN:
            if select_pressed:
                self.reverse_mode = False
                print("reverse off")
            if start_pressed:
                self.creep_mode = False
                print("creep mode off")
                
        elif joypad_direction == CONSTANTS.XBOX.JOYPAD.UP:
            if select_pressed:
                self.reverse_mode = True
                print("reverse on")
            if start_pressed:
                self.creep_mode = True
                print("creep mode on")


class InputProcessor:
    """
    Processes different types of controller inputs.
    """
    
    def __init__(self, controller_manager: ControllerManager):
        """
        Init the input processor.
        
        Args:
            controller_manager: The controller manager instance
        """

        self.controller_manager = controller_manager
        self.deadband = CONSTANTS.TIMING.DEADBAND_THRESHOLD
        
    def process_joystick_axis(self, event: Event) -> None:
        """
        Processes joystick axis movement events.
        
        Args:
            event: The axis movement event
        """

        controller_type = self.controller_manager.get_controller_type(event.instance_id)
        if not controller_type or controller_type == "n64":
            return
            
        working_const = CONSTANTS.XBOX
        
        # Calc mult based on modes
        multiplier = self._calculate_axis_multiplier(controller_type)
        
        # Apply deadband
        value = event.value if abs(event.value) >= self.deadband else 0
        
        # Convert to int with mult
        new_value = self._convert_axis_value(value, multiplier, working_const)
        
        # Update controller state
        self.controller_manager.controller_state.update_value(
            controller_type, event.axis, new_value.to_bytes(1,'big'))
            
    def process_trigger_axis(self, event: Event) -> None:
        """
        Process trigger axis events.
        
        Args:
            event: Trigger event
        """

        controller_type = self.controller_manager.get_controller_type(event.instance_id)
        if not controller_type or controller_type == "n64":
            return
            
        # Treat trigger like button
        value = CONSTANTS.XBOX.BUTTONS.ON if event.value > 0 else CONSTANTS.XBOX.BUTTONS.OFF
        
        self.controller_manager.controller_state.update_value(
            controller_type, event.axis, value)
            
    def process_button(self, event: Event) -> None:
        """
        Process button press/release events.
        
        Args:
            event: Button event
        """

        controller_type = self.controller_manager.get_controller_type(event.instance_id)
        if not controller_type:
            return
            
        joystick = self.controller_manager.joysticks[event.joy]
        button_value = joystick.get_button(event.button)
        
        # Calc button key offset
        key_offset = 6 if controller_type == "xbox" else 0
        button_key = event.button + key_offset
        
        self.controller_manager.controller_state.update_value(
            controller_type, button_key, button_value + 1)
            
    def process_joypad(self, event: Event) -> None:
        """
        Process D-pad/joypad events.
        
        Args:
            event: Joypad event
        """

        controller_type = self.controller_manager.get_controller_type(event.instance_id)
        if not controller_type:
            return
            
        if controller_type == "n64":
            self._process_n64_joypad(event)
        else:
            self._process_xbox_joypad(event)
            
    def _calculate_axis_multiplier(self, controller_type: str) -> int:
        """
        Calc the axis mult based on current modes.
        
        Args:
            controller_type: The controller type
            
        Returns:
            int: Calculated mult
        """

        if controller_type == "n64":
            return CONSTANTS.CONTROLLER_MODES.NORMAL_MULTIPLIER
            
        multiplier = CONSTANTS.CONTROLLER_MODES.NORMAL_MULTIPLIER
        
        if self.controller_manager.creep_mode:
            multiplier = CONSTANTS.CONTROLLER_MODES.CREEP_MULTIPLIER
            
        if self.controller_manager.reverse_mode:
            multiplier = -multiplier
            
        return multiplier
        
    def _convert_axis_value(self, value: float, multiplier: int, constants) -> int:
        """
        Convert axis value to integer w/ bounds checking.
        
        Args:
            value: Axis value (-1.0 to 1.0)
            multiplier: Mult to apply
            constants: Controller consts
            
        Returns:
            int: Converted value
        """

        from math import floor
        new_value = floor(multiplier * value + constants.JOYSTICK.NEUTRAL_INT)
        
        # Clamp to valid range
        if new_value < constants.JOYSTICK.MIN_VALUE:
            new_value = constants.JOYSTICK.MIN_VALUE
        elif new_value > constants.JOYSTICK.MAX_VALUE:
            new_value = constants.JOYSTICK.MAX_VALUE
            
        return new_value
        
    def _process_n64_joypad(self, event: Event) -> None:
        """
        Process N64 controller joypad events.
        
        Args:
            event: Joypad event
        """

        x, y = event.value
        working_const = CONSTANTS.N64
        
        # X axis
        if x == 0:
            self.controller_manager.controller_state.update_value(
                "n64", working_const.BUTTONS.DP_LEFT, working_const.BUTTONS.OFF)
            self.controller_manager.controller_state.update_value(
                "n64", working_const.BUTTONS.DP_RIGHT, working_const.BUTTONS.OFF)
        elif x == -1:
            self.controller_manager.controller_state.update_value(
                "n64", working_const.BUTTONS.DP_LEFT, working_const.BUTTONS.ON)
            self.controller_manager.controller_state.update_value(
                "n64", working_const.BUTTONS.DP_RIGHT, working_const.BUTTONS.OFF)
        elif x == 1:
            self.controller_manager.controller_state.update_value(
                "n64", working_const.BUTTONS.DP_LEFT, working_const.BUTTONS.OFF)
            self.controller_manager.controller_state.update_value(
                "n64", working_const.BUTTONS.DP_RIGHT, working_const.BUTTONS.ON)
                
        # Y axis
        if y == 0:
            self.controller_manager.controller_state.update_value(
                "n64", working_const.BUTTONS.DP_DOWN, working_const.BUTTONS.OFF)
            self.controller_manager.controller_state.update_value(
                "n64", working_const.BUTTONS.DP_UP, working_const.BUTTONS.OFF)
        elif y == -1:
            self.controller_manager.controller_state.update_value(
                "n64", working_const.BUTTONS.DP_DOWN, working_const.BUTTONS.ON)
            self.controller_manager.controller_state.update_value(
                "n64", working_const.BUTTONS.DP_UP, working_const.BUTTONS.OFF)
        elif y == 1:
            self.controller_manager.controller_state.update_value(
                "n64", working_const.BUTTONS.DP_DOWN, working_const.BUTTONS.OFF)
            self.controller_manager.controller_state.update_value(
                "n64", working_const.BUTTONS.DP_UP, working_const.BUTTONS.ON)
                
    def _process_xbox_joypad(self, event: Event) -> None:
        """
        Process Xbox controller joypad events for mode switching.
        
        Args:
            event: Joypad event
        """

        self.controller_manager.update_mode_flags(event.value, "xbox")