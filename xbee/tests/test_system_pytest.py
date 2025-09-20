import time
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

from ..CommandCodes import CONSTANTS
from ..core.heartbeat import HeartbeatTester, HeartbeatManager
from ..core.controller_manager import ControllerState, ControllerManager
from ..core.communication import MessageFormatter, CommunicationManager

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

    from ..core.controller_manager import InputProcessor
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