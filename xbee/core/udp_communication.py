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


class UdpMessage:
    """
    Standard UDP message format for rover communication.
    """
    
    def __init__(self, message_type: str, data: Dict[str, Any], timestamp: Optional[float] = None):
        """
        Initialize a UDP message.
        
        Args:
            message_type: Type of message (e.g., "controller", "heartbeat", "telemetry")
            data: Message payload data
            timestamp: Message timestamp (defaults to current time)
        """
        self.message_type = message_type
        self.data = data
        self.timestamp = timestamp or time.time()
        
    def to_json(self) -> str:
        """
        Convert message to JSON string for transmission.
        
        Returns:
            JSON string representation of the message
        """
        return json.dumps({
            'type': self.message_type,
            'data': self.data,
            'timestamp': self.timestamp
        })
        
    @classmethod
    def from_json(cls, json_str: str) -> 'UdpMessage':
        """
        Create message from JSON string.
        
        Args:
            json_str: JSON string to parse
            
        Returns:
            UdpMessage instance
        """
        data = json.loads(json_str)
        return cls(
            message_type=data['type'],
            data=data['data'],
            timestamp=data.get('timestamp', time.time())
        )


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
        self.message_handlers: Dict[str, Callable[[UdpMessage], None]] = {}
        
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
        
    def send_controller_data(self, xbox_values: Dict[Any, Any], n64_values: Dict[Any, Any], reverse_mode: bool) -> bool:
        """
        Send controller data over UDP.
        
        Args:
            xbox_values: Xbox controller values (keys can be int constants or strings)
            n64_values: N64 controller values (keys can be int constants or strings)
            reverse_mode: Whether reverse mode is enabled
            
        Returns:
            True if message was sent successfully
        """
        try:
            # Convert bytes values to integers for JSON serialization
            xbox_data = {}
            for key, value in xbox_values.items():
                if isinstance(value, bytes):
                    xbox_data[key] = int.from_bytes(value, 'big')
                else:
                    xbox_data[key] = value
                    
            n64_data = {}
            for key, value in n64_values.items():
                if isinstance(value, bytes):
                    n64_data[key] = int.from_bytes(value, 'big')
                else:
                    n64_data[key] = value
            
            message_data = {
                'xbox': xbox_data,
                'n64': n64_data,
                'reverse_mode': reverse_mode,
                'timestamp': time.time()
            }
            
            message = UdpMessage('controller', message_data)
            self._send_message(message)
            
            return True
            
        except Exception as e:
            print(f"Failed to send controller data: {e}")
            return False
            
    def send_heartbeat(self) -> bool:
        """
        Send heartbeat message over UDP.
        
        Returns:
            True if heartbeat was sent successfully
        """
        try:
            message_data = {
                'timestamp': time.time(),
                'status': 'alive'
            }
            
            message = UdpMessage('heartbeat', message_data)
            self._send_message(message)
            
            return True
            
        except Exception as e:
            print(f"Failed to send heartbeat: {e}")
            return False
            
    def send_quit_message(self) -> bool:
        """
        Send quit message over UDP.
        
        Returns:
            True if quit message was sent successfully
        """
        try:
            message_data = {
                'timestamp': time.time(),
                'reason': 'basestation_shutdown'
            }
            
            message = UdpMessage('quit', message_data)
            self._send_message(message)
            
            return True
            
        except Exception as e:
            print(f"Failed to send quit message: {e}")
            return False
            
    def _send_message(self, message: UdpMessage):
        """
        Send a UDP message.
        
        Args:
            message: UdpMessage to send
        """
        json_data = message.to_json().encode('utf-8')
        self.send_socket.sendto(json_data, (self.host, self.rover_port))
        self.messages_sent += 1
        
    def _receive_loop(self):
        """
        Main loop for receiving UDP messages.
        """
        while self.running:
            try:
                data, _ = self.receive_socket.recvfrom(4096)
                json_str = data.decode('utf-8')
                message = UdpMessage.from_json(json_str)
                
                self.messages_received += 1
                self._handle_received_message(message)
                
            except socket.timeout:
                # Timeout is expected - allows clean shutdown
                continue
            except Exception as e:
                if self.running:  # Only log errors if we're supposed to be running
                    print(f"Error receiving UDP message: {e}")
                
    def _handle_received_message(self, message: UdpMessage):
        """
        Handle received UDP message.
        
        Args:
            message: Received UdpMessage
        """
        # Store telemetry data
        if message.message_type == 'telemetry':
            self.last_telemetry = message.data
            
        # Call registered handlers
        handler = self.message_handlers.get(message.message_type)
        if handler:
            try:
                handler(message)
            except Exception as e:
                print(f"Error in message handler for {message.message_type}: {e}")
                
    def register_message_handler(self, message_type: str, handler: Callable[[UdpMessage], None]):
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


