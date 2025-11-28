"""
Tests for UdpCommunicationManager advanced functionality.
"""

import json
import logging
import time
from unittest.mock import Mock, patch

import pytest

from xbee.core.udp_communication import (
    SimulationCommunicationManager,
    UdpCommunicationManager,
    UdpMessage,
)


class TestUdpMessage:
    """Test UdpMessage class."""

    def test_udp_message_creation(self):
        """Test UdpMessage object creation."""
        msg = UdpMessage("test", {"key": "value"}, timestamp=12345.0)

        assert msg.message_type == "test"
        assert msg.data == {"key": "value"}
        assert msg.timestamp is not None and abs(msg.timestamp - 12345.0) < 0.001

    def test_udp_message_to_json(self):
        """Test UdpMessage JSON serialization."""
        msg = UdpMessage("test", {"key": "value"}, timestamp=12345.0)

        json_str = msg.to_json()
        parsed = json.loads(json_str)

        assert parsed["type"] == "test"
        assert parsed["data"] == {"key": "value"}
        assert abs(parsed["timestamp"] - 12345.0) < 0.001

    def test_udp_message_to_json_auto_timestamp(self):
        """Test UdpMessage JSON serialization with auto timestamp."""
        msg = UdpMessage("test", {"key": "value"})

        json_str = msg.to_json()
        parsed = json.loads(json_str)

        assert "timestamp" in parsed
        assert parsed["timestamp"] > 0

    def test_udp_message_from_json(self):
        """Test UdpMessage JSON deserialization."""
        json_str = '{"type": "test", "data": {"key": "value"}, "timestamp": 12345.0}'

        msg = UdpMessage.from_json(json_str)

        assert msg.message_type == "test"
        assert msg.data == {"key": "value"}
        assert msg.timestamp is not None and abs(msg.timestamp - 12345.0) < 0.001

    def test_udp_message_from_json_missing_type(self):
        """Test UdpMessage from_json raises for missing type."""
        json_str = '{"data": {"key": "value"}}'

        with pytest.raises(ValueError, match="Missing required field 'type'"):
            UdpMessage.from_json(json_str)

    def test_udp_message_from_json_missing_data(self):
        """Test UdpMessage from_json raises for missing data."""
        json_str = '{"type": "test"}'

        with pytest.raises(ValueError, match="Missing required field 'data'"):
            UdpMessage.from_json(json_str)


