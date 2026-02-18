import importlib

import pytest


def test_encode_data_rejects_out_of_range_id():
    """
    Passing an id of 256 (outside a one-byte range) should fail fast with ValueError.
    """
    mod = importlib.import_module("xbee.protocol.encoding")
    comm = mod.MessageEncoder()

    with pytest.raises(ValueError):
        comm.encode_data({}, 256)

    with pytest.raises(ValueError):
        comm.encode_data({}, b"\x01\x02")


def test_encode_data_rejects_unknown_id():
    """
    An id that is within range but not registered in the encoder should raise KeyError.
    """
    mod = importlib.import_module("xbee.protocol.encoding")
    comm = mod.MessageEncoder()

    unknown_id = 0xB1
    assert unknown_id not in comm.get_messages()
    with pytest.raises(KeyError):
        comm.encode_data({}, unknown_id)


def test_encode_data_accepts_alias_and_numeric_keys_for_xbox_buttons():
    """
    Ensure that the encoder accepts both alias string keys and numeric keys with button index offsets for XBOX buttons and produces the same output.
    """
    from xbee.config.constants import CONSTANTS

    mod = importlib.import_module("xbee.protocol.encoding")
    comm = mod.MessageEncoder()

    numeric_key = CONSTANTS.XBOX.BUTTON.B + CONSTANTS.XBOX.BUTTON_INDEX_OFFSET
    alias_key = CONSTANTS.XBOX.BUTTON.B_STR
    value = CONSTANTS.XBOX.BUTTON.ON

    encoded_numeric = comm.encode_data(
        {numeric_key: value}, CONSTANTS.COMPACT_MESSAGES.XBOX_ID
    )
    encoded_alias = comm.encode_data(
        {alias_key: value}, CONSTANTS.COMPACT_MESSAGES.XBOX_ID
    )

    decoded_numeric, mid = comm.decode_data(encoded_numeric)
    decoded_alias, _ = comm.decode_data(encoded_alias)

    assert mid == CONSTANTS.COMPACT_MESSAGES.XBOX_ID
    assert decoded_numeric[alias_key] is True
    assert decoded_alias[alias_key] is True
    # Ensure the encoder produced identical byte sequences for alias vs numeric keys
    # Normalize to bytes in case the implementation returns bytearray/memoryview
    assert bytes(encoded_numeric) == bytes(encoded_alias)
