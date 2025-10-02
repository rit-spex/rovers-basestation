import time
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
import socket
import threading
import json

from xbee.core.CommandCodes import CONSTANTS
from xbee.core.heartbeat import HeartbeatTester, HeartbeatManager
from xbee.core.controller_manager import ControllerState, ControllerManager
from xbee.core.communication import MessageFormatter, CommunicationManager
from xbee.core.message_system import message_codec, MessageType, HeartbeatMessage, ControllerDataMessage, TelemetryMessage
from xbee.core.udp_communication import UdpMessage, UdpCommunicationManager, SimulationCommunicationManager

def test_constants_and_enums():
    # Timing constants
    assert hasattr(CONSTANTS.TIMING, 'UPDATE_FREQUENCY')
    assert hasattr(CONSTANTS.TIMING, 'DEADBAND_THRESHOLD')

    # Communication constants
    assert hasattr(CONSTANTS.COMMUNICATION, 'DEFAULT_PORT')
    assert hasattr(CONSTANTS.COMMUNICATION, 'DEFAULT_BAUD_RATE')
    assert hasattr(CONSTANTS.COMMUNICATION, 'FALLBACK_BAUD_RATE')
    assert hasattr(CONSTANTS.COMMUNICATION, 'REMOTE_XBEE_ADDRESS')

    # Controller mode constants
    assert hasattr(CONSTANTS.CONTROLLER_MODES, 'NORMAL_MULTIPLIER')
    assert hasattr(CONSTANTS.CONTROLLER_MODES, 'CREEP_MULTIPLIER')
    assert hasattr(CONSTANTS.CONTROLLER_MODES, 'REVERSE_MULTIPLIER')

    # Heartbeat message constant
    assert hasattr(CONSTANTS.HEARTBEAT, 'MESSAGE')
    assert hasattr(CONSTANTS.HEARTBEAT, 'MESSAGE_LENGTH')
    assert hasattr(CONSTANTS.HEARTBEAT, 'INTERVAL')

def test_heartbeat_system_basic():
    tester = HeartbeatTester()
    message = tester.test_heartbeat_creation()

    assert len(message) == 3
    assert message[0:1] == CONSTANTS.HEARTBEAT.MESSAGE

def test_heartbeat_timing_and_manager():
    tester = HeartbeatTester()
    # short timing test (3s)
    tester.test_interval_timing(3)

    mock_xbee = Mock()
    mock_remote = Mock()
    manager = HeartbeatManager(mock_xbee, mock_remote)
    manager.set_interval(CONSTANTS.CONVERSION.ONE_HUNDRED_MS_TO_NS)

    sent_count = 0
    for _ in range(5):
        if manager.should_send_heartbeat() and manager.send_heartbeat():
            sent_count += 1
        time.sleep(0.11)

    assert sent_count >= 1


def test_controller_state_management():
    state = ControllerState()

    xbox_values = state.get_controller_values("xbox")
    n64_values = state.get_controller_values("n64")

    assert len(xbox_values) > 0
    assert len(n64_values) > 0

    state.update_value("xbox", CONSTANTS.XBOX.BUTTONS.A + 6, CONSTANTS.XBOX.BUTTONS.ON)
    updated_value = xbox_values.get(CONSTANTS.XBOX.BUTTONS.A + 6)
    assert updated_value == CONSTANTS.XBOX.BUTTONS.ON

def test_message_formatting():
    formatter = MessageFormatter()

    mock_xbox_values = {
        CONSTANTS.XBOX.JOYSTICK.AXIS_LY: b'\x64',
        CONSTANTS.XBOX.JOYSTICK.AXIS_RY: b'\x64',
        CONSTANTS.XBOX.BUTTONS.A + 6: CONSTANTS.XBOX.BUTTONS.ON,
        CONSTANTS.XBOX.BUTTONS.B + 6: CONSTANTS.XBOX.BUTTONS.OFF,
    }

    mock_n64_values = {
        CONSTANTS.N64.BUTTONS.A: CONSTANTS.N64.BUTTONS.ON,
        CONSTANTS.N64.BUTTONS.B: CONSTANTS.N64.BUTTONS.OFF,
    }

    xbox_message = formatter.create_xbox_message(mock_xbox_values)
    assert len(xbox_message) >= 5

    n64_message = formatter.create_n64_message(mock_n64_values)
    assert len(n64_message) >= 5

    combined_message = formatter.create_combined_message(mock_xbox_values, mock_n64_values)
    assert len(combined_message) >= 10

    reverse_message = formatter.create_xbox_message(mock_xbox_values, reverse_mode=True)
    # create_xbox_message returns a list[int]. This ensures type and length
    assert isinstance(reverse_message, list)
    assert len(reverse_message) >= 5

