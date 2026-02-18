from __future__ import annotations

import threading
import time
from unittest.mock import Mock

from xbee.communication.xbee_backend import XbeeCommunicationManager


def test_xbee_duplicate_suppression_sequential(monkeypatch):
    # Create a mock device for send_data
    mock_device = Mock()
    mock_device.send_data = Mock()
    remote_addr = "0013A200423A7DDD"

    manager = XbeeCommunicationManager(xbee_device=mock_device, remote_xbee=remote_addr)
    manager.enabled = True

    payload = b"\xaa\x01\x02"

    # First call should invoke send_data
    assert manager.send_package(payload) is True
    assert mock_device.send_data.call_count == 1

    # Second call should be detected as duplicate and not call send_data
    assert manager.send_package(payload) is True
    assert mock_device.send_data.call_count == 1


def test_xbee_duplicate_suppression_concurrent(monkeypatch):
    # Mock send_data to simulate a slow send and track invocations
    calls = []

    def slow_send(remote, data):
        calls.append(data)
        # Simulate a slow I/O operation
        time.sleep(0.01)

    mock_device = Mock()
    mock_device.send_data = Mock(side_effect=slow_send)
    remote_addr = "0013A200423A7DDD"

    manager = XbeeCommunicationManager(xbee_device=mock_device, remote_xbee=remote_addr)
    manager.enabled = True

    payload = b"\xaa\x01\x02"

    # Spawn multiple threads that attempt to send the same payload
    threads = []
    for _ in range(5):
        t = threading.Thread(target=manager.send_package, args=(payload,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=1)
        assert not t.is_alive(), "Thread did not complete within timeout"
    # Only a single underlying send_data invocation should have occurred
    assert len(calls) == 1


def test_xbee_duplicate_suppression_concurrent_first_send_fails(monkeypatch):
    # Mock send_data to raise on the first call and track invocations
    call_count = {"count": 0}
    send_started = threading.Event()

    def fail_send(remote, data):
        call_count["count"] += 1
        send_started.set()
        if call_count["count"] == 1:
            # Sleep to ensure the second thread has a chance to detect the in-flight marker
            time.sleep(0.05)
            raise RuntimeError("simulated send failure")
        return None

    mock_device = Mock()
    mock_device.send_data = Mock(side_effect=fail_send)
    remote_addr = "0013A200423A7DDD"

    manager = XbeeCommunicationManager(xbee_device=mock_device, remote_xbee=remote_addr)
    manager.enabled = True

    payload = b"\xaa\x01\x02"

    results = []

    def send_wrap():
        try:
            results.append(manager.send_package(payload))
        except Exception:
            results.append(False)

    # Spawn two threads where first underlying send raises, second should wait for
    # the result and return the same False outcome.
    t1 = threading.Thread(target=send_wrap)
    t2 = threading.Thread(target=send_wrap)
    t1.start()
    # Wait for the underlying send to actually start so the in-flight marker is set
    assert send_started.wait(timeout=1)
    t2.start()
    t1.join(timeout=1)
    t2.join(timeout=1)
    assert not t1.is_alive()
    assert not t2.is_alive()
    # Ensure both callers received consistent outcome (False)
    assert results == [False, False]
    # Underlying send_data should have been called exactly once (no double send)
    assert mock_device.send_data.call_count == 1


def test_xbee_inflight_wait_timeout(monkeypatch):
    def slow_send(remote, data):
        time.sleep(0.05)
        return None

    mock_device = Mock()
    mock_device.send_data = Mock(side_effect=slow_send)
    remote_addr = "0013A200423A7DDD"

    manager = XbeeCommunicationManager(xbee_device=mock_device, remote_xbee=remote_addr)
    manager.enabled = True
    manager.inflight_wait_timeout = 0.01

    payload = b"\xaa\x01\x02"
    t1 = threading.Thread(target=manager.send_package, args=(payload,))
    t1.start()
    time.sleep(0.001)
    assert manager.send_package(payload) is False
    # Verify the number of actual sends based on expected timeout behavior (should be 1 when suppressed)
    assert mock_device.send_data.call_count == 1
    t1.join(timeout=1)
