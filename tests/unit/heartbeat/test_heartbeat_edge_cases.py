"""
Edge case tests for heartbeat.py covering timing boundary conditions.

These tests ensure the heartbeat manager handles edge cases correctly.
"""

import threading
import time
from unittest.mock import Mock

from xbee.core.heartbeat import HeartbeatManager


class TestHeartbeatTimingEdgeCases:
    """Test heartbeat timing edge cases."""

    def test_should_send_heartbeat_immediately_after_reset(self):
        """Test heartbeat is due immediately after reset."""
        mock_comm = Mock()
        mock_comm.enabled = True
        manager = HeartbeatManager(mock_comm)

        manager.reset_heartbeat()

        assert manager.should_send_heartbeat() is True

    def test_should_not_send_heartbeat_immediately_after_send(self):
        """Test heartbeat is not due immediately after sending."""
        mock_comm = Mock()
        mock_comm.enabled = True
        mock_comm.send_heartbeat.return_value = True
        manager = HeartbeatManager(mock_comm)

        manager.send_heartbeat()

        # Should not be due immediately
        assert manager.should_send_heartbeat() is False

    def test_heartbeat_with_very_short_interval(self):
        """Test heartbeat with very short interval (1ms)."""
        mock_comm = Mock()
        mock_comm.enabled = True
        mock_comm.send_heartbeat.return_value = True
        manager = HeartbeatManager(mock_comm)
        manager.set_interval(1_000_000)  # 1ms in ns

        manager.reset_heartbeat()
        time.sleep(0.002)  # Wait 2ms

        assert manager.should_send_heartbeat() is True

    def test_heartbeat_with_very_long_interval(self):
        """Test heartbeat with very long interval (1 hour)."""
        mock_comm = Mock()
        mock_comm.enabled = True
        manager = HeartbeatManager(mock_comm)
        manager.set_interval(3_600_000_000_000)  # 1 hour in ns

        manager.send_heartbeat()

        assert manager.should_send_heartbeat() is False

    def test_update_returns_false_when_not_due(self):
        """Test update returns False when heartbeat not due."""
        mock_comm = Mock()
        mock_comm.enabled = True
        mock_comm.send_heartbeat.return_value = True
        manager = HeartbeatManager(mock_comm)
        manager.set_interval(1_000_000_000_000)  # 1000 seconds

        # First send
        manager.send_heartbeat()

        # Update should return False since not due
        result = manager.update()
        assert result is False

    def test_update_returns_true_when_due(self):
        """Test update returns True when heartbeat is due."""
        mock_comm = Mock()
        mock_comm.enabled = True
        mock_comm.send_heartbeat.return_value = True
        manager = HeartbeatManager(mock_comm)
        manager.set_interval(1_000_000)  # 1ms

        manager.reset_heartbeat()
        time.sleep(0.002)

        result = manager.update()
        assert result is True


class TestHeartbeatCommunicationDisabled:
    """Test heartbeat behavior when communication is disabled."""

    def test_send_heartbeat_when_disabled(self):
        """Test heartbeat is not sent when communication disabled."""
        mock_comm = Mock()
        mock_comm.enabled = False
        manager = HeartbeatManager(mock_comm)

        result = manager.send_heartbeat()

        assert result is False
        mock_comm.send_heartbeat.assert_not_called()

    def test_update_when_disabled(self):
        """Test update when communication disabled."""
        mock_comm = Mock()
        mock_comm.enabled = False
        manager = HeartbeatManager(mock_comm)
        manager.reset_heartbeat()

        result = manager.update()

        assert result is False


class TestHeartbeatSendFailure:
    """Test heartbeat behavior when send fails."""

    def test_send_failure_does_not_update_last_time(self):
        """Test failed send does not update last heartbeat time."""
        mock_comm = Mock()
        mock_comm.enabled = True
        mock_comm.send_heartbeat.return_value = False
        manager = HeartbeatManager(mock_comm)
        manager.reset_heartbeat()

        initial_time = manager._last_heartbeat_time

        result = manager.send_heartbeat()

        assert result is False
        # Last heartbeat time should not have changed
        assert manager._last_heartbeat_time == initial_time

    def test_send_success_updates_last_time(self):
        """Test successful send updates last heartbeat time."""
        mock_comm = Mock()
        mock_comm.enabled = True
        mock_comm.send_heartbeat.return_value = True
        manager = HeartbeatManager(mock_comm)
        manager.reset_heartbeat()

        result = manager.send_heartbeat()

        assert result is True
        # Last heartbeat time should have been updated
        assert manager._last_heartbeat_time > 0


