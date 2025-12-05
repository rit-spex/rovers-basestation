import logging
from typing import Any, Union

from .command_codes import CONSTANTS, DataType

logger = logging.getLogger(__name__)


class Signal:
    """
    Class representing a signal with a name and type.
    """

    def __init__(self, type: DataType, default_value: Any = 0):
        # Note: this signal container supports native Python types as values
        self.__type = type
        self.__default_value = default_value
        self.__value = self.__default_value

    @property
    def type(self) -> DataType:
        """
        Get the type of the signal.
        """
        return self.__type

    @property
    def value(self) -> Any:
        """
        Get the current value of the signal.
        """
        return self.__value

    @property
    def default_value(self) -> Any:
        """
        Get the default value of the signal.
        """
        return self.__default_value

    def to_string(self) -> str:
        """
        Get the string representation of the signal.
        """
        return f"Signal(type={self.__type}, value={self.__value}, default_value={self.__default_value})"


class MessageEncoder:
    """
    Module for encoding and decoding data for XBee communication.
    """

    def __init__(self):
        self.__messages = {  # Note: dictionaries are in insertion order in Python 3.7+
            CONSTANTS.COMPACT_MESSAGES.HEARTBEAT_ID: {  # byte 0
                "name": CONSTANTS.HEARTBEAT.NAME,
                "values": {
                    # byte 1-2
                    CONSTANTS.HEARTBEAT.TIMESTAMP_MESSAGE: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_16
                    )
                },  # bits 0-15
            },
            CONSTANTS.COMPACT_MESSAGES.N64_ID: {  # byte 0
                "name": CONSTANTS.N64.NAME,
                "values": {
                    # byte 1
                    CONSTANTS.N64.BUTTON.A_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, False
                    ),  # bits 0-1
                    CONSTANTS.N64.BUTTON.B_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, False
                    ),  # bits 2-3
                    CONSTANTS.N64.BUTTON.L_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, False
                    ),  # bits 4-5
                    CONSTANTS.N64.BUTTON.R_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, False
                    ),  # bits 6-7
                    # byte 2
                    CONSTANTS.N64.BUTTON.C_UP_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, False
                    ),  # bits 0-1
                    CONSTANTS.N64.BUTTON.C_DOWN_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, False
                    ),  # bits 2-3
                    CONSTANTS.N64.BUTTON.C_LEFT_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, False
                    ),  # bits 4-5
                    CONSTANTS.N64.BUTTON.C_RIGHT_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, False
                    ),  # bits 6-7
                    # byte 3
                    CONSTANTS.N64.BUTTON.DP_UP_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, False
                    ),  # bits 0-1
                    CONSTANTS.N64.BUTTON.DP_DOWN_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, False
                    ),  # bits 2-3
                    CONSTANTS.N64.BUTTON.DP_LEFT_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, False
                    ),  # bits 4-5
                    CONSTANTS.N64.BUTTON.DP_RIGHT_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, False
                    ),  # bits 6-7
                    # byte 4
                    CONSTANTS.N64.BUTTON.Z_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, False
                    ),
                },  # bits 0-1
            },
            CONSTANTS.COMPACT_MESSAGES.XBOX_ID: {  # byte 0
                "name": CONSTANTS.XBOX.NAME,
                "values": {
                    # byte 1
                    CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_8_JOYSTICK,
                        CONSTANTS.XBOX.JOYSTICK.NEUTRAL_HEX,
                    ),  # bits 0-7
                    # byte 2
                    CONSTANTS.XBOX.JOYSTICK.AXIS_RY_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_8_JOYSTICK,
                        CONSTANTS.XBOX.JOYSTICK.NEUTRAL_HEX,
                    ),  # bits 0-7
                    # byte 3
                    CONSTANTS.XBOX.BUTTON.A_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, False
                    ),  # bit 0-1
                    CONSTANTS.XBOX.BUTTON.B_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, False
                    ),  # bit 2-3
                    CONSTANTS.XBOX.BUTTON.X_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, False
                    ),  # bit 4-5
                    CONSTANTS.XBOX.BUTTON.Y_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, False
                    ),  # bit 6-7
                    # byte 4
                    CONSTANTS.XBOX.BUTTON.LEFT_BUMPER_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, False
                    ),  # bit 0-1
                    CONSTANTS.XBOX.BUTTON.RIGHT_BUMPER_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, False
                    ),  # bit 2-3
                    CONSTANTS.XBOX.TRIGGER.AXIS_LT_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, False
                    ),  # bit 4-5
                    CONSTANTS.XBOX.TRIGGER.AXIS_RT_STR: Signal(
                        CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, False
                    ),
                },  # bit 6-7
            },
            CONSTANTS.COMPACT_MESSAGES.QUIT_ID: {  # byte 0
                "name": CONSTANTS.QUIT.NAME,
                "values": {
                    # byte 1
                    CONSTANTS.QUIT.NAME: Signal(
                        CONSTANTS.COMPACT_MESSAGES.BOOLEAN, CONSTANTS.QUIT.VALUE
                    )
                },  # bit 0
            },
        }

        # Build alias->numeric mappings for known controllers so that encode_data()
        # can accept either string aliases or numeric keys as input in `data`.
        def _extract_alias_map(obj):
            out = {}
            for a in dir(obj):
                if a.endswith("_STR") and hasattr(obj, a[:-4]):
                    alias = getattr(obj, a)
                    numeric = getattr(obj, a[:-4])
                    out[alias] = numeric
            return out

        # alias to numeric mapping keyed by controller name
        self._alias_to_numeric: dict[str, dict] = {}
        # XBOX
        xbox_map = {}
        xbox_map.update(_extract_alias_map(CONSTANTS.XBOX.JOYSTICK))
        xbox_map.update(_extract_alias_map(CONSTANTS.XBOX.TRIGGER))
        # Add BUTTON_INDEX_OFFSET to XBOX button numeric values to avoid clashes with joystick axes.
        # with joystick axes.
        xbox_button_map = _extract_alias_map(CONSTANTS.XBOX.BUTTON)
        xbox_button_map = {
            alias: (numeric + CONSTANTS.XBOX.BUTTON_INDEX_OFFSET)
            for alias, numeric in xbox_button_map.items()
        }
        xbox_map.update(xbox_button_map)
        self._alias_to_numeric[CONSTANTS.XBOX.NAME] = xbox_map
        # N64
        n64_map = {}
        n64_map.update(_extract_alias_map(CONSTANTS.N64.JOYSTICK))
        n64_map.update(_extract_alias_map(CONSTANTS.N64.BUTTON))
        self._alias_to_numeric[CONSTANTS.N64.NAME] = n64_map

    def get_messages(self) -> dict[int, dict[str, Any]]:
        """
        Get the message definitions.

        Returns:
            dict: The message definitions.
        """
        return self.__messages

    def __convert_native_to_int(self, type: DataType, value: Any) -> int:
        """
        Convert a native type to an integer representation.

        Args:
            type (int): The native type.

        Returns:
            int: The integer representation.
        """
        if type == CONSTANTS.COMPACT_MESSAGES.BOOLEAN:
            return value  # return as 0/1 for 1-bit storage

        elif type == CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL:
            return value + 1  # convert bool to 1/2 for 2 bit storage

        elif type == CONSTANTS.COMPACT_MESSAGES.UINT_8_JOYSTICK:
            # convert float joystick value (-1.0-1.0) to int (0-200)
            value = max(-1.0, min(1.0, value))
            value = value * 100 + 100
            return int(value)

        else:
            return int(value)

    def __convert_int_to_native(self, type: DataType, value: int) -> Any:
        """
        Convert an integer representation to a native type.

        Args:
            type (int): The native type.

        Returns:
            Any: The native representation.
        """
        if type == CONSTANTS.COMPACT_MESSAGES.BOOLEAN:
            return bool(value)  # convert 1/2 back to bool

        elif type == CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL:
            return bool(value - 1)  # convert 1/2 back to bool

        elif type == CONSTANTS.COMPACT_MESSAGES.UINT_8_JOYSTICK:
            # convert int (0-200) back to float joystick value (-1.0-1.0)
            logger.debug("Decoding joystick value: %s", value)
            return (float(value) - 100.0) / 100.0

        else:
            return value

    def encode_data(
        self, data: dict[str, Any], id_: Union[int, bytes, bytearray, memoryview]
    ) -> bytes:
        """
        Encode the given data dictionary into bytes for transmission.

        Args:
            data (dict): The data to encode.
            id_ (Union[int, bytes, bytearray, memoryview]): Either an integer ID (single byte) or a
                bytes-like object representing the ID (e.g., b'\x01'). The implementation
                accepts both and will convert bytes/bytearray to an integer ID automatically.

        Returns:
            bytes: The encoded data.
        """

        # Accept either an int ID or a bytes-like payload as the ID
        # Convert bytes/bytearray/memoryview into an integer ID for encoding.
        message_id = id_
        if isinstance(message_id, (bytes, bytearray, memoryview)):
            if len(message_id) == 0:
                raise ValueError("message_id bytes cannot be empty")
            message_id = int.from_bytes(bytes(message_id), byteorder="big")

        # Ensure message_id is an integer
        try:
            message_id_int = int(message_id)
        except (ValueError, TypeError) as e:
            # Only reraise for expected conversion errors to avoid masking unexpected issues
            raise TypeError(
                f"message_id must be an int or bytes-like object; got {type(message_id)!r}"
            ) from e

        # Validate range (single byte)
        if message_id_int < 0 or message_id_int > 0xFF:
            raise ValueError(
                f"message_id must be in the range 0..255 (fits in one byte); got {message_id_int}"
            )

        # Validate that we know this message ID
        if message_id_int not in self.__messages:
            raise KeyError(
                f"Unknown message_id: {message_id_int}. Known IDs: {list(self.__messages.keys())}"
            )

        # the first byte is always the ID, followed by encoded payload
        return message_id_int.to_bytes(
            1, byteorder="big"
        ) + self._encode_values_for_message(message_id_int, data)

    def _encode_values_for_message(
        self, message_id: int, data: dict[str, Any]
    ) -> bytes:
        """
        Helper to encode the values for a given message ID into bytes.
        """
        bytes_data = b""
        bits_remaining = 8
        current_byte = 0

        # bit flushing is pushed to _pack_signal_bits

        for key, signal in self.__messages[message_id]["values"].items():  # type: ignore[union-attr]
            signal_bits_size = signal.type.num_bits
            # Determine the raw value from provided data, numeric alias, or default
            raw_value = self._get_raw_value_for_key(message_id, key, data, signal)
            # Normalize to integer representation for bit packing
            signal_value = self._normalize_signal_value(signal, raw_value)

            # Pack the signal bits into bytes
            packed_bytes, current_byte, bits_remaining = self._pack_signal_bits(
                signal_value, signal_bits_size, current_byte, bits_remaining
            )
            bytes_data += packed_bytes

        if bits_remaining < 8:
            bytes_data += current_byte.to_bytes(1, byteorder="big")

        return bytes_data

    def _pack_signal_bits(
        self,
        signal_value: int,
        signal_bits_size: int,
        current_byte: int,
        bits_remaining: int,
    ) -> tuple[bytes, int, int]:
        """
        Pack a signal's bits into bytes and return
        (bytes, current_byte, bits_remaining).
        """
        bytes_out = b""

        while signal_bits_size > 0:
            if bits_remaining - signal_bits_size < 0:
                signal_bits_size -= bits_remaining
                current_byte |= (signal_value >> signal_bits_size) & (
                    (1 << bits_remaining) - 1
                )
                bytes_out += current_byte.to_bytes(1, byteorder="big")
                bits_remaining = 8
                current_byte = 0
            else:
                current_byte |= (signal_value & ((1 << signal_bits_size) - 1)) << (
                    bits_remaining - signal_bits_size
                )
                bits_remaining -= signal_bits_size
                signal_bits_size = 0

                if bits_remaining == 0:
                    bytes_out += current_byte.to_bytes(1, byteorder="big")
                    bits_remaining = 8
                    current_byte = 0

        return bytes_out, current_byte, bits_remaining

    def _normalize_signal_value(self, signal: Signal, value: Any) -> int:
        """Normalize a native or encoded value for a given signal to an integer
        ready for bit packing.

        Args:
            signal: Signal object describing type and defaults.
            value: Raw value from data, alias, or defaults (may be bytes, int,
                   bool, float).

        Returns:
            int: Integer representation suitable for packing via bit ops.
        """
        # Convert bytes-like inputs to integers and validate/normalize like ints.
        # as regular ints or native types.
        if isinstance(value, (bytes, bytearray, memoryview)):
            value = int.from_bytes(bytes(value), byteorder="big")

        dtype = signal.type

        # Dispatch to smaller helpers based on the DataType to reduce cognitive
        # complexity in this function and make intent clearer.
        if dtype == CONSTANTS.COMPACT_MESSAGES.UINT_8_JOYSTICK:
            return self._normalize_uint8_joystick_value(value)

        # UINT_2_BOOL: accept bool (native) or int (encoded); floats treated like bools
        if dtype == CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL:
            return self._normalize_uint2_bool_value(value)

        # BOOLEAN: 1-bit
        if dtype == CONSTANTS.COMPACT_MESSAGES.BOOLEAN:
            return self._normalize_boolean_value(value)

        # Default conversion for other types
        return int(value)

    def _get_raw_value_for_key(
        self, message_id: int, key: str, data: dict[str, Any], signal: Signal
    ):
        """Helper to extract raw value for a message key from the provided
        data dict, handling alias->numeric lookups.
        """
        # Start with the default
        raw_value = signal.default_value

        if key in data:
            if isinstance(data[key], (bytes, bytearray, memoryview)):
                raw_value = int.from_bytes(bytes(data[key]), byteorder="big")
            else:
                raw_value = data[key]
            return raw_value

        alias_map = self._alias_to_numeric.get(self.__messages[message_id]["name"], {})  # type: ignore[arg-type]
        num_key = alias_map.get(key)
        if num_key is not None and num_key in data:
            if isinstance(data[num_key], (bytes, bytearray, memoryview)):
                return int.from_bytes(bytes(data[num_key]), byteorder="big")
            else:
                return data[num_key]

        return raw_value

    def _normalize_uint8_joystick_value(self, value: Any) -> int:
        """
        Normalize values for UINT_8_JOYSTICK signal types.
        """
        if isinstance(value, float):
            return self.__convert_native_to_int(
                CONSTANTS.COMPACT_MESSAGES.UINT_8_JOYSTICK, value
            )
        elif isinstance(value, int):
            if value < 0 or value > 255:
                raise ValueError(
                    f"Joystick value out of range: {value} (expected 0..255)"
                )
            return int(value)
        else:
            raise TypeError(f"Unsupported joystick type for value: {type(value)!r}")

    def _normalize_uint2_bool_value(self, value: Any) -> int:
        """
        Normalize values for UINT_2_BOOL signal types.
        """
        if isinstance(value, bool):
            return self.__convert_native_to_int(
                CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, value
            )
        elif isinstance(value, int):
            # UINT_2_BOOL occupies 2 bits, valid integer range is 0..3
            if value < 0 or value > 3:
                raise ValueError(
                    f"UINT_2_BOOL value out of range: {value} (expected 0..3)"
                )
            return int(value)
        elif isinstance(value, float):
            return self.__convert_native_to_int(
                CONSTANTS.COMPACT_MESSAGES.UINT_2_BOOL, bool(value)
            )
        else:
            raise TypeError(f"Unsupported 2-bit boolean value type: {type(value)!r}")

    def _normalize_boolean_value(self, value: Any) -> int:
        """
        Normalize values for BOOLEAN signal types.
        """
        if isinstance(value, bool):
            return int(value)
        elif isinstance(value, int):
            # BOOLEAN occupies 1 bit and must be 0 or 1
            if value < 0 or value > 1:
                raise ValueError(f"BOOLEAN value out of range: {value} (expected 0..1)")
            return int(value)
        else:
            raise TypeError(f"Unsupported boolean value type: {type(value)!r}")

    def decode_data(self, data: bytes) -> tuple[dict[str, Any], int]:
        """
        Decode the received bytes into a data dictionary.

        Args:
            data (bytes): The data to decode.

        Returns:
            dict: The decoded data.
            int: The identifier for the data.
        """

        # the first byte is always the ID
        id_ = int.from_bytes(data[0:1], byteorder="big")

        # Validate that we know this message ID
        if id_ not in self.__messages:
            raise KeyError(
                f"Unknown message_id during decode: {id_}. Known IDs: {list(self.__messages.keys())}"
            )

        # start decoding from byte index 1
        byte_index = 1
        bits_remaining = 8

        # Implement decoding logic here
        decoded_data = {}

        # Implement encoding logic here
        for key, signal in self.__messages[id_]["values"].items():  # type: ignore[union-attr]
            # store how many bits we need to store for this key
            signal_bits_size = signal.type.num_bits

            # set the value to zero for parsing
            signal_value = 0

            # repeat in case of 16 bit values or larger
            while signal_bits_size > 0:
                if bits_remaining - signal_bits_size < 0:
                    # use the remaining bits in the current byte
                    signal_bits_size -= bits_remaining
                    signal_value <<= bits_remaining
                    signal_value |= int.from_bytes(
                        data[byte_index : byte_index + 1], byteorder="big"
                    ) & ((1 << bits_remaining) - 1)
                    byte_index += 1
                    bits_remaining = 8
                else:
                    # the signal fits in the current byte
                    signal_value <<= signal_bits_size
                    signal_value |= (
                        int.from_bytes(
                            data[byte_index : byte_index + 1], byteorder="big"
                        )
                        >> (bits_remaining - signal_bits_size)
                    ) & ((1 << signal_bits_size) - 1)
                    bits_remaining -= signal_bits_size
                    signal_bits_size = 0

                    # reset the byte if full
                    if bits_remaining == 0:
                        bits_remaining = 8
                        byte_index += 1

            # convert back to native type
            signal_value = self.__convert_int_to_native(signal.type, signal_value)
            decoded_data[key] = signal_value

        return decoded_data, id_


if __name__ == "__main__":
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    encoder = MessageEncoder()

    test_data = {  # byte 0
        CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR: 200,  # byte 1
        "ry": 100,  # byte 2
        "A": 2,
        "B": 1,
        "X": 2,
        "Y": 1,  # byte 3
        "LB": 2,
        "RB": 1,
        "LT": 2,
        "RT": 1,  # byte 4
    }

    encoded = encoder.encode_data(test_data, CONSTANTS.COMPACT_MESSAGES.XBOX_ID)
    logger.info(
        "Encoded Data: %s, ID: %s", encoded, hex(CONSTANTS.COMPACT_MESSAGES.XBOX_ID)
    )

    decoded, message_id = encoder.decode_data(encoded)
    logger.info("Decoded Data: %s, ID: %s", decoded, hex(message_id))
