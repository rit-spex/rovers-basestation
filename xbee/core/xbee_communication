from typing import Dict, List

from .command_codes import CONSTANTS
from .encoding import BaseStationCommunication

class XbeeCommunicationManager:
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
        self.enabled = True

    def send_package(self, data: bytes, skip_duplicate_check: bool = False) -> bool:
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
            # if not skip_duplicate_check and message == self.last_message:
            #     return False
                
            self.xbee_device.send_data(self.remote_xbee, message)
            # self.last_message = message
            return True
            
        except Exception as e:
            print(f"Failed to send compact message: {e}")
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
