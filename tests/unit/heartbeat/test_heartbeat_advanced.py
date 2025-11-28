"""
Tests for HeartbeatManager advanced functionality.
"""

from unittest.mock import Mock

from xbee.core.heartbeat import HeartbeatManager


class TestHeartbeatManagerAdvanced:
    """Test HeartbeatManager advanced functionality."""

    def test_send_heartbeat_disabled(self):
        """Test send_heartbeat returns False when disabled."""
        mock_comm = Mock()
        mock_comm.enabled = False
        manager = HeartbeatManager(mock_comm)

        result = manager.send_heartbeat()

        assert result is False
        mock_comm.send_heartbeat.assert_not_called()

    def test_send_heartbeat_failure(self):
        """Test send_heartbeat handles failure correctly."""
        mock_comm = Mock()
        mock_comm.enabled = True
        mock_comm.send_heartbeat.return_value = False
        manager = HeartbeatManager(mock_comm)

        result = manager.send_heartbeat()

        assert result is False
        # Last heartbeat time should not be updated on failure
        assert manager._last_heartbeat_time == 0

    def test_update_sends_when_due(self):
        """Test update sends heartbeat when due."""
        mock_comm = Mock()
        mock_comm.enabled = True
        mock_comm.send_heartbeat.return_value = True
        manager = HeartbeatManager(mock_comm)
        manager.set_interval(0)  # Always due
        manager.reset_heartbeat()

        result = manager.update()

        assert result is True
        mock_comm.send_heartbeat.assert_called_once()

    def test_update_skips_when_not_due(self):
        """Test update skips heartbeat when not due."""
        mock_comm = Mock()
        mock_comm.enabled = True
        mock_comm.send_heartbeat.return_value = True
        manager = HeartbeatManager(mock_comm)
        manager.set_interval(10**18)  # Very long interval
        # Set last heartbeat to now (not due)
        import time

        manager._last_heartbeat_time = time.time_ns()

        result = manager.update()

        assert result is False
        mock_comm.send_heartbeat.assert_not_called()

    def test_set_interval(self):
        """Test set_interval changes the interval."""
        mock_comm = Mock()
        mock_comm.enabled = True
        manager = HeartbeatManager(mock_comm)

        manager.set_interval(500_000_000)  # 500ms

        assert manager.get_interval() == 500_000_000

    def test_reset_heartbeat(self):
        """Test reset_heartbeat resets the last heartbeat time."""
        mock_comm = Mock()
        mock_comm.enabled = True
        mock_comm.send_heartbeat.return_value = True
        manager = HeartbeatManager(mock_comm)

        # Send a heartbeat to set last_heartbeat_time
        manager.send_heartbeat()
        assert manager._last_heartbeat_time > 0

        # Reset
        manager.reset_heartbeat()
        assert manager._last_heartbeat_time == 0