class SimulationCommunicationManager:
    """
    Wrapper that provides the same interface as CommunicationManager but uses UDP in simulation mode.
    """
    
    def __init__(self, xbee_device=None, remote_xbee=None):
        """
        Initialize simulation communication manager.
        
        Args:
            xbee_device: XBee device (ignored in simulation)
            remote_xbee: Remote XBee device (ignored in simulation)
        """
        self.simulation_mode = CONSTANTS.SIMULATION_MODE
        
        if self.simulation_mode:
            self.udp_manager = UdpCommunicationManager()
            self.udp_manager.start()
            print("Simulation communication manager initialized with UDP")
        else:
            # Import the real communication manager when not in simulation
            from .communication import CommunicationManager
            self.real_manager = CommunicationManager(xbee_device, remote_xbee)
            print("Real communication manager initialized with XBee")
            
    def send_controller_data(self, xbox_values: Dict[Any, Any], n64_values: Dict[Any, Any], reverse_mode: bool) -> bool:
        """
        Send controller data via appropriate communication method.
        
        Args:
            xbox_values: Xbox controller values (keys can be int constants or strings)
            n64_values: N64 controller values (keys can be int constants or strings)
            reverse_mode: Whether reverse mode is enabled
            
        Returns:
            True if message was sent successfully
        """
        if self.simulation_mode:
            return self.udp_manager.send_controller_data(xbox_values, n64_values, reverse_mode)
        else:
            return self.real_manager.send_controller_data(xbox_values, n64_values, reverse_mode)
            
    def send_quit_message(self) -> bool:
        """
        Send quit message via appropriate communication method.
        
        Returns:
            True if message was sent successfully
        """
        if self.simulation_mode:
            return self.udp_manager.send_quit_message()
        else:
            return self.real_manager.send_quit_message()
            
    def register_telemetry_handler(self, handler: Callable[[Dict[str, Any]], None]):
        """
        Register a handler for telemetry data.
        
        Args:
            handler: Function to call when telemetry is received
        """
        if self.simulation_mode:
            def message_handler(message: UdpMessage):
                handler(message.data)
            self.udp_manager.register_message_handler('telemetry', message_handler)
        # Real manager would handle this differently
        
    def get_telemetry_data(self) -> Dict[str, Any]:
        """
        Get the latest telemetry data.
        
        Returns:
            Dictionary containing telemetry data
        """
        if self.simulation_mode:
            return self.udp_manager.last_telemetry.copy()
        else:
            # Real manager would implement this
            return {}
            
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get communication stats.
        
        Returns:
            Dictionary containing communication stats
        """
        if self.simulation_mode:
            return self.udp_manager.get_statistics()
        else:
            # Real manager would implement this
            return {'mode': 'xbee', 'connected': True}
            
    def cleanup(self):
        """
        Clean up communication resources.
        """
        if self.simulation_mode:
            self.udp_manager.stop()
        # Real manager cleanup would be handled elsewhere