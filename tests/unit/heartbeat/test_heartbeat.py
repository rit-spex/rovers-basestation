"""
Core heartbeat manager tests.

Basic functionality tests are here. See test_heartbeat_edge_cases.py for
more comprehensive boundary testing and concurrency tests.
"""

import time
from unittest.mock import Mock

import pytest

from xbee.communication.heartbeat import HeartbeatManager


@pytest.fixture
def heartbeat_manager():
    """Create a HeartbeatManager and a configured mocked communication manager.

    Returns:
        (HeartbeatManager, Mock): manager instance and its mocked comm manager
    """
    mock_comm = Mock()
    mock_comm.enabled = True
    mock_comm.send_heartbeat = Mock(return_value=True)
    manager = HeartbeatManager(mock_comm)
    return manager, mock_comm


def test_heartbeat_manager_creation_and_send(heartbeat_manager):
    """Test HeartbeatManager can be created and sends heartbeat successfully."""
    manager, mock_comm = heartbeat_manager
    manager.reset_heartbeat()

    result = manager.send_heartbeat()
    mock_comm.send_heartbeat.assert_called()
    assert result is True
    assert manager._last_heartbeat_time > 0


def test_heartbeat_manager_timing_simulation(heartbeat_manager, monkeypatch):
    """Test heartbeat timing with simulated clock to avoid flaky wall-clock tests."""
    manager, mock_comm = heartbeat_manager
    manager.set_interval(100_000_000)  # 100ms in ns
    manager.reset_heartbeat()

    # Patch time.time_ns for deterministic simulation
    now_ns = [int(time.time_ns())]

    def fake_time_ns():
        return now_ns[0]

    monkeypatch.setattr("time.time_ns", fake_time_ns, raising=True)

    sent_count = 0
    # Simulate 1 second of time in 10ms steps
    for _ in range(100):
        now_ns[0] += 10_000_000  # 10ms
        if manager.should_send_heartbeat():
            ok = manager.send_heartbeat()
            if ok:
                sent_count += 1

    # With 100ms interval over 1 second, should send ~10 heartbeats
    assert 8 <= sent_count <= 12, f"Expected 8-12 sends, got {sent_count}"
    assert mock_comm.send_heartbeat.call_count == sent_count
