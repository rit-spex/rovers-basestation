from typing import Any, cast
from unittest.mock import Mock

from xbee.communication.manager import CommunicationManager
from xbee.communication.xbee_backend import XbeeCommunicationManager


def test_send_package_passes_bytes_to_hardware():
    cm = CommunicationManager()
    invocations = []

    def fake_send_package(data, skip_duplicate_check=False):
        invocations.append(type(data))
        # Return True to signal success
        return True

    cm.hardware_com = cast(Any, Mock())
    cm.hardware_com.send_package = fake_send_package

    assert cm.send_package(b"\xaa\x01") is True
    assert invocations == [bytes]


def test_send_package_passes_int_list_to_hardware():
    cm = CommunicationManager()
    received = []

    def fake_send_package(data, skip_duplicate_check=False):
        received.append(data)
        return True

    cm.hardware_com = cast(Any, Mock())
    cm.hardware_com.send_package = fake_send_package

    # Using list of ints should be passed through to the transport layer
    payload = [0xAA, 0x01, 0x02]
    assert cm.send_package(payload) is True
    assert isinstance(received[0], list)
    assert received[0] == payload


def test_send_compact_message_fallback_converts_list_with_bytes():
    cm = CommunicationManager()

    # Create a fake transport that raises TypeError on list payloads but accepts bytes
    class FakeHW:
        def __init__(self):
            self.calls = []

        def send_package(self, data, skip_duplicate_check=False):
            self.calls.append(data)
            if isinstance(data, list):
                raise TypeError("list payload not supported")
            if isinstance(data, (bytes, bytearray, memoryview)):
                return True
            raise ValueError("Unsupported payload")

    hw = FakeHW()
    cm.hardware_com = cast(Any, hw)

    # Mixed list containing bytes and ints; send_compact_message should convert to bytes after TypeError
    result = cm.send_compact_message([b"\xaa", 0x01, 0x02])
    assert result is True
    # Ensure the underlying transport was called twice - once with list, once with converted bytes
    assert len(hw.calls) == 2
    assert isinstance(hw.calls[0], list)
    assert isinstance(hw.calls[1], (bytes, bytearray))


def test_xbee_convert_to_bytes_accepts_mixed_list():
    mock_device = Mock()
    mock_device.send_data = Mock()
    remote_address = "0013A200423A7DDD"
    xbee_manager = XbeeCommunicationManager(
        xbee_device=mock_device, remote_xbee=remote_address
    )
    xbee_manager.enabled = True

    # Test direct conversion by invoking send_package with a mixed list
    mixed = [b"\xaa", 1, 2]
    assert xbee_manager.send_package(mixed) is True
    # Verify the send_data call used the converted bytes payload
    assert mock_device.send_data.called
    sent = mock_device.send_data.call_args[0][1]
    assert isinstance(sent, (bytes, bytearray))
    assert sent == bytes([0xAA, 0x01, 0x02])


def test_send_package_passes_memoryview_to_hardware():
    cm = CommunicationManager()

    received = []

    def fake_send_package(data, skip_duplicate_check=False):
        received.append(type(data))
        return True

    cm.hardware_com = cast(Any, Mock())
    cm.hardware_com.send_package = fake_send_package

    mv = memoryview(b"\xaa\x01")
    assert cm.send_package(mv) is True
    # Ensure the same memoryview type was received by the transport
    assert received == [memoryview]