class TestUdpCommunicationManagerAdvanced:
    """Test UdpCommunicationManager advanced functionality."""

    @patch("socket.socket")
    def test_start_multiple_times(self, mock_socket_class):
        """Test start is idempotent."""
        mock_socket = Mock()
        mock_socket_class.return_value = mock_socket

        manager = UdpCommunicationManager()
        manager.start()
        manager.start()  # Second call should be no-op

        assert manager.running is True
        # Ensure we stop the manager to avoid leaking background threads across tests
        manager.stop()

    @patch("socket.socket")
    def test_receive_loop_handles_non_iterable_recvfrom(
        self, mock_socket_class, caplog
    ):
        """Ensure receive loop doesn't crash when recvfrom returns a non-iterable mock."""
        mock_socket = Mock()
        # Simulate recvfrom returning a Mock (non-iterable) object on first call and
        # then raising a socket.timeout to let the loop continue and eventually stop
        import socket

        # Return a Mock once, then raise socket.timeout repeatedly so the loop can
        # continue without exhausting the side_effect list (which causes StopIteration).
        # Track first call via closure variable to avoid setting attributes on the
        # function object (which static-analysis complains about).
        side_effect_state = {"called": False}

        def _recvfrom_side_effect(*_args, **_kwargs):
            if not side_effect_state["called"]:
                side_effect_state["called"] = True
                return Mock()
            raise socket.timeout()

        mock_socket.recvfrom.side_effect = _recvfrom_side_effect
        mock_socket_class.return_value = mock_socket
        manager = UdpCommunicationManager()

        # Start via the public API so sockets are bound and the receive thread is
        # created normally (this exercises the intended code path).
        manager.start()

        # Ensure the background thread started
        thread = getattr(manager, "receive_thread", None)
        assert thread is not None
        assert thread.is_alive()

        # Let the loop run briefly so the mocked recvfrom() is called
        with caplog.at_level(logging.ERROR):
            time.sleep(0.05)

            # Stop the manager and join thread
            manager.stop()
            if thread is not None:
                thread.join(timeout=1.0)

            # At least one call to recvfrom should have been made
            assert mock_socket.recvfrom.call_count >= 1

            # The receive thread should have finished and not be alive
            assert not (thread and thread.is_alive())

            # Ensure no ERROR level logs occurred (i.e., no unhandled exceptions)
            assert not any(rec.levelno >= logging.ERROR for rec in caplog.records)

    @patch("socket.socket")
    def test_stop_multiple_times(self, mock_socket_class):
        """Test stop is idempotent."""
        mock_socket = Mock()
        mock_socket_class.return_value = mock_socket

        manager = UdpCommunicationManager()
        manager.start()
        manager.stop()
        manager.stop()  # Second call should be no-op

        assert manager.running is False

    @patch("socket.socket")
    def test_stop_without_start(self, mock_socket_class):
        """Test stop when never started."""
        mock_socket = Mock()
        mock_socket_class.return_value = mock_socket

        manager = UdpCommunicationManager()
        manager.stop()  # Should not raise

        assert manager.running is False

    @patch("socket.socket")
    def test_send_controller_data(self, mock_socket_class):
        """Test sending controller data."""
        mock_socket = Mock()
        mock_socket_class.return_value = mock_socket

        manager = UdpCommunicationManager()
        result = manager.send_controller_data(
            {"ly": 0.5}, {"a": True}, reverse_mode=False
        )

        assert result is True
        mock_socket.sendto.assert_called()

    @patch("socket.socket")
    def test_send_quit_message(self, mock_socket_class):
        """Test sending quit message."""
        mock_socket = Mock()
        mock_socket_class.return_value = mock_socket

        manager = UdpCommunicationManager()
        result = manager.send_quit_message()

        assert result is True
        mock_socket.sendto.assert_called()

    @patch("socket.socket")
    def test_send_heartbeat(self, mock_socket_class):
        """Test sending heartbeat."""
        mock_socket = Mock()
        mock_socket_class.return_value = mock_socket

        manager = UdpCommunicationManager()
        result = manager.send_heartbeat()

        assert result is True
        mock_socket.sendto.assert_called()

    @patch("socket.socket")
    def test_validate_payload_invalid_int(self, mock_socket_class):
        """Test payload validation raises for invalid int."""
        mock_socket = Mock()
        mock_socket_class.return_value = mock_socket

        manager = UdpCommunicationManager()

        with pytest.raises(ValueError, match="out of range"):
            manager._validate_payload([256])

    @patch("socket.socket")
    def test_validate_payload_invalid_type(self, mock_socket_class):
        """Test payload validation raises for invalid type."""
        mock_socket = Mock()
        mock_socket_class.return_value = mock_socket

        manager = UdpCommunicationManager()

        with pytest.raises(ValueError, match="Unsupported data type"):
            manager._validate_payload(["string"])  # type: ignore[arg-type]

    @patch("socket.socket")
    def test_get_statistics(self, mock_socket_class):
        """Test get_statistics returns correct data."""
        mock_socket = Mock()
        mock_socket_class.return_value = mock_socket

        manager = UdpCommunicationManager()
        manager.messages_sent = 10
        manager.messages_received = 5

        stats = manager.get_statistics()

        assert stats["messages_sent"] == 10
        assert stats["messages_received"] == 5
        assert "running" in stats

    @patch("socket.socket")
    def test_register_message_handler(self, mock_socket_class):
        """Test registering message handler."""
        mock_socket = Mock()
        mock_socket_class.return_value = mock_socket

        manager = UdpCommunicationManager()
        handler = Mock()

        manager.register_message_handler("test", handler)

        assert "test" in manager.message_handlers