@pytest.fixture
def mock_xbee():
    return Mock()

@pytest.fixture
def mock_remote():
    return Mock()

@pytest.fixture
def comm_manager(mock_xbee, mock_remote):
    cm = CommunicationManager(mock_xbee, mock_remote)
    cm.xbee_device = mock_xbee
    cm.remote_xbee = mock_remote
    return cm

def test_communication_manager_send_and_quit(comm_manager):
    xbox_vals = {CONSTANTS.XBOX.JOYSTICK.AXIS_LY: b'\x64', CONSTANTS.XBOX.JOYSTICK.AXIS_RY: b'\x64'}
    n64_vals = {CONSTANTS.N64.BUTTONS.A: CONSTANTS.N64.BUTTONS.ON}

    result = comm_manager.send_controller_data(xbox_vals, n64_vals)
    assert result is True
    comm_manager.xbee_device.send_data.assert_called()

    quit_result = comm_manager.send_quit_message()
    assert quit_result is True

@pytest.fixture
def manager():
    return ControllerManager()

@pytest.fixture
def formatter():
    return MessageFormatter()

def test_integration_full_flow(manager, formatter):
    fake_instance_id = 1
    manager.instance_id_values_map[fake_instance_id] = "xbox"

    from xbee.core.controller_manager import InputProcessor
    from pygame.event import Event
    from typing import cast
    processor = InputProcessor(manager)

    axis_event = cast(Event, SimpleNamespace(instance_id=fake_instance_id, value=0.5, axis=CONSTANTS.XBOX.JOYSTICK.AXIS_LY))
    processor.process_joystick_axis(axis_event)

    xbox_values = manager.controller_state.get_controller_values("xbox")
    n64_values = manager.controller_state.get_controller_values("n64")

    stored = xbox_values.get(CONSTANTS.XBOX.JOYSTICK.AXIS_LY)
    assert stored and isinstance(stored, (bytes, bytearray))

    # toggle modes via controller state
    manager.controller_state.update_value("xbox", CONSTANTS.XBOX.BUTTONS.SELECT + 6, CONSTANTS.XBOX.BUTTONS.ON)
    manager.controller_state.update_value("xbox", CONSTANTS.XBOX.BUTTONS.START + 6, CONSTANTS.XBOX.BUTTONS.ON)
    manager.update_mode_flags(CONSTANTS.XBOX.JOYPAD.UP, "xbox")
    assert manager.reverse_mode and manager.creep_mode

    manager.update_mode_flags(CONSTANTS.XBOX.JOYPAD.DOWN, "xbox")

    message = formatter.create_combined_message(xbox_values, n64_values)
    assert len(message) > 0


def test_simulation_mode_constant():
    """
    Test that simulation mode constant is accessible and works correctly.
    """
    # Test that the constant exists and is a boolean
    assert hasattr(CONSTANTS, 'SIMULATION_MODE')
    assert isinstance(CONSTANTS.SIMULATION_MODE, bool)
    
    # Test UDP communication constants exist when in simulation mode
    if CONSTANTS.SIMULATION_MODE:
        assert hasattr(CONSTANTS.COMMUNICATION, 'UDP_HOST')
        assert hasattr(CONSTANTS.COMMUNICATION, 'UDP_BASESTATION_PORT')
        assert hasattr(CONSTANTS.COMMUNICATION, 'UDP_ROVER_PORT')
        assert hasattr(CONSTANTS.COMMUNICATION, 'UDP_TELEMETRY_PORT')


