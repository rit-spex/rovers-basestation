"""
Comms module for XBee msg formatting and transmission.
Handles the protocol msg creation and data packing.
"""

from typing import Dict, List

from .CommandCodes import CONSTANTS

class MessageFormatter:
    """
    Formats controller data into XBee transmission msgs.
    """
    
    def __init__(self):
        """
        Init the msg formatter.
        """
        ...
        
    def create_xbox_message(self, values: Dict, reverse_mode: bool = False) -> List[int]:
        """
        Create Xbox controller msg for transmission.
        
        Args:
            values: Xbox controller values dict
            reverse_mode: Whether reverse mode is enabled
            
        Returns:
            List[int]: Formatted msg data
        """
        data = [int.from_bytes(CONSTANTS.START_MESSAGE, 'big')]

        if not reverse_mode:
            # Send regular mode - left joystick is left, right joystick is right
            data.append(int.from_bytes(values.get(CONSTANTS.XBOX.JOYSTICK.AXIS_LY, b'\x64'), 'big'))
            data.append(int.from_bytes(values.get(CONSTANTS.XBOX.JOYSTICK.AXIS_RY, b'\x64'), 'big'))
        else:
            # Invert controller - left joystick is right, right joystick is left
            data.append(int.from_bytes(values.get(CONSTANTS.XBOX.JOYSTICK.AXIS_RY, b'\x64'), 'big'))
            data.append(int.from_bytes(values.get(CONSTANTS.XBOX.JOYSTICK.AXIS_LY, b'\x64'), 'big'))

        # Button data into bytes
        button_byte_1 = self._pack_xbox_buttons_1(values)
        button_byte_2 = self._pack_xbox_buttons_2(values)
        
        data.append(button_byte_1)
        data.append(button_byte_2)
        
        return data
        
    def create_n64_message(self, values: Dict) -> List[int]:
        """
        Create N64 controller msg for transmission.
        
        Args:
            values: N64 controller values dict
            
        Returns:
            List[int]: Formatted msg data
        """
        data = [int.from_bytes(CONSTANTS.START_MESSAGE, 'big')]
        
        # Pack N64 button data
        button_byte_1 = self._pack_n64_buttons_1(values)
        button_byte_2 = self._pack_n64_buttons_2(values) 
        button_byte_3 = self._pack_n64_buttons_3(values)
        button_byte_4 = self._pack_n64_buttons_4(values)
        
        data.extend([button_byte_1, button_byte_2, button_byte_3, button_byte_4])
        
        return data
        
    def create_combined_message(self, xbox_values: Dict, n64_values: Dict, reverse_mode: bool = False) -> bytearray:
        """
        Create combined Xbox and N64 msg for transmission.
        
        Args:
            xbox_values: Xbox controller vals
            n64_values: N64 controller vals  
            reverse_mode: Whether reverse mode is enabled
            
        Returns:
            bytearray: Complete formatted message
        """
        data = []
        
        # Xbox controller data
        xbox_data = self.create_xbox_message(xbox_values, reverse_mode)
        data.extend(xbox_data)
        
        # N64 controller data
        n64_data = self.create_n64_message(n64_values)
        data.extend(n64_data)
        
        return bytearray(data)
        
    def _pack_xbox_buttons_1(self, values: Dict) -> int:
        """
        Pack first set of Xbox buttons into a byte.
        
        Args:
            values: Xbox controller vals
            
        Returns:
            int: Packed byte val
        """
        result = 0
        # Pack A, B, X, Y buttons (2 bits each)
        result += 1 * values.get(CONSTANTS.XBOX.BUTTONS.A + 6, CONSTANTS.XBOX.BUTTONS.OFF)
        result += 4 * values.get(CONSTANTS.XBOX.BUTTONS.B + 6, CONSTANTS.XBOX.BUTTONS.OFF)
        result += 16 * values.get(CONSTANTS.XBOX.BUTTONS.X + 6, CONSTANTS.XBOX.BUTTONS.OFF)
        result += 64 * values.get(CONSTANTS.XBOX.BUTTONS.Y + 6, CONSTANTS.XBOX.BUTTONS.OFF)
        return result
        
    def _pack_xbox_buttons_2(self, values: Dict) -> int:
        """
        Pack second set of Xbox buttons into a byte.
        
        Args:
            values: Xbox controller vals
            
        Returns:
            int: Packed byte val
        """
        result = 0
        # Pack bumpers and triggers (2 bits each)
        result += 1 * values.get(CONSTANTS.XBOX.BUTTONS.LEFT_BUMPER + 6, CONSTANTS.XBOX.BUTTONS.OFF)
        result += 4 * values.get(CONSTANTS.XBOX.BUTTONS.RIGHT_BUMPER + 6, CONSTANTS.XBOX.BUTTONS.OFF)
        result += 16 * values.get(CONSTANTS.XBOX.TRIGGER.AXIS_LT, CONSTANTS.XBOX.BUTTONS.OFF)
        result += 64 * values.get(CONSTANTS.XBOX.TRIGGER.AXIS_RT, CONSTANTS.XBOX.BUTTONS.OFF)
        return result
        
    def _pack_n64_buttons_1(self, values: Dict) -> int:
        """
        Pack first set of N64 buttons into a byte.
        
        Args:
            values: N64 controller vals
            
        Returns:
            int: Packed byte val
        """
        result = 0
        result += 1 * values.get(CONSTANTS.N64.BUTTONS.A, CONSTANTS.N64.BUTTONS.OFF)
        result += 4 * values.get(CONSTANTS.N64.BUTTONS.B, CONSTANTS.N64.BUTTONS.OFF)
        result += 16 * values.get(CONSTANTS.N64.BUTTONS.L, CONSTANTS.N64.BUTTONS.OFF)
        result += 64 * values.get(CONSTANTS.N64.BUTTONS.R, CONSTANTS.N64.BUTTONS.OFF)
        return result
        
    def _pack_n64_buttons_2(self, values: Dict) -> int:
        """
        Pack second set of N64 buttons into a byte.
        
        Args:
            values: N64 controller vals
            
        Returns:
            int: Packed byte val
        """
        result = 0
        result += 1 * values.get(CONSTANTS.N64.BUTTONS.C_UP, CONSTANTS.N64.BUTTONS.OFF)
        result += 4 * values.get(CONSTANTS.N64.BUTTONS.C_DOWN, CONSTANTS.N64.BUTTONS.OFF)
        result += 16 * values.get(CONSTANTS.N64.BUTTONS.C_LEFT, CONSTANTS.N64.BUTTONS.OFF)
        result += 64 * values.get(CONSTANTS.N64.BUTTONS.C_RIGHT, CONSTANTS.N64.BUTTONS.OFF)
        return result
        
    def _pack_n64_buttons_3(self, values: Dict) -> int:
        """
        Pack third set of N64 buttons into a byte.
        
        Args:
            values: N64 controller vals
            
        Returns:
            int: Packed byte val
        """
        result = 0
        result += 1 * values.get(CONSTANTS.N64.BUTTONS.DP_UP, CONSTANTS.N64.BUTTONS.OFF)
        result += 4 * values.get(CONSTANTS.N64.BUTTONS.DP_DOWN, CONSTANTS.N64.BUTTONS.OFF)
        result += 16 * values.get(CONSTANTS.N64.BUTTONS.DP_LEFT, CONSTANTS.N64.BUTTONS.OFF)
        result += 64 * values.get(CONSTANTS.N64.BUTTONS.DP_RIGHT, CONSTANTS.N64.BUTTONS.OFF)
        return result
        
    def _pack_n64_buttons_4(self, values: Dict) -> int:
        """
        Pack fourth set of N64 buttons into a byte.
        
        Args:
            values: N64 controller vals
            
        Returns:
            int: Packed byte val
        """
        result = 0
        result += 1 * values.get(CONSTANTS.N64.BUTTONS.Z, CONSTANTS.N64.BUTTONS.OFF)
        # Add more stuff in future if want idk cause like we gotta get all of em and this is spare space
        return result


