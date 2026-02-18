"""
Tests for encoding.py advanced functionality.
"""

import pytest

from xbee.config.constants import CONSTANTS
from xbee.protocol.encoding import MessageEncoder, Signal


class TestSignal:
    """Test Signal class."""

    def test_signal_creation(self):
        """Test Signal object creation."""
        signal = Signal(CONSTANTS.COMPACT_MESSAGES.UINT_8_JOYSTICK, 100)

        assert signal.type == CONSTANTS.COMPACT_MESSAGES.UINT_8_JOYSTICK
        assert signal.default_value == 100
        assert signal.value == 100

    def test_signal_to_string(self):
        """Test Signal string representation."""
        signal = Signal(CONSTANTS.COMPACT_MESSAGES.BOOLEAN, True)

        string_repr = signal.to_string()

        assert "Signal" in string_repr
        assert "BOOLEAN" in string_repr or "type=" in string_repr


class TestMessageEncoderEncoding:
    """Test MessageEncoder encoding functionality."""

    def test_encode_data_bytes_id(self):
        """Test encode_data accepts bytes as ID."""
        comm = MessageEncoder()

        # XBOX_ID is 0xF0
        result = comm.encode_data({}, b"\xF0")

        assert isinstance(result, bytes)
        assert result[0] == 0xF0

    def test_encode_data_bytearray_id(self):
        """Test encode_data accepts bytearray as ID."""
        comm = MessageEncoder()

        result = comm.encode_data({}, bytearray([0xF0]))

        assert isinstance(result, bytes)
        assert result[0] == 0xF0

    def test_encode_data_empty_bytes_id_raises(self):
        """Test encode_data raises for empty bytes ID."""
        comm = MessageEncoder()

        with pytest.raises(ValueError, match="cannot be empty"):
            comm.encode_data({}, b"")

    def test_encode_data_invalid_id_type_raises(self):
        """Test encode_data raises for invalid ID type."""
        comm = MessageEncoder()

        with pytest.raises(TypeError, match="must be an int or bytes-like"):
            comm.encode_data({}, "invalid")  # type: ignore[arg-type]

    def test_encode_data_id_out_of_range_raises(self):
        """Test encode_data raises for ID out of range."""
        comm = MessageEncoder()

        with pytest.raises(ValueError, match="must be in the range"):
            comm.encode_data({}, 256)

    def test_encode_data_unknown_id_raises(self):
        """Test encode_data raises for unknown message ID."""
        comm = MessageEncoder()

        with pytest.raises(KeyError, match="Unknown message_id"):
            comm.encode_data({}, 0x99)

    def test_decode_data_unknown_id_raises(self):
        """Test decode_data raises for unknown message ID."""
        comm = MessageEncoder()

        with pytest.raises(KeyError, match="Unknown message_id during decode"):
            comm.decode_data(b"\x99\x00\x00")

    def test_encode_decode_roundtrip_xbox(self):
        """Test encoding and decoding Xbox data roundtrips correctly."""
        comm = MessageEncoder()

        data = {
            CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR: 0.5,
            CONSTANTS.XBOX.JOYSTICK.AXIS_RY_STR: -0.5,
        }

        encoded = comm.encode_data(data, CONSTANTS.COMPACT_MESSAGES.XBOX_ID)
        decoded, msg_id = comm.decode_data(encoded)

        assert msg_id == CONSTANTS.COMPACT_MESSAGES.XBOX_ID
        # Verify axis values are approximately correct after roundtrip
        assert abs(decoded[CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR] - 0.5) < 0.02
        assert abs(decoded[CONSTANTS.XBOX.JOYSTICK.AXIS_RY_STR] - (-0.5)) < 0.02

    def test_encode_decode_roundtrip_n64(self):
        """Test encoding and decoding N64 data roundtrips correctly."""
        comm = MessageEncoder()

        data = {
            CONSTANTS.N64.BUTTON.A_STR: True,
            CONSTANTS.N64.BUTTON.B_STR: False,
        }

        encoded = comm.encode_data(data, CONSTANTS.COMPACT_MESSAGES.N64_ID)
        decoded, msg_id = comm.decode_data(encoded)

        assert msg_id == CONSTANTS.COMPACT_MESSAGES.N64_ID
        assert decoded[CONSTANTS.N64.BUTTON.A_STR] is True
        assert decoded[CONSTANTS.N64.BUTTON.B_STR] is False

    def test_encode_decode_roundtrip_heartbeat(self):
        """Test encoding and decoding heartbeat data roundtrips correctly."""
        comm = MessageEncoder()

        data = {CONSTANTS.HEARTBEAT.TIMESTAMP_MESSAGE: 12345}

        encoded = comm.encode_data(data, CONSTANTS.COMPACT_MESSAGES.HEARTBEAT_ID)
        decoded, msg_id = comm.decode_data(encoded)

        assert msg_id == CONSTANTS.COMPACT_MESSAGES.HEARTBEAT_ID
        assert decoded[CONSTANTS.HEARTBEAT.TIMESTAMP_MESSAGE] == 12345


