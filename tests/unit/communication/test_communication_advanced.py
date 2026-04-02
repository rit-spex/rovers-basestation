"""
Tests for CommunicationManager message sending methods.
"""

from unittest.mock import Mock, patch

import pytest

from xbee.communication.manager import CommunicationManager, MessageFormatter
from xbee.config.constants import CONSTANTS


class TestMessageFormatterAdvanced:
    """Test MessageFormatter advanced functionality."""

    def test_create_xbox_message_reverse_mode(self):
        """Test Xbox message creation in reverse mode swaps Y axes."""
        formatter = MessageFormatter()

        values = {
            CONSTANTS.XBOX.JOYSTICK.AXIS_LY: 150,
            CONSTANTS.XBOX.JOYSTICK.AXIS_RY: 50,
        }

        message_normal = formatter.create_xbox_message(values, reverse_mode=False)
        message_reverse = formatter.create_xbox_message(values, reverse_mode=True)

        # In reverse mode, LY and RY should be swapped
        assert message_normal != message_reverse

    def test_create_combined_message(self):
        """Test combined message creation includes start byte."""
        formatter = MessageFormatter()

        xbox_values = {}
        n64_values = {}

        message = formatter.create_combined_message(xbox_values, n64_values)

        # First byte should be START_MESSAGE
        start_byte = int.from_bytes(CONSTANTS.START_MESSAGE, byteorder="big")
        assert message[0] == start_byte


class TestCommunicationManagerControllerData:
    """Test CommunicationManager controller data sending."""

    def test_send_controller_data_empty_values(self):
        """Test sending controller data with empty values."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.return_value = True

        result = comm.send_controller_data({}, {}, reverse_mode=False)

        assert result is True

    def test_send_controller_data_xbox_only(self):
        """Test sending controller data with only Xbox values."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.return_value = True

        xbox_values = {CONSTANTS.XBOX.JOYSTICK.AXIS_LY: 100}

        result = comm.send_controller_data(xbox_values, {}, reverse_mode=False)

        assert result is True

    def test_send_controller_data_n64_only(self):
        """Test sending controller data with only N64 values."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.return_value = True

        n64_values = {CONSTANTS.N64.BUTTON.A: 1}

        result = comm.send_controller_data({}, n64_values, reverse_mode=False)

        assert result is True

    def test_send_controller_data_duplicate_suppression(self):
        """Test duplicate controller data is suppressed."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.return_value = True

        xbox_values = {CONSTANTS.XBOX.JOYSTICK.AXIS_LY: 100}

        # First send
        result1 = comm.send_controller_data(xbox_values, {}, reverse_mode=False)
        # Second send with same values (should be suppressed)
        result2 = comm.send_controller_data(xbox_values, {}, reverse_mode=False)

        assert result1 is True
        assert result2 is True
        # Only one call should have been made (second suppressed)
        assert comm.hardware_com.send_package.call_count == 1


class TestCommunicationManagerPackageValidation:
    """Test CommunicationManager package payload validation."""

    def test_normalize_package_payload_bytes(self):
        """Test normalizing bytes payload."""
        comm = CommunicationManager(simulation_mode=True)

        result = comm._normalize_package_payload(b"\x01\x02\x03")

        assert result == b"\x01\x02\x03"

    def test_normalize_package_payload_bytearray(self):
        """Test normalizing bytearray payload."""
        comm = CommunicationManager(simulation_mode=True)

        result = comm._normalize_package_payload(bytearray([1, 2, 3]))

        assert result == bytearray([1, 2, 3])

    def test_normalize_package_payload_list_of_ints(self):
        """Test normalizing list of ints payload."""
        comm = CommunicationManager(simulation_mode=True)

        result = comm._normalize_package_payload([1, 2, 3])

        assert result == [1, 2, 3]

    def test_normalize_package_payload_list_with_bytes(self):
        """Test normalizing list with bytes-like elements."""
        comm = CommunicationManager(simulation_mode=True)

        result = comm._normalize_package_payload([b"\x01", 2, b"\x03"])

        assert result == b"\x01\x02\x03"

    def test_normalize_package_payload_invalid_int(self):
        """Test normalizing list with out-of-range int raises error."""
        comm = CommunicationManager(simulation_mode=True)

        with pytest.raises(ValueError, match="out of range"):
            comm._normalize_package_payload([256])

    def test_normalize_package_payload_negative_int(self):
        """Test normalizing list with negative int raises error."""
        comm = CommunicationManager(simulation_mode=True)

        with pytest.raises(ValueError, match="out of range"):
            comm._normalize_package_payload([-1])

    def test_normalize_package_payload_invalid_type(self):
        """Test normalizing unsupported type raises error."""
        comm = CommunicationManager(simulation_mode=True)

        with pytest.raises(ValueError, match="Unsupported data type"):
            comm._normalize_package_payload(["string"])  # type: ignore[arg-type]

    def test_validate_compact_message_list_invalid_sequence(self):
        """Test validating non-sequence raises TypeError."""
        comm = CommunicationManager(simulation_mode=True)

        with pytest.raises(TypeError, match="must be a sequence"):
            comm._validate_compact_message_list(123)  # type: ignore[arg-type]  # noqa


class TestCommunicationManagerRetry:
    """Test CommunicationManager retry logic."""

    def test_send_package_with_retry_success_on_first(self):
        """Test send_package succeeds on first try with retries configured."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.return_value = True

        result = comm.send_package(b"\x01\x02", retry_count=3)

        assert result is True
        assert comm.hardware_com.send_package.call_count == 1

    def test_send_package_with_retry_success_on_retry(self):
        """Test send_package succeeds on retry attempt."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.side_effect = [False, False, True]

        with patch("xbee.communication.manager.logger"):
            result = comm.send_package(b"\x01\x02", retry_count=3)

        assert result is True
        assert comm.hardware_com.send_package.call_count == 3

    def test_send_package_all_retries_fail(self):
        """Test send_package fails after all retries exhausted."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.return_value = False

        with patch("xbee.communication.manager.logger"):
            result = comm.send_package(b"\x01\x02", retry_count=2)

        assert result is False
        assert comm.hardware_com.send_package.call_count == 3  # 1 initial + 2 retries


class TestCommunicationManagerCompactMessage:
    """Test CommunicationManager compact message sending."""

    def test_send_compact_message_success(self):
        """Test send_compact_message sends successfully."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.return_value = True

        result = comm.send_compact_message([0xAB, 0x01])

        assert result is True

    def test_send_compact_message_type_error_fallback(self):
        """Test send_compact_message falls back when TypeError raised."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        # First call raises TypeError, subsequent call succeeds
        comm.hardware_com.send_package.side_effect = [TypeError("Not bytes"), True]

        with patch("xbee.communication.manager.logger"):
            result = comm.send_compact_message([0xAB, 0x01])

        assert result is True

    def test_send_compact_message_exception(self):
        """Test send_compact_message handles general exceptions."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.side_effect = RuntimeError("Network error")

        with patch("xbee.communication.manager.logger"):
            result = comm.send_compact_message([0xAB, 0x01])

        assert result is False


class TestCommunicationManagerEnableDisable:
    """Test CommunicationManager enable/disable functionality."""

    def test_enable_communication(self):
        """Test enabling communication."""
        comm = CommunicationManager(simulation_mode=True)
        comm.disable()
        assert comm.enabled is False

        comm.enable()
        assert comm.enabled is True

    def test_disable_communication(self):
        """Test disabling communication."""
        comm = CommunicationManager(simulation_mode=True)
        assert comm.enabled is True

        comm.disable()
        assert comm.enabled is False
