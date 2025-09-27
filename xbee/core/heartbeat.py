"""
Heartbeat module for XBee comms.
Sends periodic signals with timestamp data for ROS comms verification.
"""

import time
import struct
from typing import Optional

from .CommandCodes import CONSTANTS

class HeartbeatManager:
    """
    Manages heartbeat signals for XBee comms.
    """
    
    def __init__(self, xbee_device = None, remote_xbee = None):
        """
        Init heartbeat manager.
        
        Args:
            xbee_device: XBee device instance for comms
            remote_xbee: Remote XBee device to send the heartbeat to
        """
        self.xbee_device = xbee_device
        self.remote_xbee = remote_xbee
        self.last_heartbeat_time = 0
        self.heartbeat_interval = CONSTANTS.HEARTBEAT.INTERVAL
        self.enabled = True
        
    def should_send_heartbeat(self) -> bool:
        """
        Checks if it's time to send a heartbeat signal.
        
        Returns:
            bool: True if heartbeat should be sent, False otherwise
        """
        current_time = time.time_ns() # Truely so incredibly necessary to be in ns trust
        return (current_time - self.last_heartbeat_time) >= self.heartbeat_interval
    
    def create_heartbeat_message(self) -> bytearray:
        """
        Create a heartbeat message with timestamp data.
        Uses the last 2 bytes of unix timestamp.
        
        Returns:
            bytearray: Heartbeat message containing identifier and timestamp
        """
        # Current unix timestamp
        unix_timestamp = int(time.time())
        
        # Get last 2 bytes of timestamp
        # 4 byte big-edian binary
        timestamp_bytes = struct.pack('>I', unix_timestamp)[-2:]
        
        # Create message: heartbeat identifier + timestamp (last 2 bytes)
        message = bytearray()
        message.extend(CONSTANTS.HEARTBEAT.MESSAGE)
        message.extend(timestamp_bytes)
        
        return message
    
    def send_heartbeat(self) -> bool:
        """
        Sends a heartbeat message if XBee comms is available.
        
        Returns:
            bool: True if heartbeat sent successfully, False otherwise
        """
        if not self.enabled or not self.xbee_device or not self.remote_xbee:
            return False
        
        try:
            heartbeat_msg = self.create_heartbeat_message()
            self.xbee_device.send_data(self.remote_xbee, heartbeat_msg)
            self.last_heartbeat_time = time.time_ns()
            return True
        except Exception as e:
            print(f"Failed to send heartbeat: {e}")
            return False
    
    def update(self) -> bool:
        """
        Update heartbeat - check if it's time to send and send if needed.
        
        Returns:
            bool: True if heartbeat was sent successfully, False otherwise
        """
        if self.should_send_heartbeat():
            return self.send_heartbeat()
        return False
    
    def enable(self):
        """
        Enable heartbeat functionality.
        """
        self.enabled = True
        
    def disable(self):
        """
        Disable heartbeat functionality.
        """
        self.enabled = False
        
    def set_interval(self, interval_ns: int):
        """
        Sets the heartbeat interval.
        
        Args:
            interval_ns: Interval in nanoseconds between heartbeats
        """
        self.heartbeat_interval = interval_ns

class HeartbeatTester:
    """
    Test class for heartbeat functionality when actual hardware isn't available.
    """
    
    def __init__(self):
        """
        Initialize the heartbeat tester.
        """
        self.received_heartbeats = []
        self.manager = HeartbeatManager()
        
    def simulate_receive_heartbeat(self, message: bytearray) -> Optional[dict]:
        """
        Simulate receiving a heartbeat message.
        
        Args:
            message: The received heartbeat message
            
        Returns:
            dict: Parsed heartbeat data or None if invalid
        """
        if len(message) < CONSTANTS.HEARTBEAT.MESSAGE_LENGTH:
            return None

        if message[0:1] != CONSTANTS.HEARTBEAT.MESSAGE:
            return None
            
        # Extract timestamp bytes
        timestamp_bytes = message[1:3]
        timestamp_value = struct.unpack('>H', timestamp_bytes)[0]
        
        heartbeat_data = {
            'timestamp': timestamp_value,
            'received_at': time.time(),
            'message': message
        }
        
        self.received_heartbeats.append(heartbeat_data)
        return heartbeat_data
        
    def test_heartbeat_creation(self):
        """
        Test heartbeat message creation.
        """
        print("Testing heartbeat message creation...")
        
        message = self.manager.create_heartbeat_message()
        print(f"Created heartbeat message: {message.hex()}")
        print(f"Message length: {len(message)} bytes")
        
        # Verify message is correctly formatted
        if message[0:1] == CONSTANTS.HEARTBEAT.MESSAGE:
            print("Heartbeat identifier: CORRECT")
        else:
            print("Heartbeat identifier: INCORRECT")
            
        if len(message) == CONSTANTS.HEARTBEAT.MESSAGE_LENGTH:
            print(f"Message length: CORRECT ({CONSTANTS.HEARTBEAT.MESSAGE_LENGTH} bytes)")
        else:
            print("Message length: INCORRECT",
                  f"(expected {CONSTANTS.HEARTBEAT.MESSAGE_LENGTH} bytes, got {len(message)} bytes)")
            
        # Parse and display timestamp
        parsed = self.simulate_receive_heartbeat(message)
        if parsed:
            print(f"SUCCESS:\nTimestamp extracted: {parsed['timestamp']}")
            current_time = int(time.time())
            print(f"Current unix timestamp: {current_time}")
            print(f"Last 2 bytes of current time: {current_time & 0xFFFF}")
        
        return message
        
    def test_interval_timing(self, test_duration_seconds=5):
        """
        Test heartbeat interval timing at 500ms.
        
        Args:
            test_duration_seconds: How long to run the timing test for
        """
        print(f"\nTesting heartbeat timing for {test_duration_seconds} seconds...")
        
        # Set shorter interval for testing
        self.manager.set_interval(CONSTANTS.CONVERSION.FIVE_HUNDRED_MS_TO_NS)
        
        start_time = time.time()
        heartbeat_count = 0
        
        while time.time() - start_time < test_duration_seconds:
            if self.manager.should_send_heartbeat():
                message = self.manager.create_heartbeat_message()
                print(f"Heartbeat {heartbeat_count + 1}: {message.hex()}")
                heartbeat_count += 1
                self.manager.last_heartbeat_time = time.time_ns()
                
            time.sleep(0.1)  # Prevent busy waiting
            
        print(f"Generated {heartbeat_count} heartbeats in {test_duration_seconds} seconds")
        interval_seconds = CONSTANTS.CONVERSION.FIVE_HUNDRED_MS_TO_NS / CONSTANTS.CONVERSION.NS_PER_S
        expected_count = int(test_duration_seconds / interval_seconds)
        print(f"Expected approximately {expected_count} heartbeats")


if __name__ == "__main__":
    # Run tests when executed directly
    tester = HeartbeatTester()
    
    print("=== Heartbeat System Test ===")
    tester.test_heartbeat_creation()
    tester.test_interval_timing()
    print("\n=== Test Complete ===")