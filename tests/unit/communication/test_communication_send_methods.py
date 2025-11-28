"""
Additional tests for communication.py focusing on untested methods.

Tests cover send methods, error handling, and payload validation.
"""

from unittest.mock import Mock, patch

from xbee.core.communication import CommunicationManager, MessageFormatter


class TestSendControllerData:
    """Test send_controller_data method."""

    def test_send_controller_data_success(self):
        """Test successful controller data send."""
        cm = CommunicationManager(simulation_mode=True)
        cm.hardware_com = Mock()
        cm.hardware_com.send_package.return_value = True

        xbox_data = {"ly": 0.5, "ry": 0.5}
        n64_data = {}
        result = cm.send_controller_data(xbox_data, n64_data, reverse_mode=False)

        assert result is True
        cm.hardware_com.send_package.assert_called_once()

    @patch("xbee.core.communication.logger")
    def test_send_controller_data_exception_logged(self, mock_logger):
        """Test exception in send_controller_data is logged."""
        cm = CommunicationManager(simulation_mode=True)
        # Patch send_package to raise exception
        with patch.object(cm, "send_package", side_effect=Exception("Send failed")):
            result = cm.send_controller_data({}, {}, reverse_mode=False)

        assert result is False
        mock_logger.exception.assert_called_once()


class TestMessageFormatter:
    """Test MessageFormatter class."""

    def test_create_xbox_message(self):
        """Test creating Xbox message."""
        formatter = MessageFormatter()

        xbox_values = {"ly": 0.0, "ry": 0.0}
        message = formatter.create_xbox_message(xbox_values, reverse_mode=False)

        assert isinstance(message, (list, bytes, bytearray))

    def test_create_n64_message(self):
        """Test creating N64 message."""
        formatter = MessageFormatter()

        n64_values = {"A": False, "B": False}
        message = formatter.create_n64_message(n64_values)

        assert isinstance(message, (list, bytes, bytearray))

    def test_create_combined_message(self):
        """Test creating combined message."""
        formatter = MessageFormatter()

        xbox_values = {"ly": 0.0, "ry": 0.0}
        n64_values = {"A": False}
        message = formatter.create_combined_message(xbox_values, n64_values)

        assert isinstance(message, (list, bytes, bytearray))


class TestSendMethods:
    """Test various send methods."""

    def test_send_quit_message(self):
        """Test sending quit message."""
        cm = CommunicationManager(simulation_mode=True)
        cm.hardware_com = Mock()
        cm.hardware_com.send_package.return_value = True

        result = cm.send_quit_message()

        assert result is True

    def test_send_heartbeat_default_timestamp(self):
        """Test sending heartbeat with default timestamp."""
        cm = CommunicationManager(simulation_mode=True)
        cm.hardware_com = Mock()
        cm.hardware_com.send_package.return_value = True

        result = cm.send_heartbeat()

        assert result is True

    def test_send_heartbeat_custom_timestamp(self):
        """Test sending heartbeat with custom timestamp."""
        cm = CommunicationManager(simulation_mode=True)
        cm.hardware_com = Mock()
        cm.hardware_com.send_package.return_value = True

        result = cm.send_heartbeat(timestamp_ms=1234)

        assert result is True


class TestMessageValidation:
    """Test message payload validation."""

    def test_send_package_with_valid_bytes(self):
        """Test send_package accepts valid bytes."""
        cm = CommunicationManager(simulation_mode=True)
        cm.hardware_com = Mock()
        cm.hardware_com.send_package.return_value = True

        result = cm.send_package(b"\xaa\xbb\xcc")

        assert result is True

    def test_send_package_with_bytearray(self):
        """Test send_package accepts bytearray."""
        cm = CommunicationManager(simulation_mode=True)
        cm.hardware_com = Mock()
        cm.hardware_com.send_package.return_value = True

        result = cm.send_package(bytearray([0xAA, 0xBB]))

        assert result is True

    def test_send_compact_message_with_list(self):
        """Test send_compact_message accepts list of ints."""
        cm = CommunicationManager(simulation_mode=True)
        cm.hardware_com = Mock()
        cm.hardware_com.send_package.return_value = True

        result = cm.send_compact_message([0xAA, 0xBB, 0xCC])

        assert result is True

    @patch("xbee.core.communication.logger")
    def test_send_compact_message_exception_logged(self, mock_logger):
        """Test send_compact_message exception is logged."""
        cm = CommunicationManager(simulation_mode=True)
        cm.hardware_com = Mock()
        cm.hardware_com.send_package.side_effect = Exception("Error")

        result = cm.send_compact_message([0xAA])

        assert result is False
        mock_logger.exception.assert_called()
