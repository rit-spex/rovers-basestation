import pygame
import time
from xbee.core.command_codes import CONSTANTS
from xbee.core.controller_manager import ControllerManager

def test_xbox_mapping():
    pygame.init()
    pygame.joystick.init()
    
    print("Enumerating joysticks...")
    for i in range(pygame.joystick.get_count()):
        joy = pygame.joystick.Joystick(i)
        print(f"Joystick {i}: {joy.get_name()}")
        
    manager = ControllerManager()
    
    # Mock an Xbox Axis Motion Event
    class MockEvent:
        def __init__(self, axis, value, instance_id=0):
            self.type = pygame.JOYAXISMOTION
            self.axis = axis
            self.value = value
            self.instance_id = instance_id

    # We need to register instance ID 0 as Xbox
    manager.instance_id_values_map[0] = CONSTANTS.XBOX.NAME
    
    # Simulate moving LX (Axis 0)
    print("\nSimulating AXIS_LX (Axis 0) set to 1.0...")
    event_lx = MockEvent(0, 1.0)
    manager.handle_axis_motion(event_lx)
    xbox_vals = manager.controller_state.get_controller_values(CONSTANTS.XBOX.NAME)
    print(f"AXIS_LX (0) value: {xbox_vals.get(0)}")
    print(f"AXIS_LX_STR value: {xbox_vals.get('AXIS_LX')}")
    
    # Simulate moving LY (Axis 1)
    print("\nSimulating AXIS_LY (Axis 1) set to 1.0...")
    event_ly = MockEvent(1, 1.0)
    manager.handle_axis_motion(event_ly)
    xbox_vals = manager.controller_state.get_controller_values(CONSTANTS.XBOX.NAME)
    print(f"AXIS_LY (1) value: {xbox_vals.get(1)}")
    print(f"AXIS_LY_STR value: {xbox_vals.get('AXIS_LY')}")

    # Simulate moving LT (Axis 2)
    print("\nSimulating AXIS_LT (Axis 2) set to 1.0...")
    event_lt = MockEvent(2, 1.0)
    manager.handle_axis_motion(event_lt)
    xbox_vals = manager.controller_state.get_controller_values(CONSTANTS.XBOX.NAME)
    print(f"AXIS_LT (2) value: {xbox_vals.get(2)}")
    print(f"AXIS_LT_STR value: {xbox_vals.get('AXIS_LT')}")
    
    # Simulate moving RX (Axis 3)
    print("\nSimulating AXIS_RX (Axis 3) set to 1.0...")
    event_rx = MockEvent(3, 1.0)
    manager.handle_axis_motion(event_rx)
    xbox_vals = manager.controller_state.get_controller_values(CONSTANTS.XBOX.NAME)
    print(f"AXIS_RX (3) value: {xbox_vals.get(3)}")
    print(f"AXIS_RX_STR value: {xbox_vals.get('AXIS_RX')}")

    # Simulate moving RY (Axis 4)
    print("\nSimulating AXIS_RY (Axis 4) set to 1.0...")
    event_ry = MockEvent(4, 1.0)
    manager.handle_axis_motion(event_ry)
    xbox_vals = manager.controller_state.get_controller_values(CONSTANTS.XBOX.NAME)
    print(f"AXIS_RY (4) value: {xbox_vals.get(4)}")
    print(f"AXIS_RY_STR value: {xbox_vals.get('AXIS_RY')}")

if __name__ == "__main__":
    test_xbox_mapping()
