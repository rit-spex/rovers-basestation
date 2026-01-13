"""
Edge case tests for communication.py covering error paths and boundary conditions.

These tests ensure the communication manager handles edge cases correctly.
"""

import threading
import time
from unittest.mock import Mock, patch

import pytest

from xbee.core.command_codes import CONSTANTS
from xbee.core.communication import CommunicationManager, MessageFormatter


class TestCommunicationManagerErrorPaths:
    """Test error handling in CommunicationManager."""

    def test_send_controller_data_with_send_failure(self):
        """Test send_controller_data handles hardware send failures."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.return_value = False

        result = comm.send_controller_data(
            {CONSTANTS.XBOX.JOYSTICK.AXIS_LY: 100}, {}, reverse_mode=False
        )

        # Should return False when hardware send fails
        assert result is False

    def test_send_controller_data_exception_in_formatter(self):
        """Test send_controller_data handles formatter exceptions via try-except."""
        comm = CommunicationManager(simulation_mode=True)

        # Make formatter raise a ValueError - this propagates through
        with patch.object(
            comm.formatter, "create_xbox_message", side_effect=ValueError("Bad data")
        ):
            # ValueError should propagate since it's a programming error
            with pytest.raises(ValueError):
                comm.send_controller_data({"invalid": "data"}, {}, reverse_mode=False)

    def test_send_package_with_valueerror_propagates(self):
        """Test that ValueError from hardware is propagated."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.side_effect = ValueError("Invalid byte")

        with pytest.raises(ValueError, match="Invalid byte"):
            comm.send_package(b"\x01\x02")

    def test_send_package_with_typeerror_propagates(self):
        """Test that TypeError from hardware is propagated."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.side_effect = TypeError("Wrong type")

        with pytest.raises(TypeError, match="Wrong type"):
            comm.send_package(b"\x01\x02")

    def test_send_gps_position_with_nan_coordinates(self):
        """Test send_gps_position handles NaN coordinates."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.return_value = True

        import math

        # NaN should still encode (struct.pack handles it)
        result = comm.send_gps_position(latitude=math.nan, longitude=math.nan)

        assert result is True

    def test_send_gps_position_with_infinity(self):
        """Test send_gps_position handles infinity."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.return_value = True

        import math

        result = comm.send_gps_position(latitude=math.inf, longitude=-math.inf)

        assert result is True


class TestMessageFormatterEdgeCases:
    """Test MessageFormatter edge cases."""

    def test_create_xbox_message_with_empty_values(self):
        """Test Xbox message creation with empty values uses defaults."""
        formatter = MessageFormatter()

        message = formatter.create_xbox_message({}, reverse_mode=False)

        assert isinstance(message, list)
        assert len(message) > 0

    def test_create_xbox_message_reverse_mode_with_missing_axes(self):
        """Test reverse mode works when some axes are missing."""
        formatter = MessageFormatter()

        # Only provide one axis
        values = {CONSTANTS.XBOX.JOYSTICK.AXIS_LY: 150}

        message = formatter.create_xbox_message(values, reverse_mode=True)

        assert isinstance(message, list)
        assert len(message) > 0

    def test_create_combined_message_preserves_start_byte(self):
        """Test combined message always has START_MESSAGE as first byte."""
        formatter = MessageFormatter()

        for _ in range(10):
            message = formatter.create_combined_message({}, {})
            start_byte = int.from_bytes(CONSTANTS.START_MESSAGE, byteorder="big")
            assert message[0] == start_byte

    def test_create_n64_message_ignores_axis_collision_values(self):
        """N64 message encoding should ignore axis-like keys/values.

        Regression: N64 axis indices overlap with button indices (e.g., 0/1).
        If an axis value leaks into the dict under a colliding numeric key, the
        encoder must not interpret it as a 2-bit button value.
        """

        formatter = MessageFormatter()

        # Simulate a bad mixed dict (axis value under numeric 0) alongside proper
        # button values.
        values = {
            CONSTANTS.N64.JOYSTICK.AXIS_X: 173,  # collides with C_DOWN numeric index
            CONSTANTS.N64.BUTTON.A_STR: CONSTANTS.N64.BUTTON.ON,
            CONSTANTS.N64.BUTTON.C_DOWN_STR: CONSTANTS.N64.BUTTON.OFF,
        }

        message = formatter.create_n64_message(values)

        assert isinstance(message, list)
        assert len(message) > 0


class TestDuplicateSuppressionEdgeCases:
    """Test duplicate suppression edge cases."""

    def test_different_messages_not_suppressed(self):
        """Test that different messages are not suppressed."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.return_value = True

        # Send different messages
        values1 = {CONSTANTS.XBOX.JOYSTICK.AXIS_LY: 100}
        values2 = {CONSTANTS.XBOX.JOYSTICK.AXIS_LY: 150}

        comm.send_controller_data(values1, {}, reverse_mode=False)
        comm.send_controller_data(values2, {}, reverse_mode=False)

        # Both should have been sent
        assert comm.hardware_com.send_package.call_count == 2

    def test_duplicate_combined_message_suppressed(self):
        """Test duplicate combined messages are suppressed."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.return_value = True

        # Send same empty message twice
        comm.send_controller_data({}, {}, reverse_mode=False)
        comm.send_controller_data({}, {}, reverse_mode=False)

        # Second should be suppressed
        assert comm.hardware_com.send_package.call_count == 1

    def test_duplicate_suppression_resets_on_different_message(self):
        """Test duplicate suppression tracking resets correctly."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.return_value = True

        values_a = {CONSTANTS.XBOX.JOYSTICK.AXIS_LY: 100}
        values_b = {CONSTANTS.XBOX.JOYSTICK.AXIS_LY: 150}

        # A, B, A sequence should send all three
        comm.send_controller_data(values_a, {}, reverse_mode=False)
        comm.send_controller_data(values_b, {}, reverse_mode=False)
        comm.send_controller_data(values_a, {}, reverse_mode=False)

        assert comm.hardware_com.send_package.call_count == 3


