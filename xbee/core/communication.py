"""
Comms module for XBee msg formatting and transmission.
Handles the protocol msg creation and data packing.
"""

from typing import Dict, List

from .command_codes import CONSTANTS
from .encoding import BaseStationCommunication
from .xbee_communication import XbeeCommunicationManager
from .udp_communication import UdpCommunicationManager

class MessageFormatter:
    """
    Formats controller data into XBee transmission msgs.
    """
    
    def __init__(self):
        """
        Init the msg formatter.
        """
        
    def create_xbox_message(self, values: Dict, reverse_mode: bool = False) -> bytes:
        """
        Create Xbox controller msg for transmission.
        
        Args:
            values: Xbox controller values dict
            reverse_mode: Whether reverse mode is enabled
            
        Returns:
            List[int]: Formatted msg data
        """
        
        temp_dict = values.copy()
        
        if reverse_mode:
            # In reverse mode, swap the Y axes
            left_y = values.get(CONSTANTS.XBOX.JOYSTICK.AXIS_LY, CONSTANTS.XBOX.JOYSTICK.NEUTRAL_INT)
            right_y = values.get(CONSTANTS.XBOX.JOYSTICK.AXIS_RY, CONSTANTS.XBOX.JOYSTICK.NEUTRAL_INT)

            # update the values in the dict for packing
            temp_dict[CONSTANTS.XBOX.JOYSTICK.AXIS_LY] = right_y
            temp_dict[CONSTANTS.XBOX.JOYSTICK.AXIS_RY] = left_y

        return BaseStationCommunication.encode_data(temp_dict, CONSTANTS.COMPACT_MESSAGES.XBOX_ID)

    def create_n64_message(self, values: Dict) -> bytes:
        """
        Create N64 controller msg for transmission.
        
        Args:
            values: N64 controller values dict
            
        Returns:
            List[int]: Formatted msg data
        """

        # Pack N64 button data
        
        return BaseStationCommunication.encode_data(values, CONSTANTS.COMPACT_MESSAGES.N64_ID)


class CommunicationManager:
    """
    Manages XBee comms and msg transmission.
    """
    
    def __init__(self, xbee_device=None, remote_xbee=None, simulation_mode: bool = False):
        """
        Init the comms manager.
        
        Args:
            xbee_device: XBee device instance
            remote_xbee: Remote XBee device instance
        """
        if simulation_mode:
            self.hardware_com = UdpCommunicationManager()
        else:
            self.hardware_com = XbeeCommunicationManager(xbee_device, remote_xbee)

        self.formatter = MessageFormatter()
        self.last_xbox_message = bytes()
        self.last_n64_message = bytes()
        self.simulation_mode = simulation_mode
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
                self.send_package(xbox_message)
                self.last_xbox_message = xbox_message
                message_send = True

            # send n64 msg
            n64_message = self.formatter.create_n64_message(n64_values)

            # Avoid sending dupe msgs
            if n64_message != self.last_n64_message:
                self.send_package(n64_message)
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

        quit_message = BaseStationCommunication.encode_data({}, CONSTANTS.COMPACT_MESSAGES.QUIT_ID)

        return self.send_package(quit_message)
    
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
        
        heartbeat_data = BaseStationCommunication.encode_data({
            CONSTANTS.HEARTBEAT.TIMESTAMP_MESSAGE: timestamp_ms
        }, CONSTANTS.COMPACT_MESSAGES.HEARTBEAT_ID)

        return self.send_package(heartbeat_data, skip_duplicate_check=True)

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

    def send_package(self, data: bytes, skip_duplicate_check: bool = False) -> bool:
        """
        Send a compact custom message (as few bytes as possible).

        Args:
            data: Bytes to send.
            skip_duplicate_check: If True, always send even if identical to last message
            
        Returns:
            bool: True if sent successfully, False otherwise
        """

        if not self.enabled or not self.xbee_device or not self.remote_xbee or not self.simulation_mode:
            return self.hardware_com.send_package(data, skip_duplicate_check)
        elif self.simulation_mode and self.enabled:
            return self.hardware_com.send_package(data, skip_duplicate_check)
        else:
            return False
