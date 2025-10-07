"""
Expandable msg encoding/decoding system for rover communication.
Provides a unified interface for encoding and decoding messages with easy extensibility.
"""

import struct
import json
import time
from typing import Dict, List, Type, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod
from .command_codes import CONSTANTS # for future use

@dataclass
class MessageHeader:
    """
    Standard msg header for all rover communications.
    """
    message_type: int
    message_id: int
    timestamp: float
    payload_length: int
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'MessageHeader':
        """Create header from byte data."""
        values = struct.unpack('>BIQH', data[:15])  # Big-endian format
        return cls(
            message_type=values[0],
            message_id=values[1],
            timestamp=struct.unpack('>d', struct.pack('>Q', values[2]))[0],
            payload_length=values[3]
        )
    
    def to_bytes(self) -> bytes:
        """Convert header to byte data."""
        timestamp_int = struct.unpack('>Q', struct.pack('>d', self.timestamp))[0]
        return struct.pack('>BIQH', 
                          self.message_type, 
                          self.message_id, 
                          timestamp_int, 
                          self.payload_length)


class MessageType:
    """
    Message type constants.
    """
    HEARTBEAT = 0x01
    CONTROLLER_DATA = 0x02
    TELEMETRY = 0x03
    STATUS_REQUEST = 0x04
    STATUS_RESPONSE = 0x05
    COMMAND = 0x06
    COMMAND_RESPONSE = 0x07
    ERROR = 0x08
    QUIT = 0xFF
    
    # just add new consts here
    CAMERA_DATA = 0x10
    SENSOR_DATA = 0x11
    GPS_DATA = 0x12
    DIAGNOSTIC = 0x13
    
    # Mapping for string names
    TYPE_NAMES = {
        0x01: "HEARTBEAT",
        0x02: "CONTROLLER_DATA", 
        0x03: "TELEMETRY",
        0x04: "STATUS_REQUEST",
        0x05: "STATUS_RESPONSE",
        0x06: "COMMAND",
        0x07: "COMMAND_RESPONSE",
        0x08: "ERROR",
        0x10: "CAMERA_DATA",
        0x11: "SENSOR_DATA",
        0x12: "GPS_DATA", 
        0x13: "DIAGNOSTIC",
        0xFF: "QUIT"
    }
    
    @classmethod
    def get_name(cls, message_type: int) -> str:
        """
        Get name you can actualy read for msg type.
        """
        return cls.TYPE_NAMES.get(message_type, f"UNKNOWN_{message_type:02X}")


class BaseMessage(ABC):
    """
    Base class for all msg types.
    Is the encoding/decoding interface that all msgs will implement.
    """
    
    def __init__(self, message_id: Optional[int] = None, timestamp: Optional[float] = None):
        """
        Init base msg.
        
        Args:
            message_id: Unique msg ID (auto generated if None)
            timestamp: Msg timestamp (current time if None)
        """
        self.message_id = message_id or int(time.time() * 1000) % 0xFFFFFFFF
        self.timestamp = timestamp or time.time()
    
    @property
    @abstractmethod # guess who had to learn you gotta do this for abstract
    def message_type(self) -> int:
        """
        Return the msg type const.
        """
        ...
    
    @abstractmethod
    def encode_payload(self) -> bytes:
        """
        Encode msg payload to bytes.
        
        Returns:
            Byte representation of msg payload
        """
        ...
    
    @abstractmethod
    def decode_payload(self, payload: bytes) -> None:
        """
        Decode msg payload from bytes.
        
        Args:
            payload: Byte data to decode
        """
        ...
    
    def encode(self) -> bytes:
        """
        Encode complete msg with header.
        
        Returns:
            Complete encoded msg
        """
        payload = self.encode_payload()
        header = MessageHeader(
            message_type=self.message_type,
            message_id=self.message_id,
            timestamp=self.timestamp,
            payload_length=len(payload)
        )
        return header.to_bytes() + payload
    
    @classmethod
    def decode(cls, data: bytes) -> 'BaseMessage':
        """
        Decode msg from bytes.
        
        Args:
            data: Complete msg bytes w/ header

        Returns:
            Decoded msg instance
        """
        if len(data) < 15:  # Min header size
            raise ValueError("Message too short")
            
        header = MessageHeader.from_bytes(data[:15])
        payload = data[15:15+header.payload_length]
        
        # Create msg instance and decode payload
        message = cls(message_id=header.message_id, timestamp=header.timestamp)
        message.decode_payload(payload)
        return message


