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
        
    def _unpack_xbox_buttons_1(self, byte_val: int) -> Dict:
        """
        Unpack first set of Xbox buttons from a byte.
        
        Args:
            byte_val: Packed byte value
            
        Returns:
            Dict: Unpacked button values
        """
        buttons = {}
        buttons[CONSTANTS.XBOX.BUTTONS.A + 6] = (byte_val // 1) % 4
        buttons[CONSTANTS.XBOX.BUTTONS.B + 6] = (byte_val // 4) % 4
        buttons[CONSTANTS.XBOX.BUTTONS.X + 6] = (byte_val // 16) % 4
        buttons[CONSTANTS.XBOX.BUTTONS.Y + 6] = (byte_val // 64) % 4
        return buttons
        
    def _unpack_xbox_buttons_2(self, byte_val: int) -> Dict:
        """
        Unpack second set of Xbox buttons from a byte.
        
        Args:
            byte_val: Packed byte value
            
        Returns:
            Dict: Unpacked button values
        """
        buttons = {}
        buttons[CONSTANTS.XBOX.BUTTONS.LEFT_BUMPER + 6] = (byte_val // 1) % 4
        buttons[CONSTANTS.XBOX.BUTTONS.RIGHT_BUMPER + 6] = (byte_val // 4) % 4
        buttons[CONSTANTS.XBOX.TRIGGER.AXIS_LT] = (byte_val // 16) % 4
        buttons[CONSTANTS.XBOX.TRIGGER.AXIS_RT] = (byte_val // 64) % 4
        return buttons
        
    def _unpack_n64_buttons_1(self, byte_val: int) -> Dict:
        """
        Unpack first set of N64 buttons from a byte.
        
        Args:
            byte_val: Packed byte value
            
        Returns:
            Dict: Unpacked button values
        """
        buttons = {}
        buttons[CONSTANTS.N64.BUTTONS.A] = (byte_val // 1) % 4
        buttons[CONSTANTS.N64.BUTTONS.B] = (byte_val // 4) % 4
        buttons[CONSTANTS.N64.BUTTONS.L] = (byte_val // 16) % 4
        buttons[CONSTANTS.N64.BUTTONS.R] = (byte_val // 64) % 4
        return buttons
        
    def _unpack_n64_buttons_2(self, byte_val: int) -> Dict:
        """
        Unpack second set of N64 buttons from a byte.
        
        Args:
            byte_val: Packed byte value
            
        Returns:
            Dict: Unpacked button values
        """
        buttons = {}
        buttons[CONSTANTS.N64.BUTTONS.C_UP] = (byte_val // 1) % 4
        buttons[CONSTANTS.N64.BUTTONS.C_DOWN] = (byte_val // 4) % 4
        buttons[CONSTANTS.N64.BUTTONS.C_LEFT] = (byte_val // 16) % 4
        buttons[CONSTANTS.N64.BUTTONS.C_RIGHT] = (byte_val // 64) % 4
        return buttons
        
    def _unpack_n64_buttons_3(self, byte_val: int) -> Dict:
        """
        Unpack third set of N64 buttons from a byte.
        
        Args:
            byte_val: Packed byte value
            
        Returns:
            Dict: Unpacked button values
        """
        buttons = {}
        buttons[CONSTANTS.N64.BUTTONS.DP_UP] = (byte_val // 1) % 4
        buttons[CONSTANTS.N64.BUTTONS.DP_DOWN] = (byte_val // 4) % 4
        buttons[CONSTANTS.N64.BUTTONS.DP_LEFT] = (byte_val // 16) % 4
        buttons[CONSTANTS.N64.BUTTONS.DP_RIGHT] = (byte_val // 64) % 4
        return buttons
        
    def _unpack_n64_buttons_4(self, byte_val: int) -> Dict:
        """
        Unpack fourth set of N64 buttons from a byte.
        
        Args:
            byte_val: Packed byte value
            
        Returns:
            Dict: Unpacked button values
        """
        buttons = {}
        buttons[CONSTANTS.N64.BUTTONS.Z] = (byte_val // 1) % 4
        # Spare space for future buttons
        return buttons
        
    def parse_xbox_message(self, data: List[int]) -> Dict:
        """
        Parse received Xbox controller message.
        
        Args:
            data: Raw message data (5 bytes: START + LY + RY + BTN1 + BTN2)
            
        Returns:
            Dict: Parsed controller values
            
        Raises:
            ValueError: If message format is invalid
        """
        if len(data) < 5:
            raise ValueError(f"Invalid Xbox message length: {len(data)}, expected 5")
        
        if data[0] != int.from_bytes(CONSTANTS.START_MESSAGE, 'big'):
            raise ValueError(f"Invalid start byte: {data[0]:#x}")
        
        values = {}
        values[CONSTANTS.XBOX.JOYSTICK.AXIS_LY] = data[1].to_bytes(1, 'big')
        values[CONSTANTS.XBOX.JOYSTICK.AXIS_RY] = data[2].to_bytes(1, 'big')
        
        # Unpack buttons
        values.update(self._unpack_xbox_buttons_1(data[3]))
        values.update(self._unpack_xbox_buttons_2(data[4]))
        
        return values
        
    def parse_n64_message(self, data: List[int]) -> Dict:
        """
        Parse received N64 controller message.
        
        Args:
            data: Raw message data (5 bytes: START + BTN1 + BTN2 + BTN3 + BTN4)
            
        Returns:
            Dict: Parsed controller values
            
        Raises:
            ValueError: If message format is invalid
        """
        if len(data) < 5:
            raise ValueError(f"Invalid N64 message length: {len(data)}, expected 5")
        
        if data[0] != int.from_bytes(CONSTANTS.START_MESSAGE, 'big'):
            raise ValueError(f"Invalid start byte: {data[0]:#x}")
        
        values = {}
        
        # Unpack all button bytes
        values.update(self._unpack_n64_buttons_1(data[1]))
        values.update(self._unpack_n64_buttons_2(data[2]))
        values.update(self._unpack_n64_buttons_3(data[3]))
        values.update(self._unpack_n64_buttons_4(data[4]))
        
        return values
        
    def parse_combined_message(self, data: bytearray) -> tuple[Dict, Dict]:
        """
        Parse received combined Xbox and N64 message.
        
        Args:
            data: Raw combined message data (10 bytes total)
            
        Returns:
            tuple[Dict, Dict]: (xbox_values, n64_values)
            
        Raises:
            ValueError: If message format is invalid
        """
        if len(data) < 10:
            raise ValueError(f"Invalid combined message length: {len(data)}, expected 10")
        
        # Split into Xbox (first 5 bytes) and N64 (next 5 bytes)
        xbox_data = list(data[0:5])
        n64_data = list(data[5:10])
        
        xbox_values = self.parse_xbox_message(xbox_data)
        n64_values = self.parse_n64_message(n64_data)
        
        return xbox_values, n64_values


class CommunicationManager:
    """
    Manages XBee comms and msg transmission.
    """
    
    def __init__(self, xbee_device=None, remote_xbee=None, use_legacy_format: bool = True):
        """
        Init the comms manager.
        
        Args:
            xbee_device: XBee device instance
            remote_xbee: Remote XBee device instance
            use_legacy_format: If True, use fast 10-byte format. If False, use new flexible JSON format.
        """
        self.xbee_device = xbee_device
        self.remote_xbee = remote_xbee
        self.formatter = MessageFormatter()
        self.last_message = bytearray()
        self.enabled = True
        self.use_legacy_format = use_legacy_format
        
        # Import message system only if needed (avoid circular imports)
        if not use_legacy_format:
            from .message_system import MessageCodec, ControllerDataMessage
            self.codec = MessageCodec()
        else:
            self.codec = None
        
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
            if self.use_legacy_format:
                # Fast 10-byte format (legacy)
                message = self.formatter.create_combined_message(xbox_values, n64_values, reverse_mode)
            else:
                # New flexible JSON format with header
                from .message_system import ControllerDataMessage
                msg_obj = ControllerDataMessage(xbox_data=xbox_values, n64_data=n64_values, reverse_mode=reverse_mode)
                if self.codec:
                    message = self.codec.encode_message(msg_obj)
                else:
                    raise RuntimeError("Codec not initialized for new format")
            
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
        return self.send_compact_message([CONSTANTS.QUIT_MESSAGE])
    
    def send_compact_message(self, data: List, skip_duplicate_check: bool = False) -> bool:
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
        
    def set_message_format(self, use_legacy: bool):
        """
        Switch between legacy fast format and new flexible format.
        
        Args:
            use_legacy: True for 10-byte fast format, False for JSON format with header
        """
        if use_legacy == self.use_legacy_format:
            return  # Already in this mode
            
        self.use_legacy_format = use_legacy
        
        if not use_legacy and self.codec is None:
            # Initialize codec for new format
            from .message_system import MessageCodec
            self.codec = MessageCodec()
            print("Switched to new flexible JSON format (larger, but extensible)")
        elif use_legacy:
            print("Switched to legacy fast format (10 bytes, optimized for speed)")
            
    def get_message_format_info(self) -> str:
        """
        Get info about current message format.
        
        Returns:
            str: Description of current format
        """
        if self.use_legacy_format:
            return "Legacy Format"
        else:
            return "New Format"
    
    # Example messages
    # Add custom messages here, just define the message ID and format.
    
    def send_status_update(self, motor_speed: int, battery_level: int, temperature: int) -> bool:
        """
        Example: Send a 4-byte status update.
        Format: [0xB0][motor_speed][battery_level][temperature]
        
        Args:
            motor_speed: 0-255
            battery_level: 0-255 (percentage * 2.55)
            temperature: 0-255 (degrees C + 50 for negative temps)
            
        Returns:
            bool: True if sent
        """
        return self.send_compact_message([0xB0, motor_speed, battery_level, temperature])
    
    def send_error_code(self, error_code: int, subsystem_id: int = 0) -> bool:
        """
        Example: Send a 3-byte error message.
        Format: [0xE0][subsystem_id][error_code]
        
        Args:
            error_code: 0-255 error code
            subsystem_id: 0-255 which subsystem had the error
            
        Returns:
            bool: True if sent
        """
        return self.send_compact_message([0xE0, subsystem_id, error_code])
    
    def send_gps_position(self, latitude: float, longitude: float) -> bool:
        """
        Example: Send a 9-byte GPS position.
        Format: [0xC0][lat (4 bytes float)][lon (4 bytes float)]
        
        Args:
            latitude: GPS latitude (-90 to 90)
            longitude: GPS longitude (-180 to 180)
            
        Returns:
            bool: True if sent
        """
        import struct
        lat_bytes = struct.pack('>f', latitude)
        lon_bytes = struct.pack('>f', longitude)
        return self.send_compact_message([0xC0] + list(lat_bytes) + list(lon_bytes))
    
    def send_sensor_reading(self, sensor_id: int, value: int) -> bool:
        """
        Example: Send a 4-byte sensor reading.
        Format: [0xD0][sensor_id][value (2 bytes, big-endian)]
        
        Args:
            sensor_id: 0-255 which sensor
            value: 0-65535 sensor value
            
        Returns:
            bool: True if sent
        """
        high_byte = (value >> 8) & 0xFF
        low_byte = value & 0xFF
        return self.send_compact_message([0xD0, sensor_id, high_byte, low_byte])