def test_message_system():
    """
    Test the expandable message encoding/decoding system.
    """
    # Test heartbeat message
    heartbeat = message_codec.create_heartbeat("alive")
    encoded = message_codec.encode_message(heartbeat)
    decoded = message_codec.decode_message(encoded)
    
    assert isinstance(decoded, HeartbeatMessage)
    assert decoded.status == "alive"
    assert decoded.message_type == MessageType.HEARTBEAT
    
    # Test controller data message
    xbox_data = {'axis_ly': 100, 'axis_ry': 150, 'button_a': 1}
    n64_data = {'axis_x': 120, 'axis_y': 80}
    controller_msg = message_codec.create_controller_data(xbox_data, n64_data, True)
    encoded = message_codec.encode_message(controller_msg)
    decoded = message_codec.decode_message(encoded)
    
    assert isinstance(decoded, ControllerDataMessage)
    assert decoded.xbox_data == xbox_data
    assert decoded.n64_data == n64_data
    assert decoded.reverse_mode is True
    
    # Test telemetry message
    sensor_data = {'temperature': 25.5, 'humidity': 60.0}
    system_status = {'battery': 85, 'status': 'ok'}
    telemetry = message_codec.create_telemetry(sensor_data, system_status)
    encoded = message_codec.encode_message(telemetry)
    decoded = message_codec.decode_message(encoded)
    
    assert isinstance(decoded, TelemetryMessage)
    assert decoded.sensor_data == sensor_data
    assert decoded.system_status == system_status


def test_udp_message():
    """
    Test UDP message format for simulation mode.
    """
    # Test message creation and JSON serialization
    data = {"test_key": "test_value", "number": 42}
    message = UdpMessage("test_type", data)
    
    # Test JSON conversion
    json_str = message.to_json()
    parsed = json.loads(json_str)
    
    assert parsed['type'] == "test_type"
    assert parsed['data'] == data
    assert 'timestamp' in parsed
    
    # Test message reconstruction from JSON
    reconstructed = UdpMessage.from_json(json_str)
    assert reconstructed.message_type == message.message_type
    assert reconstructed.data == message.data


def test_simulation_communication_manager():
    """
    Test simulation communication manager functionality.
    """
    # Test initialization
    sim_manager = SimulationCommunicationManager()
    
    # Test that it has the expected interface
    assert hasattr(sim_manager, 'send_controller_data')
    assert hasattr(sim_manager, 'send_quit_message')
    assert hasattr(sim_manager, 'get_statistics')
    
    # Test statistics
    stats = sim_manager.get_statistics()
    assert isinstance(stats, dict)
    
    if CONSTANTS.SIMULATION_MODE:
        assert 'messages_sent' in stats
        assert 'messages_received' in stats
        assert 'running' in stats


def test_udp_communication_manager():
    """
    Test UDP communication manager if in simulation mode.
    """
    if not CONSTANTS.SIMULATION_MODE:
        pytest.skip("UDP tests only run in simulation mode")
    
    # Test UDP manager creation
    udp_manager = UdpCommunicationManager()
    
    # Test that sockets are set up
    assert udp_manager.host == CONSTANTS.COMMUNICATION.UDP_HOST
    assert udp_manager.rover_port == CONSTANTS.COMMUNICATION.UDP_ROVER_PORT
    assert udp_manager.telemetry_port == CONSTANTS.COMMUNICATION.UDP_TELEMETRY_PORT
    
    # Test statistics
    stats = udp_manager.get_statistics()
    assert 'messages_sent' in stats
    assert 'messages_received' in stats
    
    # Clean up
    udp_manager.stop()


def test_mock_rover_simulation():
    """
    Test mock rover functionality for UDP testing.
    """
    if not CONSTANTS.SIMULATION_MODE:
        pytest.skip("Mock rover tests only run in simulation mode")
    
    # Test mock rover creation and basic functionality
    rover = MockRover()
    assert rover.host == CONSTANTS.COMMUNICATION.UDP_HOST
    assert rover.rover_port == CONSTANTS.COMMUNICATION.UDP_ROVER_PORT
    assert rover.telemetry_port == CONSTANTS.COMMUNICATION.UDP_TELEMETRY_PORT
    
    # Test that rover can start and stop
    rover.start()
    assert rover.running is True
    
    # Let it run briefly
    time.sleep(0.1)
    
    rover.stop()
    assert rover.running is False