class TestConvertSignalValue:
    """Test signal value conversion methods."""

    def test_convert_uint8_joystick_float(self):
        """Test converting float joystick value."""
        comm = MessageEncoder()

        # 0.0 -> 100, 1.0 -> 200, -1.0 -> 0
        assert comm._convert_uint8_joystick(0.0) == 100
        assert comm._convert_uint8_joystick(1.0) == 200
        assert comm._convert_uint8_joystick(-1.0) == 0

    def test_convert_uint8_joystick_int(self):
        """Test converting int joystick value (already encoded)."""
        comm = MessageEncoder()

        assert comm._convert_uint8_joystick(150) == 150

    def test_convert_uint8_joystick_out_of_range(self):
        """Test converting out of range joystick value raises error."""
        comm = MessageEncoder()

        with pytest.raises(ValueError, match="out of range"):
            comm._convert_uint8_joystick(256)

    def test_convert_uint8_joystick_invalid_type(self):
        """Test converting invalid joystick type raises error."""
        comm = MessageEncoder()

        with pytest.raises(TypeError, match="Unsupported joystick type"):
            comm._convert_uint8_joystick("invalid")

    def test_convert_uint2_bool_bool(self):
        """Test converting bool value for UINT_2_BOOL."""
        comm = MessageEncoder()

        # True -> 2, False -> 1
        assert comm._convert_uint2_bool(True) == 2
        assert comm._convert_uint2_bool(False) == 1

    def test_convert_uint2_bool_int(self):
        """Test converting int value for UINT_2_BOOL."""
        comm = MessageEncoder()

        assert comm._convert_uint2_bool(1) == 1
        assert comm._convert_uint2_bool(2) == 2

    def test_convert_uint2_bool_float(self):
        """Test converting float value for UINT_2_BOOL."""
        comm = MessageEncoder()

        # Truthy float -> True -> 2
        assert comm._convert_uint2_bool(1.5) == 2
        # Zero float -> False -> 1
        assert comm._convert_uint2_bool(0.0) == 1

    def test_convert_uint2_bool_out_of_range(self):
        """Test converting out of range UINT_2_BOOL value raises error."""
        comm = MessageEncoder()

        with pytest.raises(ValueError, match=r"must be 1 \(OFF\) or 2 \(ON\)"):
            comm._convert_uint2_bool(5)

    def test_convert_uint2_bool_non_canonical_ints_raise(self):
        """Test non-canonical UINT_2_BOOL integer values are rejected."""
        comm = MessageEncoder()

        with pytest.raises(ValueError, match=r"must be 1 \(OFF\) or 2 \(ON\)"):
            comm._convert_uint2_bool(0)

        with pytest.raises(ValueError, match=r"must be 1 \(OFF\) or 2 \(ON\)"):
            comm._convert_uint2_bool(3)

    def test_convert_uint2_bool_invalid_type(self):
        """Test converting invalid UINT_2_BOOL type raises error."""
        comm = MessageEncoder()

        with pytest.raises(TypeError, match="Unsupported 2-bit boolean"):
            comm._convert_uint2_bool("invalid")

    def test_convert_boolean_bool(self):
        """Test converting bool value for BOOLEAN."""
        comm = MessageEncoder()

        assert comm._convert_boolean(True) == 1
        assert comm._convert_boolean(False) == 0

    def test_convert_boolean_int(self):
        """Test converting int value for BOOLEAN."""
        comm = MessageEncoder()

        assert comm._convert_boolean(0) == 0
        assert comm._convert_boolean(1) == 1

    def test_convert_boolean_out_of_range(self):
        """Test converting out of range BOOLEAN value raises error."""
        comm = MessageEncoder()

        with pytest.raises(ValueError, match="out of range"):
            comm._convert_boolean(2)

    def test_convert_boolean_invalid_type(self):
        """Test converting invalid BOOLEAN type raises error."""
        comm = MessageEncoder()

        with pytest.raises(TypeError, match="Unsupported boolean"):
            comm._convert_boolean("invalid")


class TestEncodingWithBytesValues:
    """Test encoding with bytes values in data dictionary."""

    def test_encode_with_bytes_axis_value(self):
        """Test encoding with bytes value for axis."""
        comm = MessageEncoder()

        data = {
            CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR: b"\x64",  # 100
        }

        encoded = comm.encode_data(data, CONSTANTS.COMPACT_MESSAGES.XBOX_ID)

        assert isinstance(encoded, bytes)
        assert len(encoded) > 0

    def test_encode_with_numeric_key_alias(self):
        """Test encoding with numeric key that has string alias."""
        comm = MessageEncoder()

        # Use numeric key (gets translated to string alias internally)
        data = {
            CONSTANTS.XBOX.JOYSTICK.AXIS_LY: 0.5,
        }

        encoded = comm.encode_data(data, CONSTANTS.COMPACT_MESSAGES.XBOX_ID)  # type: ignore[arg-type]

        assert isinstance(encoded, bytes)
        assert len(encoded) > 0