class CommunicationManager:
    """
    Manages XBee comms and msg transmission.
    """
    
    def __init__(self, xbee_device=None, remote_xbee=None):
        """
        Init the comms manager.
        
        Args:
            xbee_device: XBee device instance
            remote_xbee: Remote XBee device instance
        """
        self.xbee_device = xbee_device
        self.remote_xbee = remote_xbee
        self.formatter = MessageFormatter()
        self.last_message = bytearray()
        self.enabled = True
        
    def send_controller_data(self, xbox_values: Dict, n64_values: Dict, reverse_mode: bool = False) -> bool:
        """
        Send controller data via XBee.
        
        Args:
            xbox_values: Xbox controller vals
            n64_values: N64 controller vals
            reverse_mode: Whether reverse mode is enabled
            
        Returns:
            bool: True if message was sent, False if skipped/failed
        """
        if not self.enabled or not self.xbee_device or not self.remote_xbee:
            return False
            
        try:
            message = self.formatter.create_combined_message(xbox_values, n64_values, reverse_mode)
            
            # Avoid sending dupe msgs
            if message == self.last_message:
                return False
                
            self.xbee_device.send_data(self.remote_xbee, message)
            self.last_message = message
            return True
            
        except Exception as e:
            print(f"Failed to send controller data: {e}")
            return False
            
    def send_quit_message(self) -> bool:
        """
        Send quit msg to rover.
        
        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.enabled or not self.xbee_device or not self.remote_xbee: # Wow I hate python just use !
            return False
            
        try:
            data = bytearray([int.from_bytes(CONSTANTS.QUIT_MESSAGE, 'big')])
            print(f"Telling the rover to quit: {data}")
            self.xbee_device.send_data(self.remote_xbee, data)
            return True
            
        except Exception as e:
            print(f"Failed to send quit message: {e}")
            return False
            
    def enable(self):
        """
        Enable communication.
        """
        self.enabled = True
        
    def disable(self):
        """
        Disable communication.
        """
        self.enabled = False