class TestSimulationCommunicationManager:
    """Test SimulationCommunicationManager."""

    @patch("xbee.core.udp_communication.UdpCommunicationManager")
    def test_initialization(self, mock_udp_manager):
        """Test SimulationCommunicationManager initialization."""
        mock_instance = Mock()
        mock_udp_manager.return_value = mock_instance

        _ = SimulationCommunicationManager()

        # auto_start=True is passed to UdpCommunicationManager
        mock_udp_manager.assert_called_once_with(auto_start=True)

    @patch("xbee.core.udp_communication.UdpCommunicationManager")
    def test_initialization_no_auto_start(self, mock_udp_manager):
        """Test initialization without auto start."""
        mock_instance = Mock()
        mock_udp_manager.return_value = mock_instance

        _ = SimulationCommunicationManager(auto_start=False)

        # auto_start=False is passed to UdpCommunicationManager
        mock_udp_manager.assert_called_once_with(auto_start=False)

    @patch("xbee.core.udp_communication.UdpCommunicationManager")
    def test_send_controller_data(self, mock_udp_manager):
        """Test sending controller data through simulation manager."""
        mock_instance = Mock()
        mock_instance.send_controller_data.return_value = True
        mock_udp_manager.return_value = mock_instance

        sim = SimulationCommunicationManager()
        result = sim.send_controller_data({"ly": 0.5}, {"a": True}, False)

        assert result is True
        mock_instance.send_controller_data.assert_called_once()

    @patch("xbee.core.udp_communication.UdpCommunicationManager")
    def test_send_quit_message(self, mock_udp_manager):
        """Test sending quit message through simulation manager."""
        mock_instance = Mock()
        mock_instance.send_quit_message.return_value = True
        mock_udp_manager.return_value = mock_instance

        sim = SimulationCommunicationManager()
        result = sim.send_quit_message()

        assert result is True
        mock_instance.send_quit_message.assert_called_once()

    @patch("xbee.core.udp_communication.UdpCommunicationManager")
    def test_send_heartbeat(self, mock_udp_manager):
        """Test sending heartbeat through simulation manager."""
        mock_instance = Mock()
        mock_instance.send_heartbeat.return_value = True
        mock_udp_manager.return_value = mock_instance

        sim = SimulationCommunicationManager()
        result = sim.send_heartbeat()

        assert result is True
        mock_instance.send_heartbeat.assert_called_once()

    @patch("xbee.core.udp_communication.UdpCommunicationManager")
    def test_register_telemetry_handler(self, mock_udp_manager):
        """Test registering telemetry handler."""
        mock_instance = Mock()
        mock_udp_manager.return_value = mock_instance

        sim = SimulationCommunicationManager()
        handler = Mock()
        sim.register_telemetry_handler(handler)

        mock_instance.register_message_handler.assert_called_once()

    @patch("xbee.core.udp_communication.UdpCommunicationManager")
    def test_cleanup(self, mock_udp_manager):
        """Test cleanup stops UDP manager."""
        mock_instance = Mock()
        mock_udp_manager.return_value = mock_instance

        sim = SimulationCommunicationManager()
        sim.cleanup()

        mock_instance.stop.assert_called_once()

    @patch("xbee.core.udp_communication.UdpCommunicationManager")
    def test_get_statistics(self, mock_udp_manager):
        """Test getting statistics from simulation manager."""
        mock_instance = Mock()
        mock_instance.get_statistics.return_value = {"messages_sent": 5}
        mock_udp_manager.return_value = mock_instance

        sim = SimulationCommunicationManager()
        stats = sim.get_statistics()

        assert stats == {"messages_sent": 5}
