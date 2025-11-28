from typing import Any, Dict

import pytest

from xbee.core.command_codes import CONSTANTS
from xbee.core.encoding import MessageEncoder


def encode_and_decode(data: Dict[str, Any], id_):
    comm = MessageEncoder()
    encoded = comm.encode_data(data, id_)
    decoded, _ = comm.decode_data(encoded)
    return encoded, decoded


def test_joystick_bytes_in_range_passes():
    # Single-byte representation 200 -> b'\xc8'
    data = {CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR: b"\xc8"}
    # Should not raise and should encode to a value that decodes back to 200
    _, decoded = encode_and_decode(data, CONSTANTS.COMPACT_MESSAGES.XBOX_ID)
    assert decoded[CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR] == pytest.approx(
        (200 - 100) / 100.0
    )


def test_joystick_bytes_out_of_range_raises():
    comm = MessageEncoder()
    # Two-byte representation (0x0100 = 256) is out-of-range for the 8-bit joystick.
    data = {CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR: b"\x01\x00"}

    with pytest.raises(ValueError):
        comm.encode_data(data, CONSTANTS.COMPACT_MESSAGES.XBOX_ID)


def test_normalize_signal_value_bytes_direct_call():
    # Verify that the internal normalization function also applies validation
    comm = MessageEncoder()
    sig = comm.get_messages()[CONSTANTS.COMPACT_MESSAGES.XBOX_ID]["values"][
        CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR
    ]
    # In-range: single byte
    val = comm._normalize_signal_value(sig, b"\xc8")
    assert val == 200

    # Out-of-range: two bytes representing 0x0100 = 256
    with pytest.raises(ValueError):
        comm._normalize_signal_value(sig, b"\x01\x00")
