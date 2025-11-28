from __future__ import annotations

from unittest.mock import Mock

from xbee.core.udp_communication import UdpCommunicationManager


def test_udp_send_exception_is_handled(monkeypatch):
    # Avoid binding sockets
    monkeypatch.setattr(UdpCommunicationManager, "_setup_sockets", lambda self: None)
    um = UdpCommunicationManager()
    um.running = False

    # Simulate exception in underlying send
    def fail_send(message):
        raise RuntimeError("send error")

    um._send_message = Mock(side_effect=fail_send)

    # Should return False but not raise
    assert um.send_controller_data({}, {}, False) is False
