from __future__ import annotations

from unittest.mock import Mock

from xbee.communication.xbee_backend import XbeeCommunicationManager


def test_xbee_inflight_entry_removed_after_exception():
    mock_device = Mock()
    # Simulate send_data raising an exception
    mock_device.send_data = Mock(side_effect=RuntimeError("send failed"))
    manager = XbeeCommunicationManager(xbee_device=mock_device, remote_xbee="00")
    manager.enabled = True
    payload = [0xAA, 0x01]

    res = manager.send_package(payload)
    assert res is False
    # Ensure inflight dict cleaned up after exception
    assert not manager._inflight_messages


def test_xbee_inflight_entry_removed_after_success():
    mock_device = Mock()
    mock_device.send_data = Mock(return_value=None)
    manager = XbeeCommunicationManager(xbee_device=mock_device, remote_xbee="00")
    manager.enabled = True
    payload = [0xAA, 0x02]

    res = manager.send_package(payload)
    assert res is True
    assert not manager._inflight_messages
