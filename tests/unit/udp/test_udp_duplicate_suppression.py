from __future__ import annotations

import threading
import time
from unittest.mock import Mock

from xbee.core.udp_communication import UdpCommunicationManager


def test_udp_duplicate_suppression_concurrent(monkeypatch):
    # Don't create real sockets
    monkeypatch.setattr(UdpCommunicationManager, "_setup_sockets", lambda self: None)
    um = UdpCommunicationManager()
    um.running = False

    calls = []
    send_hold = threading.Event()
    send_started = threading.Event()
    num_threads = 5
    start_barrier = threading.Barrier(num_threads + 1)

    def slow_send(msg):
        calls.append(msg)
        # signal the main thread that the underlying send has started
        send_started.set()
        # block here until the test explicitly releases the send
        send_hold.wait(timeout=1)
        return True

    um._send_message = Mock(side_effect=slow_send)
    payload = [b"\xaa", 0x01, 0x02]

    results = []

    def send_wrap():
        # Wait until all worker threads (and the test thread) are ready
        start_barrier.wait()
        results.append(um.send_package(payload))

    threads = []
    for _ in range(num_threads):
        t = threading.Thread(target=send_wrap)
        threads.append(t)
        t.start()
    # release the worker threads so they all start send_package nearly simultaneously
    start_barrier.wait()
    # wait until the underlying send call is actually in progress
    assert send_started.wait(timeout=1)
    # release the slow send so it completes and unblocks waiting threads
    send_hold.set()
    for t in threads:
        t.join(timeout=1)
        assert not t.is_alive()
    assert len(calls) == 1
    # verify every thread observed the successful send
    assert len(results) == num_threads
    assert all(results), "All threads should receive True from send_package"
    # only a single underlying send should have been attempted
    assert um._send_message.call_count == 1


def test_udp_duplicate_suppression_concurrent_first_send_fails(monkeypatch):
    monkeypatch.setattr(UdpCommunicationManager, "_setup_sockets", lambda self: None)
    um = UdpCommunicationManager()
    um.running = False
    call_count = {"count": 0}

    def fail_send(msg):
        call_count["count"] += 1
        if call_count["count"] == 1:
            time.sleep(0.05)
            # first call fails
            return False
        return True

    um._send_message = Mock(side_effect=fail_send)
    payload = [b"\xaa", 0x01, 0x02]

    results = []

    def send_wrap():
        results.append(um.send_package(payload))

    t1 = threading.Thread(target=send_wrap)
    t2 = threading.Thread(target=send_wrap)
    t1.start()
    time.sleep(0.01)
    t2.start()
    t1.join(timeout=1)
    t2.join(timeout=1)
    assert not t1.is_alive()
    assert not t2.is_alive()
    # both threads should reflect the failed first send
    assert results == [False, False]
    # only one underlying send attempt should have been made
    assert um._send_message.call_count == 1


def test_udp_inflight_wait_timeout(monkeypatch):
    monkeypatch.setattr(UdpCommunicationManager, "_setup_sockets", lambda self: None)
    um = UdpCommunicationManager()
    um.running = False
    um.inflight_wait_timeout = 0.01

    def slow_send(msg):
        time.sleep(0.05)
        return True

    um._send_message = Mock(side_effect=slow_send)
    payload = [b"\xaa", 0x01, 0x02]

    t1 = threading.Thread(target=um.send_package, args=(payload,))
    t1.start()
    time.sleep(0.001)
    assert um.send_package(payload) is False
    assert um._send_message.call_count == 1
    t1.join(timeout=1)