class TestSendMethodsBoundaryValues:
    """Test send methods with boundary values."""

    def test_send_sensor_reading_at_zero(self):
        """Test sensor reading at minimum value."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.return_value = True

        result = comm.send_sensor_reading(sensor_id=0, reading=0)

        assert result is True

    def test_send_sensor_reading_at_max(self):
        """Test sensor reading at maximum value."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.return_value = True

        result = comm.send_sensor_reading(sensor_id=255, reading=65535)

        assert result is True

    def test_send_status_update_all_zeros(self):
        """Test status update with all zero values."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.return_value = True

        result = comm.send_status_update(
            status_code=0, battery_level=0, signal_strength=0
        )

        assert result is True

    def test_send_status_update_all_max(self):
        """Test status update with max values (truncated to byte)."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.return_value = True

        result = comm.send_status_update(
            status_code=1000,  # Will be masked to 0xE8
            battery_level=100,
            signal_strength=100,
        )

        assert result is True

    def test_send_error_code_high_values(self):
        """Test error code with high values."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.return_value = True

        result = comm.send_error_code(error_code=0xFF, severity=0xFF)

        assert result is True


class TestCompactMessageValidation:
    """Test compact message validation edge cases."""

    def test_validate_compact_message_with_empty_list(self):
        """Test validating empty list passes."""
        comm = CommunicationManager(simulation_mode=True)

        # Should not raise
        comm._validate_compact_message_list([])

    def test_validate_compact_message_with_single_byte(self):
        """Test validating single byte list."""
        comm = CommunicationManager(simulation_mode=True)

        # Should not raise
        comm._validate_compact_message_list([0x00])

    def test_validate_compact_message_with_max_bytes(self):
        """Test validating list with all max values."""
        comm = CommunicationManager(simulation_mode=True)

        # Should not raise
        comm._validate_compact_message_list([255] * 100)

    def test_normalize_payload_with_memoryview(self):
        """Test normalizing memoryview payload."""
        comm = CommunicationManager(simulation_mode=True)

        data = memoryview(b"\x01\x02\x03")
        result = comm._normalize_package_payload(data)

        assert result == data


class TestRetryLogicEdgeCases:
    """Test retry logic edge cases."""

    def test_send_package_retry_with_intermittent_failure(self):
        """Test retry succeeds after intermittent failures."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        # Fail twice, then succeed
        comm.hardware_com.send_package.side_effect = [False, False, True]

        with patch("xbee.core.communication.logger"):
            result = comm.send_package(b"\x01", retry_count=5)

        assert result is True
        assert comm.hardware_com.send_package.call_count == 3

    def test_send_package_zero_retries(self):
        """Test send_package with zero retries only tries once."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.return_value = False

        result = comm.send_package(b"\x01", retry_count=0)

        assert result is False
        assert comm.hardware_com.send_package.call_count == 1

    def test_quit_message_uses_retries(self):
        """Test quit message uses retry logic."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        # Fail twice, succeed on third
        comm.hardware_com.send_package.side_effect = [False, False, True]

        with patch("xbee.core.communication.logger"):
            result = comm.send_quit_message()

        assert result is True
        # Quit uses retry_count=3, so should try 3 times (initial + 2 retries)
        # But it succeeds on third, so exactly 3 calls


class TestConcurrencyEdgeCases:
    """Test concurrency-related edge cases."""

    def test_concurrent_send_different_messages(self):
        """Test concurrent sends of different messages."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.return_value = True

        results = []
        errors = []

        def send_message(msg_id):
            try:
                result = comm.send_package(bytes([msg_id]))
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=send_message, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        assert all(r is True for r in results)

    def test_enable_disable_during_send(self):
        """Test enabling/disabling during sends is safe."""
        comm = CommunicationManager(simulation_mode=True)
        comm.hardware_com = Mock()
        comm.hardware_com.send_package.return_value = True

        errors = []

        def toggle_enable():
            for _ in range(50):
                comm.enable()
                time.sleep(0.001)
                comm.disable()
                time.sleep(0.001)

        def send_messages():
            for i in range(50):
                try:
                    comm.send_package(bytes([i % 256]))
                except Exception as e:
                    errors.append(e)

        toggle_thread = threading.Thread(target=toggle_enable)
        send_thread = threading.Thread(target=send_messages)

        toggle_thread.start()
        send_thread.start()

        toggle_thread.join(timeout=5)
        send_thread.join(timeout=5)

        # Should complete without errors
        assert len(errors) == 0
