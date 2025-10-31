"""
Comms module for XBee msg formatting and transmission.
Handles the protocol msg creation and data packing.
"""

from typing import Dict, List

from .command_codes import CONSTANTS

class MessageFormatter:
    """
    Formats controller data into XBee transmission msgs.
    """
    
    def __init__(self):
        """
        Init the msg formatter.
        """
        
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

        

        # byte 1
        button_byte_1 = 0
        button_byte_1 += 1 * values.get(CONSTANTS.XBOX.BUTTONS.A + 6, CONSTANTS.XBOX.BUTTONS.OFF)
        button_byte_1 += 4 * values.get(CONSTANTS.XBOX.BUTTONS.B + 6, CONSTANTS.XBOX.BUTTONS.OFF)
        button_byte_1 += 16 * values.get(CONSTANTS.XBOX.BUTTONS.X + 6, CONSTANTS.XBOX.BUTTONS.OFF)
        button_byte_1 += 64 * values.get(CONSTANTS.XBOX.BUTTONS.Y + 6, CONSTANTS.XBOX.BUTTONS.OFF)

        # byte 2
        button_byte_2 = 0
        button_byte_2 += 1 * values.get(CONSTANTS.XBOX.BUTTONS.LEFT_BUMPER + 6, CONSTANTS.XBOX.BUTTONS.OFF)
        button_byte_2 += 4 * values.get(CONSTANTS.XBOX.BUTTONS.RIGHT_BUMPER + 6, CONSTANTS.XBOX.BUTTONS.OFF)
        button_byte_2 += 16 * values.get(CONSTANTS.XBOX.TRIGGER.AXIS_LT, CONSTANTS.XBOX.BUTTONS.OFF)
        button_byte_2 += 64 * values.get(CONSTANTS.XBOX.TRIGGER.AXIS_RT, CONSTANTS.XBOX.BUTTONS.OFF)

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

        # byte 1
        button_byte_1 = 0
        button_byte_1 += 1 * values.get(CONSTANTS.N64.BUTTONS.A, CONSTANTS.N64.BUTTONS.OFF)
        button_byte_1 += 4 * values.get(CONSTANTS.N64.BUTTONS.B, CONSTANTS.N64.BUTTONS.OFF)
        button_byte_1 += 16 * values.get(CONSTANTS.N64.BUTTONS.L, CONSTANTS.N64.BUTTONS.OFF)
        button_byte_1 += 64 * values.get(CONSTANTS.N64.BUTTONS.R, CONSTANTS.N64.BUTTONS.OFF)

        # byte 2
        button_byte_2 = 0
        button_byte_2 += 1 * values.get(CONSTANTS.N64.BUTTONS.C_UP, CONSTANTS.N64.BUTTONS.OFF)
        button_byte_2 += 4 * values.get(CONSTANTS.N64.BUTTONS.C_DOWN, CONSTANTS.N64.BUTTONS.OFF)
        button_byte_2 += 16 * values.get(CONSTANTS.N64.BUTTONS.C_LEFT, CONSTANTS.N64.BUTTONS.OFF)
        button_byte_2 += 64 * values.get(CONSTANTS.N64.BUTTONS.C_RIGHT, CONSTANTS.N64.BUTTONS.OFF)

        # byte 3
        button_byte_3 = 0
        button_byte_3 += 1 * values.get(CONSTANTS.N64.BUTTONS.DP_UP, CONSTANTS.N64.BUTTONS.OFF)
        button_byte_3 += 4 * values.get(CONSTANTS.N64.BUTTONS.DP_DOWN, CONSTANTS.N64.BUTTONS.OFF)
        button_byte_3 += 16 * values.get(CONSTANTS.N64.BUTTONS.DP_LEFT, CONSTANTS.N64.BUTTONS.OFF)
        button_byte_3 += 64 * values.get(CONSTANTS.N64.BUTTONS.DP_RIGHT, CONSTANTS.N64.BUTTONS.OFF)

        # byte 4
        button_byte_4 = 0
        button_byte_4 += 1 * values.get(CONSTANTS.N64.BUTTONS.Z, CONSTANTS.N64.BUTTONS.OFF)

        # Add more stuff in future if want idk cause like we gotta get all of em and this is spare space
        data.extend([button_byte_1, button_byte_2, button_byte_3, button_byte_4])
        
        return data

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
        self.last_xbox_message = bytearray()
        self.last_n64_message = bytearray()
        self.enabled = True
        
    def send_controller_data(self, xbox_values: Dict, n64_values: Dict, reverse_mode: bool = False) -> bool:
        """
        Send controller data via XBee using compact 10-byte format.
        
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
            message_send = False

            # send xbox msg
            xbox_message = self.formatter.create_xbox_message(xbox_values, reverse_mode)

            # Avoid sending dupe msgs
            if xbox_message != self.last_xbox_message:
                self.xbee_device.send_data(self.remote_xbee, xbox_message)
                self.last_xbox_message = xbox_message
                message_send = True

            # send n64 msg
            n64_message = self.formatter.create_n64_message(n64_values)

            # Avoid sending dupe msgs
            if n64_message != self.last_n64_message:
                self.xbee_device.send_data(self.remote_xbee, n64_message)
                self.last_n64_message = n64_message
                message_send = True

            return message_send

        except Exception as e:
            print(f"Failed to send controller data: {e}")
            return False
            
    def send_quit_message(self) -> bool:
        """
        Send quit msg to rover.
        
        Returns:
            bool: True if sent successfully, False otherwise
        """
        return self.send_package([CONSTANTS.QUIT_MESSAGE])

    def send_package(self, data: List, skip_duplicate_check: bool = False) -> bool:
        """
        Send a compact custom message (as few bytes as possible).
        
        This is the EASY way to send custom messages without the overhead
        of the new JSON format. Perfect for embedded systems where every byte counts.
        
        Args:
            data: List of bytes or integers to send. Can be:
                  - List[int]: [0xAA, 0x01, 0x02]
                  - List[bytes]: [b'\xAA', b'\x01']
                  - Mixed: [b'\xAA', 0x01, 0x02]
            skip_duplicate_check: If True, always send even if identical to last message
            
        Returns:
            bool: True if sent successfully, False otherwise
            
        Examples:
            # Send a 1-byte heartbeat
            comm.send_compact_message([0xAA])
            
            # Send a 3-byte status update (header + 2 bytes data)
            comm.send_compact_message([0xBB, motor_speed, battery_level])
            
            # Send GPS coordinates (header + 8 bytes for lat/lon)
            import struct
            lat_bytes = struct.pack('>f', 40.7128)  # latitude as float
            lon_bytes = struct.pack('>f', -74.0060)  # longitude as float
            comm.send_compact_message([0xCC] + list(lat_bytes) + list(lon_bytes))
        """
        if not self.enabled or not self.xbee_device or not self.remote_xbee:
            return False
            
        try:
            # Convert everything to bytearray
            message = bytearray()
            for item in data:
                if isinstance(item, bytes):
                    message.extend(item)
                elif isinstance(item, int):
                    message.append(item)
                else:
                    raise ValueError(f"Unsupported data type: {type(item)}")
            
            # Skip duplicate check if requested
            if not skip_duplicate_check and message == self.last_message:
                return False
                
            self.xbee_device.send_data(self.remote_xbee, message)
            self.last_message = message
            return True
            
        except Exception as e:
            print(f"Failed to send compact message: {e}")
            return False
    
    def send_heartbeat(self, timestamp_ms: int = 0) -> bool:
        """
        Send a compact heartbeat message (3 bytes total).
        
        Format: [HEARTBEAT_ID (1 byte)] [TIMESTAMP (2 bytes, little-endian)]
        
        Args:
            timestamp_ms: Timestamp in milliseconds (0-65535). If 0, current time is used.
            
        Returns:
            bool: True if sent successfully
            
        Example:
            comm.send_heartbeat()  # Auto timestamp
            comm.send_heartbeat(1234)  # Custom timestamp
        """
        if timestamp_ms == 0:
            import time
            timestamp_ms = int(time.time() * 1000) % 65536  # Keep in 2-byte range
        
        # Pack as: [0xAA][low_byte][high_byte]
        low_byte = timestamp_ms & 0xFF
        high_byte = (timestamp_ms >> 8) & 0xFF
        
        return self.send_compact_message([CONSTANTS.HEARTBEAT.MESSAGE, low_byte, high_byte], 
                                        skip_duplicate_check=True)
            
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
