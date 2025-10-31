"""
UDP communication system for rover basestation simulation mode.
Replaces XBee serial communication with network messages for testing.
"""

import socket
import threading
import json
import time
from typing import Dict, Any, Optional, Callable
from .command_codes import CONSTANTS
from .communication import MessageFormatter

class UdpCommunicationManager:
    """
    UDP-based communication manager for simulation mode.
    Handles sending controller data and receiving telemetry over UDP.
    """
    
    def __init__(self):
        """
        Initialize UDP communication system.
        """
        self.host = CONSTANTS.COMMUNICATION.UDP_HOST
        self.basestation_port = CONSTANTS.COMMUNICATION.UDP_BASESTATION_PORT
        self.rover_port = CONSTANTS.COMMUNICATION.UDP_ROVER_PORT
        self.telemetry_port = CONSTANTS.COMMUNICATION.UDP_TELEMETRY_PORT
        
        # Socket for sending commands to rover
        self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.send_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Socket for receiving telemetry from rover
        self.receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.receive_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Threading control
        self.running = False
        self.receive_thread = None
        
        # Callbacks for received messages
        self.message_handlers: Dict[str, Callable[[bytes], None]] = {}

        # Statistics
        self.messages_sent = 0
        self.messages_received = 0
        self.last_telemetry = {}
        
        self._setup_sockets()
        
    def _setup_sockets(self):
        """
        Setup UDP sockets for communication.
        """
        try:
            # Bind receiving socket for telemetry
            self.receive_socket.bind((self.host, self.telemetry_port))
            self.receive_socket.settimeout(1.0)  # 1 second timeout for clean shutdown
            print(f"UDP receiver bound to {self.host}:{self.telemetry_port}")
            
            print(f"UDP sender configured for {self.host}:{self.rover_port}")
            
        except Exception as e:
            print(f"Failed to setup UDP sockets: {e}")
            raise
            
    def start(self):
        """
        Start the UDP communication system.
        """
        if self.running:
            return
            
        self.running = True
        
        # Start receiving thread
        self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receive_thread.start()
        
        print("UDP communication started")
        
    def stop(self):
        """
        Stop the UDP communication system.
        """
        if not self.running:
            return
            
        self.running = False
        
        # Wait for receive thread to finish
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=2.0)
            
        # Close sockets
        try:
            self.send_socket.close()
            self.receive_socket.close()
        except Exception as e:
            print(f"Error closing UDP sockets: {e}")
            
        print("UDP communication stopped")
        
    def _send_message(self, message: bytes) -> None:
        """
        Send a UDP message.
        
        Args:
            message: bytes to send
        """
        self.send_socket.sendto(message, (self.host, self.rover_port))
        self.messages_sent += 1

    def _receive_loop(self) -> None:
        """
        Main loop for receiving UDP messages.
        """
        # while self.running:
        #     try:
        #         data, _ = self.receive_socket.recvfrom(4096)
        #         # json_str = data.decode('utf-8')
        #         message = UdpMessage.from_json(json_str)
                
        #         self.messages_received += 1
        #         self._handle_received_message(message)
                
        #     except socket.timeout:
        #         # Timeout is expected - allows clean shutdown
        #         continue
        #     except Exception as e:
        #         if self.running:  # Only log errors if we're supposed to be running
        #             print(f"Error receiving UDP message: {e}")
                
    def _handle_received_message(self, message: bytes) -> None:
        """
        Handle received UDP message.
        
        Args:
            message: Received bytes message
        """

            
        # Call registered handlers
        handler = self.message_handlers.get(message.message_type)
        if handler:
            try:
                handler(message)
            except Exception as e:
                print(f"Error in message handler for {message.message_type}: {e}")

    def register_message_handler(self, message_type: str, handler: Callable[[bytes], None]):
        """
        Register a handler for a specific message type.
        
        Args:
            message_type: Type of message to handle
            handler: Function to call when message is received
        """
        self.message_handlers[message_type] = handler
        
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get communication statistics.
        
        Returns:
            Dictionary containing communication stats
        """
        return {
            'messages_sent': self.messages_sent,
            'messages_received': self.messages_received,
            'last_telemetry': self.last_telemetry.copy(),
            'running': self.running
        }

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

            self._send_data(message)
            # self.last_message = message
            return True
            
        except Exception as e:
            print(f"Failed to send compact message: {e}")
            return False
# class SimulationCommunicationManager:
#     """
#     UDP-based communication manager for simulation mode.
#     Provides the same interface as CommunicationManager but uses UDP instead of XBee.
#     """
    
#     def __init__(self, xbee_device=None, remote_xbee=None):
#         """
#         Initialize simulation communication manager with UDP.
        
#         Args:
#             xbee_device: XBee device (ignored in simulation)
#             remote_xbee: Remote XBee device (ignored in simulation)
#         """
#         self.udp_manager = UdpCommunicationManager()
#         self.udp_manager.start()
#         print("Simulation communication manager initialized with UDP")
            
#     def send_controller_data(self, xbox_values: Dict[Any, Any], n64_values: Dict[Any, Any], reverse_mode: bool) -> bool:
#         """
#         Send controller data via UDP.
        
#         Args:
#             xbox_values: Xbox controller values (keys can be int constants or strings)
#             n64_values: N64 controller values (keys can be int constants or strings)
#             reverse_mode: Whether reverse mode is enabled
            
#         Returns:
#             True if message was sent successfully
#         """
#         return self.udp_manager.send_controller_data(xbox_values, n64_values, reverse_mode)
            
#     def send_quit_message(self) -> bool:
#         """
#         Send quit message via UDP.
        
#         Returns:
#             True if message was sent successfully
#         """
#         return self.udp_manager.send_quit_message()
    
#     def send_heartbeat(self) -> bool:
#         """
#         Send heartbeat message via UDP (simulation mode).
        
#         Returns:
#             True if message was sent successfully
#         """
#         return self.udp_manager.send_heartbeat()
            
#     def register_telemetry_handler(self, handler: Callable[[Dict[str, Any]], None]):
#         """
#         Register a handler for telemetry data.
        
#         Args:
#             handler: Function to call when telemetry is received
#         """
#         def message_handler(message: UdpMessage):
#             handler(message.data)
#         self.udp_manager.register_message_handler('telemetry', message_handler)
        
#     def get_telemetry_data(self) -> Dict[str, Any]:
#         """
#         Get the latest telemetry data.
        
#         Returns:
#             Dictionary containing telemetry data
#         """
#         return self.udp_manager.last_telemetry.copy()
            
#     def get_statistics(self) -> Dict[str, Any]:
#         """
#         Get communication stats.
        
#         Returns:
#             Dictionary containing communication stats
#         """
#         return self.udp_manager.get_statistics()
            
#     def cleanup(self):
#         """
#         Clean up communication resources.
#         """
#         self.udp_manager.stop()
