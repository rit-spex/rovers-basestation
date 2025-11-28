"""
Edge case tests for encoding.py covering boundary values and unusual inputs.

These tests ensure the encoder handles edge cases correctly, not just happy paths.
"""

from xbee.core.command_codes import CONSTANTS
from xbee.core.encoding import MessageEncoder, Signal


class TestEncodingBoundaryValues:
    """Test encoding with boundary and extreme values."""

    def test_joystick_axis_at_minimum_value(self):
        """Test encoding joystick at minimum value (-1.0)."""
        comm = MessageEncoder()

        data = {CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR: -1.0}
        encoded = comm.encode_data(data, CONSTANTS.COMPACT_MESSAGES.XBOX_ID)
        decoded, _ = comm.decode_data(encoded)

        # -1.0 should decode to approximately -1.0
        assert abs(decoded[CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR] - (-1.0)) < 0.02

    def test_joystick_axis_at_maximum_value(self):
        """Test encoding joystick at maximum value (1.0)."""
        comm = MessageEncoder()

        data = {CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR: 1.0}
        encoded = comm.encode_data(data, CONSTANTS.COMPACT_MESSAGES.XBOX_ID)
        decoded, _ = comm.decode_data(encoded)

        # 1.0 should decode to approximately 1.0
        assert abs(decoded[CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR] - 1.0) < 0.02

    def test_joystick_axis_at_neutral_value(self):
        """Test encoding joystick at neutral value (0.0)."""
        comm = MessageEncoder()

        data = {CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR: 0.0}
        encoded = comm.encode_data(data, CONSTANTS.COMPACT_MESSAGES.XBOX_ID)
        decoded, _ = comm.decode_data(encoded)

        assert abs(decoded[CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR]) < 0.02

    def test_joystick_axis_clamped_above_max(self):
        """Test that values > 1.0 are clamped to 1.0."""
        comm = MessageEncoder()

        # Values above 1.0 should be clamped
        data = {CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR: 5.0}
        encoded = comm.encode_data(data, CONSTANTS.COMPACT_MESSAGES.XBOX_ID)
        decoded, _ = comm.decode_data(encoded)

        # Should be clamped to 1.0
        assert abs(decoded[CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR] - 1.0) < 0.02

    def test_joystick_axis_clamped_below_min(self):
        """Test that values < -1.0 are clamped to -1.0."""
        comm = MessageEncoder()

        # Values below -1.0 should be clamped
        data = {CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR: -5.0}
        encoded = comm.encode_data(data, CONSTANTS.COMPACT_MESSAGES.XBOX_ID)
        decoded, _ = comm.decode_data(encoded)

        # Should be clamped to -1.0
        assert abs(decoded[CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR] - (-1.0)) < 0.02

    def test_heartbeat_timestamp_at_max_uint16(self):
        """Test heartbeat with max uint16 timestamp value."""
        comm = MessageEncoder()

        data = {CONSTANTS.HEARTBEAT.TIMESTAMP_MESSAGE: 65535}  # Max uint16
        encoded = comm.encode_data(data, CONSTANTS.COMPACT_MESSAGES.HEARTBEAT_ID)
        decoded, _ = comm.decode_data(encoded)

        assert decoded[CONSTANTS.HEARTBEAT.TIMESTAMP_MESSAGE] == 65535

    def test_heartbeat_timestamp_at_zero(self):
        """Test heartbeat with zero timestamp."""
        comm = MessageEncoder()

        data = {CONSTANTS.HEARTBEAT.TIMESTAMP_MESSAGE: 0}
        encoded = comm.encode_data(data, CONSTANTS.COMPACT_MESSAGES.HEARTBEAT_ID)
        decoded, _ = comm.decode_data(encoded)

        assert decoded[CONSTANTS.HEARTBEAT.TIMESTAMP_MESSAGE] == 0

    def test_all_n64_buttons_pressed(self):
        """Test encoding when all N64 buttons are pressed simultaneously."""
        comm = MessageEncoder()

        data = {
            CONSTANTS.N64.BUTTON.A_STR: True,
            CONSTANTS.N64.BUTTON.B_STR: True,
            CONSTANTS.N64.BUTTON.C_UP_STR: True,
            CONSTANTS.N64.BUTTON.C_DOWN_STR: True,
            CONSTANTS.N64.BUTTON.C_LEFT_STR: True,
            CONSTANTS.N64.BUTTON.C_RIGHT_STR: True,
            CONSTANTS.N64.BUTTON.L_STR: True,
            CONSTANTS.N64.BUTTON.R_STR: True,
            CONSTANTS.N64.BUTTON.Z_STR: True,
        }
        encoded = comm.encode_data(data, CONSTANTS.COMPACT_MESSAGES.N64_ID)
        decoded, _ = comm.decode_data(encoded)

        for key in data:
            assert decoded[key] is True, f"Button {key} should be True"

    def test_all_xbox_buttons_pressed(self):
        """Test encoding when all Xbox buttons are pressed simultaneously."""
        comm = MessageEncoder()

        data = {
            CONSTANTS.XBOX.BUTTON.A_STR: True,
            CONSTANTS.XBOX.BUTTON.B_STR: True,
            CONSTANTS.XBOX.BUTTON.X_STR: True,
            CONSTANTS.XBOX.BUTTON.Y_STR: True,
            CONSTANTS.XBOX.BUTTON.LEFT_BUMPER_STR: True,
            CONSTANTS.XBOX.BUTTON.RIGHT_BUMPER_STR: True,
        }
        encoded = comm.encode_data(data, CONSTANTS.COMPACT_MESSAGES.XBOX_ID)
        decoded, _ = comm.decode_data(encoded)

        for key in data:
            assert decoded[key] is True, f"Button {key} should be True"


