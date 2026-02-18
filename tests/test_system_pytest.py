from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from xbee.communication.heartbeat import HeartbeatManager
from xbee.config.constants import CONSTANTS


def test_constants_and_enums():
    # Timing constants
    assert hasattr(CONSTANTS.TIMING, "UPDATE_FREQUENCY")
    assert hasattr(CONSTANTS.TIMING, "DEADBAND_THRESHOLD")

    # Communication constants
    assert hasattr(CONSTANTS.COMMUNICATION, "DEFAULT_PORT")
    assert hasattr(CONSTANTS.COMMUNICATION, "DEFAULT_BAUD_RATE")
    assert hasattr(CONSTANTS.COMMUNICATION, "REMOTE_XBEE_ADDRESS")

    # Controller mode constants
    assert hasattr(CONSTANTS.CONTROLLER_MODES, "NORMAL_MULTIPLIER")
    assert hasattr(CONSTANTS.CONTROLLER_MODES, "CREEP_MULTIPLIER")
    assert hasattr(CONSTANTS.CONTROLLER_MODES, "REVERSE_MULTIPLIER")

    # Heartbeat message constant
    assert hasattr(CONSTANTS.HEARTBEAT, "MESSAGE")
    assert hasattr(CONSTANTS.HEARTBEAT, "MESSAGE_LENGTH")
    assert hasattr(CONSTANTS.HEARTBEAT, "INTERVAL")

    # Input type enums are defined for XBOX and N64
    assert hasattr(CONSTANTS.XBOX, "INPUT_TYPE")
    assert hasattr(CONSTANTS.N64, "INPUT_TYPE")
    assert hasattr(CONSTANTS.XBOX.INPUT_TYPE, "IS_BUTTON")
    assert hasattr(CONSTANTS.XBOX.INPUT_TYPE, "IS_AXIS")
    assert hasattr(CONSTANTS.XBOX.INPUT_TYPE, "IS_TRIGGER")


def test_heartbeat_system_basic():
    # Use a mocked communication manager and test the HeartbeatManager directly
    mock_comm_manager = Mock()
    mock_comm_manager.enabled = True
    mock_comm_manager.send_heartbeat = Mock(return_value=True)
    manager = HeartbeatManager(mock_comm_manager)
    manager.reset_heartbeat()
    result = manager.send_heartbeat()
    assert result is True
    assert manager._last_heartbeat_time > 0


def test_run_gps_reader_raises_on_scan_failure(monkeypatch):
    """
    When I2C scan raises, ensure we surface the error and deinit the bus.
    """
    import importlib

    mod = importlib.import_module("utils.gps")

    class FakeI2C:
        instances = []

        def __init__(self, scl, sda, freq=None, frequency=None, *args, **kwargs):
            FakeI2C.instances.append(self)
            self.deinit_called = False

        def scan(self):
            raise RuntimeError("scan error")

        def deinit(self):
            self.deinit_called = True

    FakeI2C.instances.clear()

    monkeypatch.setattr(mod, "board", SimpleNamespace(SCL=1, SDA=2))
    monkeypatch.setattr(mod, "busio", SimpleNamespace(I2C=FakeI2C))

    with pytest.raises(RuntimeError):
        mod.run_gps_reader()
    assert len(FakeI2C.instances) == 1
    assert FakeI2C.instances[0].deinit_called is True