class HeartbeatMessage(BaseMessage):
    """
    Heartbeat msg to see connection info.
    """
    
    def __init__(self, status: str = "alive", **kwargs):
        super().__init__(**kwargs)
        self.status = status
        
    @property
    def message_type(self) -> int:
        return MessageType.HEARTBEAT
    
    def encode_payload(self) -> bytes:
        data = {"status": self.status}
        return json.dumps(data).encode('utf-8')
    
    def decode_payload(self, payload: bytes) -> None:
        data = json.loads(payload.decode('utf-8'))
        self.status = data.get("status", "alive")


class ControllerDataMessage(BaseMessage):
    """
    Controller input data msg.
    """
    
    def __init__(self, xbox_data: Optional[Dict] = None, n64_data: Optional[Dict] = None, 
                 reverse_mode: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.xbox_data = xbox_data or {}
        self.n64_data = n64_data or {}
        self.reverse_mode = reverse_mode
        
    @property
    def message_type(self) -> int:
        return MessageType.CONTROLLER_DATA
    
    def encode_payload(self) -> bytes:
        # Convert bytes vals to ints for JSON serialzaton
        xbox_clean = {}
        for key, value in self.xbox_data.items():
            if isinstance(value, bytes):
                xbox_clean[key] = int.from_bytes(value, 'big')
            else:
                xbox_clean[key] = value
                
        n64_clean = {}
        for key, value in self.n64_data.items():
            if isinstance(value, bytes):
                n64_clean[key] = int.from_bytes(value, 'big') 
            else:
                n64_clean[key] = value
        
        data = {
            "xbox": xbox_clean,
            "n64": n64_clean, 
            "reverse_mode": self.reverse_mode
        }
        return json.dumps(data).encode('utf-8')
    
    def decode_payload(self, payload: bytes) -> None:
        data = json.loads(payload.decode('utf-8'))
        self.xbox_data = data.get("xbox", {})
        self.n64_data = data.get("n64", {})
        self.reverse_mode = data.get("reverse_mode", False)


class TelemetryMessage(BaseMessage):
    """
    Telemetry data msg from rover.
    """
    
    def __init__(self, sensor_data: Optional[Dict] = None, system_status: Optional[Dict] = None, **kwargs):
        super().__init__(**kwargs)
        self.sensor_data = sensor_data or {}
        self.system_status = system_status or {}
        
    @property
    def message_type(self) -> int:
        return MessageType.TELEMETRY
    
    def encode_payload(self) -> bytes:
        data = {
            "sensors": self.sensor_data,
            "system": self.system_status
        }
        return json.dumps(data).encode('utf-8')
    
    def decode_payload(self, payload: bytes) -> None:
        data = json.loads(payload.decode('utf-8'))
        self.sensor_data = data.get("sensors", {})
        self.system_status = data.get("system", {})


class CommandMessage(BaseMessage):
    """
    Command msg for rover control.
    """
    
    def __init__(self, command: str = "", parameters: Optional[Dict] = None, **kwargs):
        super().__init__(**kwargs)
        self.command = command
        self.parameters = parameters or {}
        
    @property
    def message_type(self) -> int:
        return MessageType.COMMAND
    
    def encode_payload(self) -> bytes:
        data = {
            "command": self.command,
            "parameters": self.parameters
        }
        return json.dumps(data).encode('utf-8')
    
    def decode_payload(self, payload: bytes) -> None:
        data = json.loads(payload.decode('utf-8'))
        self.command = data.get("command", "")
        self.parameters = data.get("parameters", {})


class ErrorMessage(BaseMessage):
    """
    Error msg for comms issues.
    """
    
    def __init__(self, error_code: int = 0, error_message: str = "", **kwargs):
        super().__init__(**kwargs)
        self.error_code = error_code
        self.error_message = error_message
        
    @property
    def message_type(self) -> int:
        return MessageType.ERROR
    
    def encode_payload(self) -> bytes:
        data = {
            "error_code": self.error_code,
            "message": self.error_message
        }
        return json.dumps(data).encode('utf-8')
    
    def decode_payload(self, payload: bytes) -> None:
        data = json.loads(payload.decode('utf-8'))
        self.error_code = data.get("error_code", 0)
        self.error_message = data.get("message", "")


class MessageCodec:
    """
    Central msg encoder/decoder that handles all msg types.
    Expand by just registering new msg classes.
    """
    
    def __init__(self):
        """
        Init msg codec with default msg types.
        """
        self._message_classes: Dict[int, Type[BaseMessage]] = {}
        
        # Register built-in msg types
        self.register_message_class(MessageType.HEARTBEAT, HeartbeatMessage)
        self.register_message_class(MessageType.CONTROLLER_DATA, ControllerDataMessage)
        self.register_message_class(MessageType.TELEMETRY, TelemetryMessage)
        self.register_message_class(MessageType.COMMAND, CommandMessage)
        self.register_message_class(MessageType.ERROR, ErrorMessage)
        
    def register_message_class(self, message_type: int, message_class: Type[BaseMessage]):
        """
        Register a new msg type class.
        
        Args:
            message_type: Msg type const
            message_class: Class that uses BaseMessage
        """
        self._message_classes[message_type] = message_class
        
    def encode_message(self, message: BaseMessage) -> bytes:
        """
        Encode a msg to bytes.
        
        Args:
            message: Message to encode
            
        Returns:
            Encoded msg bytes
        """
        return message.encode()
        
    def decode_message(self, data: bytes) -> BaseMessage:
        """
        Decode bytes to a msg.
        
        Args:
            data: Raw msg bytes
            
        Returns:
            Decoded msg instance
            
        Raises:
            ValueError: If msg type is unknown or data is invalid
        """
        if len(data) < 15:
            raise ValueError("Message too short")
            
        header = MessageHeader.from_bytes(data[:15])
        
        message_class = self._message_classes.get(header.message_type)
        if not message_class:
            raise ValueError(f"Unknown msg type: {header.message_type}")
            
        return message_class.decode(data)
        
    def create_heartbeat(self, status: str = "alive") -> HeartbeatMessage:
        """
        Create a heartbeat msg.
        
        Args:
            status: Heartbeat status
            
        Returns:
            HeartbeatMessage instance
        """
        return HeartbeatMessage(status=status)
        
    def create_controller_data(self, xbox_data: Dict, n64_data: Dict, reverse_mode: bool = False) -> ControllerDataMessage:
        """
        Create a controller data msg.
        
        Args:
            xbox_data: Xbox controller data
            n64_data: N64 controller data
            reverse_mode: Whether reverse mode is active
            
        Returns:
            ControllerDataMessage instance
        """
        return ControllerDataMessage(
            xbox_data=xbox_data,
            n64_data=n64_data,
            reverse_mode=reverse_mode
        )
        
    def create_telemetry(self, sensor_data: Dict, system_status: Dict) -> TelemetryMessage:
        """
        Create a telemetry msg.
        
        Args:
            sensor_data: Sensor readings
            system_status: System status info
            
        Returns:
            TelemetryMessage instance
        """
        return TelemetryMessage(
            sensor_data=sensor_data,
            system_status=system_status
        )
        
    def create_command(self, command: str, parameters: Optional[Dict] = None) -> CommandMessage:
        """
        Create a command msg.
        
        Args:
            command: Command to execute
            parameters: Command params
            
        Returns:
            CommandMessage instance
        """
        return CommandMessage(command=command, parameters=parameters or {})
        
    def create_error(self, error_code: int, error_message: str) -> ErrorMessage:
        """
        Create an error msg.
        
        Args:
            error_code: Numeric error code
            error_message: Human readable error msg
            
        Returns:
            ErrorMessage instance
        """
        return ErrorMessage(error_code=error_code, error_message=error_message)
        
    def get_supported_types(self) -> List[int]:
        """
        Get list of supported msg types.
        
        Returns:
            List of msg type constants
        """
        return list(self._message_classes.keys())


# Global codec instance for easy use
message_codec = MessageCodec()

# =============================================================================================================
# ================================================== EXAMPLE ==================================================
# =============================================================================================================

class GPSMessage(BaseMessage):
    """
    GPS position msg.
    """
    
    def __init__(self, latitude: float = 0.0, longitude: float = 0.0, 
                 altitude: float = 0.0, accuracy: float = 0.0, **kwargs):
        super().__init__(**kwargs)
        self.latitude = latitude
        self.longitude = longitude
        self.altitude = altitude
        self.accuracy = accuracy
        
    @property
    def message_type(self) -> int:
        return MessageType.GPS_DATA
    
    def encode_payload(self) -> bytes:
        data = {
            "lat": self.latitude,
            "lon": self.longitude, 
            "alt": self.altitude,
            "acc": self.accuracy
        }
        return json.dumps(data).encode('utf-8')
    
    def decode_payload(self, payload: bytes) -> None:
        data = json.loads(payload.decode('utf-8'))
        self.latitude = data.get("lat", 0.0)
        self.longitude = data.get("lon", 0.0)
        self.altitude = data.get("alt", 0.0)
        self.accuracy = data.get("acc", 0.0)

# Register the new msg type
message_codec.register_message_class(MessageType.GPS_DATA, GPSMessage)

# =============================================================================================================
# ==================================================== END ====================================================
# =============================================================================================================