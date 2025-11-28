from __future__ import annotations

import threading
import time
from unittest.mock import Mock

from xbee.core.communication import CommunicationManager


def test_communication_manager_duplicate_suppression_concurrent(monkeypatch):
    # Use the real UdpCommunicationManager (in simulation_mode) with its
    # inflight duplicate suppression but monkeypatch sockets to avoid binding.
    from xbee.core.udp_communication import UdpCommunicationManager

    monkeypatch.setattr(UdpCommunicationManager, "_setup_sockets", lambda self: None)
    cm = CommunicationManager(xbee_device=None, remote_xbee=None, simulation_mode=True)
    cm.enabled = True

    send_calls = []

    def fake_send(msg):
        send_calls.append(msg)
        time.sleep(0.01)
        return True

    # Replace UDP sender with a slow mock to observe duplicate suppression; use monkeypatch.setattr(raising=False) to avoid static-type issues.
    monkeypatch.setattr(
        cm.hardware_com, "_send_message", Mock(side_effect=fake_send), raising=False
    )

    xbox_values = {"ly": 0.5}

    barrier = threading.Barrier(5)

    def worker():
        barrier.wait()  # Ensure all threads start sending at the same time
        cm.send_controller_data(xbox_values, {}, reverse_mode=False)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=1)
        assert not t.is_alive()

    # Underlying sender should have been invoked only once due to UDP inflight suppression
    assert len(send_calls) == 1