def test_message_codec_extensibility():
    """
    Test that the message codec is easily extensible.
    """
    # Test that we can get supported types
    supported_types = message_codec.get_supported_types()
    assert MessageType.HEARTBEAT in supported_types
    assert MessageType.CONTROLLER_DATA in supported_types
    assert MessageType.TELEMETRY in supported_types
    
    # Test that GPS message type was registered (from message_system.py)
    assert MessageType.GPS_DATA in supported_types
    
    # Test message type name mapping
    assert MessageType.get_name(MessageType.HEARTBEAT) == "HEARTBEAT"
    assert MessageType.get_name(MessageType.CONTROLLER_DATA) == "CONTROLLER_DATA"
    assert MessageType.get_name(0xFF) == "QUIT"


class MockRover:
    """
    Mock rover for testing UDP communication in simulation mode.
    """
    
    def __init__(self):
        self.host = CONSTANTS.COMMUNICATION.UDP_HOST
        self.rover_port = CONSTANTS.COMMUNICATION.UDP_ROVER_PORT
        self.telemetry_port = CONSTANTS.COMMUNICATION.UDP_TELEMETRY_PORT
        self.running = False
        self.message_count = 0
        
        # Only create sockets if in simulation mode
        if CONSTANTS.SIMULATION_MODE:
            self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.command_socket.bind((self.host, self.rover_port))
            self.command_socket.settimeout(1.0)
            
            self.telemetry_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
    def start(self):
        """
        Start the mock rover (simulation mode only).
        """
        if not CONSTANTS.SIMULATION_MODE:
            return
            
        self.running = True
        
        # Start command listener thread
        command_thread = threading.Thread(target=self._command_loop, daemon=True)
        command_thread.start()
        
        # Start telemetry sender thread  
        telemetry_thread = threading.Thread(target=self._telemetry_loop, daemon=True)
        telemetry_thread.start()
        
    def stop(self):
        """
        Stop the mock rover.
        """
        self.running = False
        if CONSTANTS.SIMULATION_MODE:
            self.command_socket.close()
            self.telemetry_socket.close()
            
    def _command_loop(self):
        """
        Listen for incoming commands.
        """
        while self.running:
            try:
                data, _ = self.command_socket.recvfrom(4096)
                message = UdpMessage.from_json(data.decode('utf-8'))
                self.message_count += 1
                
                if message.message_type == 'quit':
                    self.running = False
                    
            except socket.timeout:
                continue
            except Exception:
                if self.running:
                    break
                    
    def _telemetry_loop(self):
        """
        Send just completely fake mock telemetry data.
        """
        counter = 0
        while self.running:
            try:
                telemetry_data = {
                    # Stuff based off counter cause idk how else to do it
                    'battery_voltage': 12.5 + (counter % 10) * 0.1,
                    'temperature': 25.0 + (counter % 20) * 0.5,
                    'system_status': 'operational',
                    'messages_received': self.message_count,
                    'uptime': counter * 2
                }
                
                message = UdpMessage('telemetry', telemetry_data)
                json_data = message.to_json().encode('utf-8')
                
                self.telemetry_socket.sendto(json_data, (self.host, self.telemetry_port))
                
                counter += 1
                time.sleep(1)
                
            except Exception:
                if self.running:
                    break


def test_integrated_system():
    """
    Integration test of the complete system.
    """
    if not CONSTANTS.SIMULATION_MODE:
        pytest.skip("Integration test requires simulation mode")
        
    # Test mock rover
    rover = MockRover()
    rover.start()
    
    # Test UDP communication manager
    udp_manager = UdpCommunicationManager()
    udp_manager.start()
    
    # Test sending controller data
    xbox_data = {'axis_ly': b'\x64', 'axis_ry': b'\x64'}
    n64_data = {}
    
    result = udp_manager.send_controller_data(xbox_data, n64_data, False)
    assert result is True
    
    # Test heartbeat
    result = udp_manager.send_heartbeat()  
    assert result is True
    
    # Allow some time for communication
    time.sleep(0.5)
    
    # Check statistics
    stats = udp_manager.get_statistics()
    assert stats['messages_sent'] >= 2
    
    # Clean up
    udp_manager.stop()
    rover.stop()