class TestEncodingMalformedInputs:
    """Test encoding behavior with malformed or unexpected inputs."""

    def test_decode_truncated_message_raises_or_handles(self):
        """Test decoding a truncated message."""
        comm = MessageEncoder()

        # Only send the ID byte without payload
        truncated = bytes([CONSTANTS.COMPACT_MESSAGES.XBOX_ID])

        # This should either raise or handle gracefully
        try:
            decoded, _ = comm.decode_data(truncated)
            # If it doesn't raise, values should be defaults
            assert isinstance(decoded, dict)
        except (IndexError, ValueError, KeyError):
            # Expected behavior for malformed data
            pass

    def test_decode_extra_bytes_ignored(self):
        """Test that extra bytes at the end are ignored."""
        comm = MessageEncoder()

        # Encode valid data
        data = {CONSTANTS.HEARTBEAT.TIMESTAMP_MESSAGE: 1234}
        valid_encoded = comm.encode_data(data, CONSTANTS.COMPACT_MESSAGES.HEARTBEAT_ID)

        # Add extra garbage bytes
        padded = valid_encoded + b"\xff\xff\xff"

        # Should decode the valid portion
        decoded, msg_id = comm.decode_data(padded)
        assert msg_id == CONSTANTS.COMPACT_MESSAGES.HEARTBEAT_ID
        assert decoded[CONSTANTS.HEARTBEAT.TIMESTAMP_MESSAGE] == 1234

    def test_encode_with_none_value_uses_default(self):
        """Test that None values are handled (use defaults)."""
        comm = MessageEncoder()

        # When a key is missing, default should be used
        data = {}  # No values provided
        encoded = comm.encode_data(data, CONSTANTS.COMPACT_MESSAGES.XBOX_ID)
        decoded, _ = comm.decode_data(encoded)

        # Should get default neutral value for joystick
        assert abs(decoded[CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR]) < 0.02

    def test_encode_with_mixed_key_types(self):
        """Test encoding with both string and numeric keys."""
        comm = MessageEncoder()

        data = {
            CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR: 0.5,  # String key
            CONSTANTS.XBOX.JOYSTICK.AXIS_RY: -0.3,  # Numeric key (should work via alias)
        }

        encoded = comm.encode_data(data, CONSTANTS.COMPACT_MESSAGES.XBOX_ID)
        decoded, _ = comm.decode_data(encoded)

        assert abs(decoded[CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR] - 0.5) < 0.02
        # Verify the numeric key also worked (should have a corresponding string key)
        assert CONSTANTS.XBOX.JOYSTICK.AXIS_RY_STR in decoded
        assert abs(decoded[CONSTANTS.XBOX.JOYSTICK.AXIS_RY_STR] - (-0.3)) < 0.02


class TestSignalEdgeCases:
    """Test Signal class edge cases."""

    def test_signal_with_zero_bits_type(self):
        """Test Signal with minimal DataType."""
        from xbee.core.command_codes import DataType

        zero_bit_type = DataType(num_bits=0, id=0xFF)
        signal = Signal(zero_bit_type, 0)

        assert signal.type.num_bits == 0
        assert signal.default_value == 0

    def test_signal_with_large_bits_type(self):
        """Test Signal with large DataType (32 bits)."""
        from xbee.core.command_codes import DataType

        large_type = DataType(num_bits=32, id=0xFE)
        signal = Signal(large_type, 0xDEADBEEF)

        assert signal.type.num_bits == 32
        assert signal.default_value == 0xDEADBEEF

    def test_signal_default_value_preserved(self):
        """Test that Signal preserves default value correctly."""
        signal = Signal(CONSTANTS.COMPACT_MESSAGES.UINT_8_JOYSTICK, 127)

        # Value should start at default
        assert signal.value == 127
        assert signal.default_value == 127


class TestMultipleEncodesWithoutDecodes:
    """Test multiple encodes without decoding to check for state corruption."""

    def test_encoder_state_isolation(self):
        """Test that multiple encodes don't corrupt encoder state."""
        comm = MessageEncoder()

        # Encode many different messages
        for i in range(100):
            data = {
                CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR: (i % 200 - 100) / 100.0,
            }
            encoded = comm.encode_data(data, CONSTANTS.COMPACT_MESSAGES.XBOX_ID)
            assert len(encoded) > 0

        # Final encode should still work correctly
        final_data = {CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR: 0.5}
        final_encoded = comm.encode_data(final_data, CONSTANTS.COMPACT_MESSAGES.XBOX_ID)
        decoded, _ = comm.decode_data(final_encoded)

        assert abs(decoded[CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR] - 0.5) < 0.02

    def test_rapid_encode_decode_cycles(self):
        """Test rapid encode/decode cycles don't accumulate errors."""
        comm = MessageEncoder()

        original_value = 0.75

        for _ in range(50):
            data = {CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR: original_value}
            encoded = comm.encode_data(data, CONSTANTS.COMPACT_MESSAGES.XBOX_ID)
            decoded, _ = comm.decode_data(encoded)
            # Use decoded value as next input (testing roundtrip stability)
            original_value = decoded[CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR]

        # After many cycles, should still be close to original
        assert abs(original_value - 0.75) < 0.05