class TestHeartbeatIntervalConfiguration:
    """Test heartbeat interval configuration."""

    def test_set_interval_zero(self):
        """Test setting interval to zero."""
        mock_comm = Mock()
        mock_comm.enabled = True
        manager = HeartbeatManager(mock_comm)

        manager.set_interval(0)

        assert manager.get_interval() == 0
        # Should always be due
        assert manager.should_send_heartbeat() is True

    def test_set_interval_negative(self):
        """Test setting negative interval (implementation dependent)."""
        mock_comm = Mock()
        mock_comm.enabled = True
        manager = HeartbeatManager(mock_comm)

        # Depending on implementation, this might always be due
        manager.set_interval(-1)

        # At minimum, get_interval should return what was set
        assert manager.get_interval() == -1

    def test_get_interval_default(self):
        """Test default interval is from CONSTANTS."""
        from xbee.core.command_codes import CONSTANTS

        mock_comm = Mock()
        manager = HeartbeatManager(mock_comm)

        assert manager.get_interval() == CONSTANTS.HEARTBEAT.INTERVAL


class TestHeartbeatConcurrency:
    """Test heartbeat manager in concurrent scenarios."""

    def test_concurrent_update_calls(self):
        """Test concurrent update calls are safe."""
        mock_comm = Mock()
        mock_comm.enabled = True
        mock_comm.send_heartbeat.return_value = True
        manager = HeartbeatManager(mock_comm)
        manager.set_interval(1_000)  # Very short interval

        results = []
        errors = []

        def call_update():
            try:
                for _ in range(100):
                    result = manager.update()
                    results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=call_update) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
            assert not t.is_alive(), "Thread did not complete within timeout"

        assert len(errors) == 0

    def test_concurrent_interval_changes(self):
        """Test concurrent interval changes are safe."""
        mock_comm = Mock()
        mock_comm.enabled = True
        manager = HeartbeatManager(mock_comm)

        errors = []

        def change_interval():
            try:
                for i in range(100):
                    manager.set_interval(i * 1_000_000)
            except Exception as e:
                errors.append(e)

        def check_interval():
            try:
                for _ in range(100):
                    _ = manager.get_interval()
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=change_interval),
            threading.Thread(target=check_interval),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
            assert not t.is_alive(), "Thread did not complete within timeout"

        assert len(errors) == 0


class TestHeartbeatTimingAccuracy:
    """Test heartbeat timing accuracy under various conditions."""

    def test_timing_drift_over_multiple_sends(self, monkeypatch):
        """Test that timing doesn't drift significantly over multiple sends."""
        mock_comm = Mock()
        mock_comm.enabled = True
        mock_comm.send_heartbeat.return_value = True
        manager = HeartbeatManager(mock_comm)
        manager.set_interval(100_000_000)  # 100ms

        # Track time progression deterministically
        current_time = [1_000_000_000_000]  # Start at 1 second in ns

        def fake_time_ns():
            return current_time[0]

        monkeypatch.setattr("time.time_ns", fake_time_ns)

        manager.reset_heartbeat()

        send_count = 0
        for _ in range(100):
            current_time[0] += 10_000_000  # Advance 10ms
            if manager.should_send_heartbeat():
                manager.send_heartbeat()
                send_count += 1

        # After 1 second with 100ms interval, should send approximately 10 times
        assert 9 <= send_count <= 11

    def test_no_sends_when_time_not_advanced(self, monkeypatch):
        """Test no sends occur when time doesn't advance."""
        mock_comm = Mock()
        mock_comm.enabled = True
        mock_comm.send_heartbeat.return_value = True
        manager = HeartbeatManager(mock_comm)
        manager.set_interval(100_000_000)  # 100ms

        # Fixed time
        fixed_time = 1_000_000_000_000

        def fake_time_ns():
            return fixed_time

        monkeypatch.setattr("time.time_ns", fake_time_ns)

        # First send after reset
        manager.reset_heartbeat()
        assert manager.should_send_heartbeat() is True
        manager.send_heartbeat()

        # No more sends since time doesn't advance
        for _ in range(10):
            assert manager.should_send_heartbeat() is False
