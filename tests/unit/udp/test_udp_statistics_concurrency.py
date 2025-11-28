from __future__ import annotations

import threading
import time

from xbee.core.udp_communication import UdpCommunicationManager


def _udp_writer(um, errors):
    try:
        for _ in range(200):
            um._send_message(b"x")
    except Exception as e:
        errors.append(e)


def _udp_reader(um, errors):
    try:
        for _ in range(500):
            stats = um.get_statistics()
            assert isinstance(stats.get("messages_sent"), int)
            assert isinstance(stats.get("messages_received"), int)
            time.sleep(0.0005)
    except Exception as e:
        errors.append(e)


def test_udp_get_statistics_concurrent_reads_and_writes(monkeypatch):
    # Avoid binding sockets in tests
    monkeypatch.setattr(UdpCommunicationManager, "_setup_sockets", lambda self: None)
    um = UdpCommunicationManager()
    um.running = False
    # Defensive init if _setup_sockets is monkeypatched or attributes are mocked; ensures counters increment safely.
    um.messages_sent = getattr(um, "messages_sent", 0)
    um.messages_received = getattr(um, "messages_received", 0)
    if not hasattr(um, "_message_lock") or um._message_lock is None:
        um._message_lock = threading.RLock()

    # Replace _send_message with a fake that increments counters under the
    # manager's lock to simulate activity.
    def fake_send(message):
        with um._message_lock:
            um.messages_sent += 1
        time.sleep(0.0005)
        return True

    um._send_message = fake_send

    errors = []

    threads = [
        threading.Thread(target=_udp_writer, args=(um, errors)) for _ in range(3)
    ]
    threads.extend(
        threading.Thread(target=_udp_reader, args=(um, errors)) for _ in range(4)
    )

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
        assert not t.is_alive()

    assert not errors, f"Encountered exceptions: {errors}"
