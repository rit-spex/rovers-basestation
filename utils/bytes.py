"""
Shared byte conversion utilities for the rover basestation.
"""

from typing import Sequence, Union

ByteItem = Union[int, bytes, bytearray, memoryview]
ByteSequence = Sequence[ByteItem]


def _validate_byte_int(value: int, idx: int) -> None:
    """Validate that an integer can be represented as a single byte."""
    if value < 0 or value > 255:
        raise ValueError(
            f"Integer value at index {idx} out of range for a byte: {value} (expected 0..255)"
        )


def convert_to_bytes(
    data: Union[bytes, bytearray, memoryview, ByteSequence],
) -> bytes:
    """
    Convert various byte-like data types to bytes.

    Accepts:
    - bytes, bytearray, or memoryview directly
    - Sequence of ints (0-255), bytes, bytearray, or memoryview items

    Args:
        data: The data to convert to bytes.

    Returns:
        bytes: The converted byte string.

    Raises:
        ValueError: If an integer is outside the valid byte range (0-255)
                    or if an unsupported type is in the sequence.
    """
    if isinstance(data, (bytes, bytearray, memoryview)):
        return bytes(data)

    message = bytearray()
    for idx, item in enumerate(data):
        if isinstance(item, (bytes, bytearray, memoryview)):
            message.extend(bytes(item))
        elif isinstance(item, int):
            _validate_byte_int(item, idx)
            message.append(item)
        else:
            raise ValueError(f"Unsupported data type at index {idx}: {type(item)}")

    return bytes(message)


def validate_byte_sequence(data: ByteSequence) -> None:
    """
    Validate that a sequence can be converted to bytes.

    Args:
        data: The sequence to validate.

    Raises:
        ValueError: If an integer is outside the valid byte range (0-255)
                    or if an unsupported type is found.
    """
    for idx, item in enumerate(data):
        if isinstance(item, int):
            _validate_byte_int(item, idx)
        elif not isinstance(item, (bytes, bytearray, memoryview)):
            raise ValueError(f"Unsupported data type at index {idx}: {type(item)}")
