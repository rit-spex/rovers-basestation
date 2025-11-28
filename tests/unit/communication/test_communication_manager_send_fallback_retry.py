from __future__ import annotations

from unittest.mock import Mock

from xbee.core.command_codes import CONSTANTS
from xbee.core.communication import CommunicationManager
from xbee.core.udp_communication import UdpCommunicationManager


def test_send_compact_message_fallback_to_bytes(monkeypatch):
    # Avoid binding UDP sockets in tests
    monkeypatch.setattr(UdpCommunicationManager, "_setup_sockets", lambda self: None)
    cm = CommunicationManager(xbee_device=None, remote_xbee=None, simulation_mode=True)

    # Simulate hardware that raises TypeError for list payloads but accepts bytes
    def hardware_send(payload, skip_duplicate_check=False):
        if isinstance(payload, list):
            raise TypeError("doesn't accept list payloads")
        return True

    cm.hardware_com = Mock()
    cm.hardware_com.send_package = Mock(side_effect=hardware_send)

    # Use compact list payload
    data = [CONSTANTS.COMPACT_MESSAGES.STATUS, 1, 2, 3]
    res = cm.send_compact_message(data)
    assert res is True
    # Last call must have been with bytes (i.e., fallback conversion succeeded)
    assert isinstance(
        cm.hardware_com.send_package.call_args[0][0], (bytes, bytearray, memoryview)
    )


def test_send_package_retries(monkeypatch):
    monkeypatch.setattr(UdpCommunicationManager, "_setup_sockets", lambda self: None)
    cm = CommunicationManager(xbee_device=None, remote_xbee=None, simulation_mode=True)

    call_count = {"count": 0}

    def send_with_retry(payload, skip_duplicate_check=False):
        call_count["count"] += 1
        # Fail on the first attempt and succeed afterwards
        if call_count["count"] == 1:
            return False
        return True

    cm.hardware_com = Mock()
    cm.hardware_com.send_package = Mock(side_effect=send_with_retry)

    data = b"\x01\x02"
    result = cm.send_package(data, retry_count=1)
    assert result is True
    assert cm.hardware_com.send_package.call_count == 2
