"""
Centralized pytest fixtures for the rovers-basestation test suite.

This module provides reusable fixtures for common test scenarios including
mock XBee devices, controllers, UDP sockets, and sample data.
"""

import json
import socket
from pathlib import Path
from typing import Any, Dict
from unittest.mock import Mock

import pytest

# Path to mock_data directory used by fixtures; fixtures raise FileNotFoundError if required files are missing.
MOCK_DATA_DIR = Path(__file__).parent / "mock_data"


@pytest.fixture
def mock_xbee_device():
    """
    Provides a mock XBee device for testing.

    Returns:
        Mock XBee device with common methods stubbed.
    """
    device = Mock()
    device.open = Mock()
    device.close = Mock()
    device.send_data = Mock(return_value=True)
    device.is_open = Mock(return_value=True)
    # Return a real XBee64BitAddress if digi.xbee is available; otherwise return a minimal fake with required attributes.
    try:
        from digi.xbee.models.address import XBee64BitAddress  # type: ignore

        x64 = XBee64BitAddress.from_hex_string("0013A200423A7DDD")
    except Exception:

        class _FakeXBee64BitAddress:
            def __init__(self, hexstr: str):
                self._hex = hexstr
                self.address = bytes.fromhex(hexstr)

            def __str__(self) -> str:
                return self._hex

        x64 = _FakeXBee64BitAddress("0013A200423A7DDD")

    device.get_64bit_addr = Mock(return_value=x64)
    return device


@pytest.fixture
def mock_udp_socket():
    """
    Provides a mock UDP socket for testing network communication.

    Returns:
        Mock socket with sendto and recvfrom methods.
    """
    sock = Mock(spec=socket.socket)
    sock.sendto = Mock(return_value=10)
    sock.recvfrom = Mock(return_value=(b"test_data", ("127.0.0.1", 5005)))
    sock.setsockopt = Mock()
    sock.bind = Mock()
    sock.close = Mock()
    return sock


def _load_controller_inputs() -> Dict[str, Any]:
    """Load controller inputs from mock_data directory."""
    filepath = MOCK_DATA_DIR / "controller_inputs.json"
    with open(filepath, "r") as f:
        return json.load(f)


def _load_telemetry_messages() -> Dict[str, Any]:
    """Load telemetry messages from mock_data directory."""
    filepath = MOCK_DATA_DIR / "telemetry_messages.json"
    with open(filepath, "r") as f:
        return json.load(f)


@pytest.fixture
def sample_xbox_controller_data() -> Dict[str, Any]:
    """
    Provides sample Xbox controller input data from mock_data/controller_inputs.json.

    Returns:
        Dictionary with typical Xbox controller state.
    """
    # Controller axes are floats in -1.0..1.0; compact encoding maps neutral 0.0 to 100.
    # `sample_encoded_xbox_message` fixture for an example encoded payload.
    data = _load_controller_inputs()
    return data["controller_inputs"]["xbox_neutral"]


@pytest.fixture
def sample_xbox_controller_forward() -> Dict[str, Any]:
    """
    Provides sample Xbox controller input with forward motion from mock_data.

    Returns:
        Dictionary with Xbox controller state showing forward movement.
    """
    data = _load_controller_inputs()
    return data["controller_inputs"]["xbox_forward"]


@pytest.fixture
def sample_xbox_controller_buttons_pressed() -> Dict[str, Any]:
    """
    Provides sample Xbox controller input with buttons pressed from mock_data.

    Returns:
        Dictionary with Xbox controller state with multiple buttons pressed.
    """
    data = _load_controller_inputs()
    return data["controller_inputs"]["xbox_buttons_pressed"]


@pytest.fixture
def sample_n64_controller_data() -> Dict[str, Any]:
    """
    Provides sample N64 controller input data from mock_data/controller_inputs.json.

    Returns:
        Dictionary with typical N64 controller state.
    """
    data = _load_controller_inputs()
    return data["controller_inputs"]["n64_neutral"]


@pytest.fixture
def sample_n64_controller_all_pressed() -> Dict[str, Any]:
    """
    Provides sample N64 controller input with all buttons pressed from mock_data.

    Returns:
        Dictionary with N64 controller state with all buttons pressed.
    """
    data = _load_controller_inputs()
    return data["controller_inputs"]["n64_all_pressed"]


@pytest.fixture
def sample_telemetry_data() -> Dict[str, Any]:
    """
    Provides sample telemetry data from mock_data/telemetry_messages.json.

    Returns:
        Dictionary with typical telemetry fields.
    """
    data = _load_telemetry_messages()
    return data["telemetry_messages"]["basic_telemetry"]


@pytest.fixture
def sample_telemetry_low_battery() -> Dict[str, Any]:
    """
    Provides sample telemetry data with low battery from mock_data.

    Returns:
        Dictionary with low battery telemetry.
    """
    data = _load_telemetry_messages()
    return data["telemetry_messages"]["low_battery"]


@pytest.fixture
def sample_telemetry_with_gps() -> Dict[str, Any]:
    """
    Provides sample telemetry data with GPS coordinates from mock_data.

    Returns:
        Dictionary with GPS-enhanced telemetry.
    """
    data = _load_telemetry_messages()
    return data["telemetry_messages"]["with_gps"]


@pytest.fixture
def sample_udp_messages() -> Dict[str, str]:
    """
    Provides sample UDP messages from mock_data/telemetry_messages.json.

    Returns:
        Dictionary with sample UDP JSON messages.
    """
    data = _load_telemetry_messages()
    return data["udp_messages"]


@pytest.fixture
def sample_encoded_xbox_message() -> bytes:
    """
    Provides a pre-encoded Xbox controller message.

    Returns:
        Bytes representing encoded Xbox controller data.
    """
    # Xbox message: ID (0x02) + ly (100) + ry (100) + buttons (all off) - ly/ry=100 is the neutral encoding value.
    return bytes([0x02, 100, 100, 0x55, 0x55])


@pytest.fixture
def sample_encoded_heartbeat() -> bytes:
    """
    Provides a pre-encoded heartbeat message.

    Returns:
        Bytes representing encoded heartbeat.
    """
    # Heartbeat message: ID (0x01) + timestamp (16-bit: 0)
    return bytes([0x01, 0x00, 0x00])


@pytest.fixture
def load_mock_json():
    """
    Provides a helper function to load JSON from mock_data directory.

    Returns:
        Function that loads JSON files from mock_data/.
    """

    def _load(filename: str) -> Dict[str, Any]:
        filepath = MOCK_DATA_DIR / filename
        if not filepath.exists():
            raise FileNotFoundError(
                f"Required mock JSON file does not exist: {filepath}. Please add the file to tests/mock_data/."
            )
        with open(filepath, "r") as f:
            return json.load(f)

    return _load


@pytest.fixture
def load_mock_binary():
    """
    Provides a helper function to load binary from mock_data directory.

    Returns:
        Function that loads binary files from mock_data/.
    """

    def _load(filename: str) -> bytes:
        filepath = MOCK_DATA_DIR / filename
        if not filepath.exists():
            raise FileNotFoundError(
                f"Required mock binary file does not exist: {filepath}. Please add the file to tests/mock_data/."
            )
        with open(filepath, "rb") as f:
            return f.read()

    return _load
