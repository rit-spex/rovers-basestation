"""
Comms module for XBee msg formatting and transmission.
Handles the protocol msg creation and data packing.
"""

import logging
import struct
import threading
from collections.abc import Sequence as AbcSequence
from typing import Dict, Sequence, Union

from utils.bytes import convert_to_bytes

from .command_codes import CONSTANTS
from .encoding import MessageEncoder
from .udp_communication import UdpCommunicationManager
from .xbee_communication import XbeeCommunicationManager

logger = logging.getLogger(__name__)


class MessageFormatter:
    """
    Formats controller data into XBee transmission msgs.
    """

    def __init__(self):
        """
        Init the msg formatter.
        """
        self.encoder = MessageEncoder()

    def create_xbox_message(self, values: Dict, reverse_mode: bool = False) -> list:
        """
        Create Xbox controller msg for transmission.

        Args:
            values: Xbox controller values dict
            reverse_mode: Whether reverse mode is enabled

            Returns:
            list[int]: Formatted msg data (each element is a single byte integer)
        """

        temp_dict = values.copy()

        if reverse_mode:
            # In reverse mode, swap the Y axes
            left_y = values.get(
                CONSTANTS.XBOX.JOYSTICK.AXIS_LY, CONSTANTS.XBOX.JOYSTICK.NEUTRAL_INT
            )
            right_y = values.get(
                CONSTANTS.XBOX.JOYSTICK.AXIS_RY, CONSTANTS.XBOX.JOYSTICK.NEUTRAL_INT
            )

            # update the values in the dict for packing
            temp_dict[CONSTANTS.XBOX.JOYSTICK.AXIS_LY] = right_y
            temp_dict[CONSTANTS.XBOX.JOYSTICK.AXIS_RY] = left_y

        # Return as a list[int] for testability while keeping encoding binary-safe.
        return list(
            self.encoder.encode_data(temp_dict, CONSTANTS.COMPACT_MESSAGES.XBOX_ID)
        )

    def create_n64_message(self, values: Dict) -> list:
        """
        Create N64 controller msg for transmission.

        Args:
            values: N64 controller values dict

            Returns:
            list[int]: Formatted msg data (each element is a single byte integer)
        """

        # Pack N64 button data.
        #
        # IMPORTANT: N64 joystick axis indices overlap with N64 button indices
        # (e.g., AXIS_X=0 conflicts with C_DOWN=0). To prevent accidental axis
        # values being interpreted as 2-bit button values, only pass the
        # expected N64 button fields (string keys) to the encoder.

        expected_keys = self.encoder.get_messages()[CONSTANTS.COMPACT_MESSAGES.N64_ID]["values"].keys()
        filtered_values = {k: values[k] for k in expected_keys if k in values}

        return list(
            self.encoder.encode_data(filtered_values, CONSTANTS.COMPACT_MESSAGES.N64_ID)
        )

    def create_combined_message(self, xbox_values: Dict, n64_values: Dict) -> list:
        """
        Create a combined message containing both Xbox and N64 controller data.

        Args:
            xbox_values: Xbox controller values dict
            n64_values: N64 controller values dict

        Returns:
            list[int]: Combined message data as a list of byte integers
        """
        # Create individual messages
        xbox_message = self.create_xbox_message(xbox_values)
        n64_message = self.create_n64_message(n64_values)

        # Prepend START_MESSAGE so integrated messages are easily recognized by the
        # human test harness. START_MESSAGE is a single byte.
        start_byte = int.from_bytes(CONSTANTS.START_MESSAGE, byteorder="big")
        return [start_byte] + xbox_message + n64_message


class CommunicationManager:
    """
    Manages XBee comms and msg transmission.
    """

    def __init__(
        self, xbee_device=None, remote_xbee=None, simulation_mode: bool = False
    ):
        """
        Init the comms manager.

        Args:
            xbee_device: XBee device instance
            remote_xbee: Remote XBee device instance
        """
        self.xbee_device = xbee_device
        self.remote_xbee = remote_xbee

        # Type annotation for hardware_com to accept both communication manager types
        self.hardware_com: Union[UdpCommunicationManager, XbeeCommunicationManager]

        if simulation_mode:
            self.hardware_com = UdpCommunicationManager()
        else:
            self.hardware_com = XbeeCommunicationManager(xbee_device, remote_xbee)

        self.formatter = MessageFormatter()
        # Lock protecting last_xbox_message / last_n64_message to give a
        # consistent memory ordering when multiple threads call send methods.
        self._send_lock = threading.Lock()
        # Store last messages as lists for easy comparison with the formatter output
        self.last_xbox_message: list = []
        self.last_n64_message: list = []
        # Track last_combined_message to detect combined-message duplicates reliably.
        self.last_combined_message: list = []
        self.simulation_mode = simulation_mode
        self.enabled = True

    def send_controller_data(
        self, xbox_values: Dict, n64_values: Dict, reverse_mode: bool = False
    ) -> bool:
        """
        Send controller data via XBee using compact 10-byte format.

        Args:
            xbox_values: Xbox controller vals
            n64_values: N64 controller vals
            reverse_mode: Whether reverse mode is enabled

        Returns:
            bool: True if the message was sent or if a duplicate was suppressed, False if failed
        """

        try:
            message_sent = False

            if not xbox_values and not n64_values:
                return self._send_combined_default_message()

            if xbox_values:
                message_sent = (
                    self._send_xbox_message_if_new(xbox_values, reverse_mode)
                    or message_sent
                )

            if n64_values:
                message_sent = self._send_n64_message_if_new(n64_values) or message_sent

            return message_sent

        except ValueError:
            # Programming errors (bad input) should surface to the caller
            raise
        except Exception:
            logger.exception("Failed to send controller data")
            return False

    def send_quit_message(self) -> bool:
        """
        Send quit msg to rover with retry logic (critical command).

        Returns:
            bool: True if sent successfully, False otherwise
        """

        quit_message = self.formatter.encoder.encode_data(
            {}, CONSTANTS.COMPACT_MESSAGES.QUIT_ID
        )

        # Use retry_count=3 for quit messages since they're critical
        return self.send_package(quit_message, retry_count=3)

    def _send_combined_default_message(self) -> bool:
        """Send a combined empty Xbox/N64 default message.

        Returns True if the message was sent (or duplicate suppressed).
        """
        combined_message = self.formatter.create_combined_message({}, {})
        # Prefer tracking combined message equality separately (avoids relying on per-controller states).
        with self._send_lock:
            if combined_message == self.last_combined_message:
                return True  # duplicate suppressed
        success = self.send_package(bytes(combined_message))
        if success:
            # Track combined & per-controller messages for consistency.
            xbox_msg = self.formatter.create_xbox_message({}, False)
            n64_msg = self.formatter.create_n64_message({})
            with self._send_lock:
                self.last_combined_message = combined_message
                self.last_xbox_message = xbox_msg
                self.last_n64_message = n64_msg
        return success

    def _send_xbox_message_if_new(self, xbox_values: Dict, reverse_mode: bool) -> bool:
        """Send Xbox message if changed compared to the last sent message."""
        xbox_message = self.formatter.create_xbox_message(xbox_values, reverse_mode)
        # Best-effort duplicate suppression (TOCTOU race possible); use locks or an inflight primitive for strict semantics.
        with self._send_lock:
            if xbox_message == self.last_xbox_message:
                return True  # duplicate suppressed
        xb_bytes = bytes(xbox_message)
        success = self.send_package(xb_bytes)
        if success:
            with self._send_lock:
                self.last_xbox_message = xbox_message
        return success

    def _send_n64_message_if_new(self, n64_values: Dict) -> bool:
        """Send N64 message if changed compared to the last sent message."""
        n64_message = self.formatter.create_n64_message(n64_values)
        # Best-effort duplicate suppression (TOCTOU race possible); use locks or an inflight primitive for strict semantics.
        with self._send_lock:
            if n64_message == self.last_n64_message:
                return True  # duplicate suppressed
        n64_bytes = bytes(n64_message)
        success = self.send_package(n64_bytes)
        if success:
            with self._send_lock:
                self.last_n64_message = n64_message
        return success

    def send_heartbeat(self, timestamp_ms: int = 0) -> bool:
        """
        Send a compact heartbeat message (3 bytes total).

        Format: [HEARTBEAT_ID (1 byte)] [TIMESTAMP (2 bytes, little-endian)]

        Args:
            timestamp_ms: Timestamp in milliseconds (0-65535). If 0, current time is used.

        Returns:
            bool: True if sent successfully

        Example:
            comm.send_heartbeat()  # Auto timestamp
            comm.send_heartbeat(1234)  # Custom timestamp
        """

        if timestamp_ms == 0:
            import time

            timestamp_ms = int(time.time() * 1000) % 65536  # Keep in 2-byte range

        heartbeat_data = self.formatter.encoder.encode_data(
            {CONSTANTS.HEARTBEAT.TIMESTAMP_MESSAGE: timestamp_ms},
            CONSTANTS.COMPACT_MESSAGES.HEARTBEAT_ID,
        )

        return self.send_package(heartbeat_data, skip_duplicate_check=True)

    def enable(self):
        """
        Enable communication.
        """
        self.enabled = True

    def disable(self):
        """
        Disable communication.
        """
        self.enabled = False

    def send_package(
        self,
        data: Union[bytes, bytearray, memoryview, Sequence[Union[int, bytes]]],
        skip_duplicate_check: bool = False,
        retry_count: int = 0,
    ) -> bool:
        """
        Send a compact custom message (as few bytes as possible).

        Args:
            data: Bytes to send. Accepts bytes-like objects or a list containing ints (0..255) or
                  bytes-like elements (or a mix of both). Examples include:
                  - bytes
                  - bytearray
                  - memoryview
                  - List[int] (e.g., [0xAA, 0x01])
                  - List[Union[int, bytes]] (e.g., [b'\xaa', 0x01, 0x02])
            skip_duplicate_check: If True, always send even if identical to last message
            retry_count: Number of times to retry on failure (0 = no retries, just single attempt).
                        Use retry_count > 0 for critical messages like quit commands.

        Returns:
            bool: True if sent successfully or if a duplicate was suppressed, False otherwise

        Raises:
            ValueError: Raised when the payload contains invalid data types or integer
                values aka outside 0..255. Validation is during normalization and may
                also be raised by the hardware transport layer.
            TypeError: Re-raised to indicate the underlying transport doesn't accept
                the provided payload type (like passing a list where the hardware
                expects bytes).
        """

        # Normalize mixed list payloads: convert lists containing bytes-like elements to bytes.
        data = self._normalize_package_payload(data)

        try:
            # Try initial send
            if self.hardware_com.send_package(
                data, skip_duplicate_check=skip_duplicate_check
            ):
                return True

            # If initial send failed and retries are configured, try again
            for attempt in range(retry_count):
                logger.debug(f"Retrying send (attempt {attempt + 1}/{retry_count})")
                if self.hardware_com.send_package(
                    data, skip_duplicate_check=skip_duplicate_check
                ):
                    logger.info(f"Send succeeded on retry attempt {attempt + 1}")
                    return True

            # All attempts failed
            if retry_count > 0:
                logger.warning(f"Send failed after {retry_count + 1} attempts")
            return False
        except ValueError:
            # Important: Validation errors are programmer-level errors and should
            # bubble up to the caller.
            raise
        except TypeError:
            # Re-raise TypeError to allow callers to take corrective action
            # (e.g., convert list payloads to bytes and retry).
            raise
        except Exception:
            logger.exception("Failed to send package via hardware_com")
            return False

    def send_compact_message(
        self, data: Sequence[Union[int, bytes]], skip_duplicate_check: bool = False
    ) -> bool:
        """
        Send a compact custom message (as few bytes as possible).

        Args:
            data: List of bytes or integers to send
            skip_duplicate_check: If True, always send even if identical to last message

        Returns:
            bool: True if sent successfully, False otherwise
        """
        # Validate/normalize items first: ensure all list elements are ints or bytes-like
        self._validate_compact_message_list(data)

        # Attempt to send via the hardware abstraction and handle the list->bytes
        # fallback conversion in the helper.
        return self._hardware_send_or_convert(data, skip_duplicate_check)

    def _validate_compact_message_list(self, data: Sequence[Union[int, bytes]]) -> None:
        """Validate a compact message list to ensure each entry is either an
        integer 0..255 or a bytes-like object convertible to bytes.
        """
        if not isinstance(data, AbcSequence):
            raise TypeError("data must be a sequence of ints or bytes-like objects")

        for idx, item in enumerate(data):
            if isinstance(item, int):
                if item < 0 or item > 255:
                    raise ValueError(
                        f"Integer value at index {idx} out of range for a byte: {item} (expected 0..255)"
                    )
            elif not isinstance(item, (bytes, bytearray, memoryview)):
                raise ValueError(f"Unsupported data type at index {idx}: {type(item)}")

    # NOTE: _convert_compact_list_to_bytes was removed; use the consolidated `_convert_list_to_bytes` helper instead.

    def _hardware_send_or_convert(
        self, data: Sequence[Union[int, bytes]], skip_duplicate_check: bool
    ) -> bool:
        """Attempt to send a list payload on the underlying hardware. If the
        hardware does not support list payloads, convert them to bytes and
        retry once.
        """
        try:
            return self.hardware_com.send_package(data, skip_duplicate_check)
        except TypeError:
            # The underlying transport doesn't accept the list type; convert it to
            # a compact bytes payload and retry once.
            message = self._convert_list_to_bytes(data)
            logger.debug(
                "send_compact_message fell back to bytes conversion before sending"
            )
            try:
                return self.send_package(
                    bytes(message), skip_duplicate_check=skip_duplicate_check
                )
            except ValueError:
                # Propagate programmer errors (bad input) to the caller
                raise
            except Exception:
                logger.exception(
                    "Failed to send compact message after fallback conversion"
                )
                return False
        except ValueError:
            # Validation errors should surface to the caller
            raise
        except Exception:
            logger.exception("Failed to send compact message")
            return False

    def _normalize_package_payload(
        self, data: Union[bytes, bytearray, memoryview, Sequence[Union[int, bytes]]]
    ) -> Union[bytes, bytearray, memoryview, Sequence[Union[int, bytes]]]:
        """Normalize package payloads for `send_package`.

        Accepts bytes-like objects and lists of ints (0..255). If a list contains
        bytes-like elements, it will be converted to a single bytes object. If a
        list contains only ints, it is returned as-is.

        Raises:
            ValueError: For unsupported element types or integer values out of
                        the 0..255 range.
        """
        if isinstance(data, (bytes, bytearray, memoryview)):
            return data

        if isinstance(data, AbcSequence):
            if self._list_contains_bytes_like(data):
                return self._convert_list_to_bytes(data)
            else:
                # Validate ints
                self._validate_int_list(data)
                return data

        # Unknown payload type
        raise TypeError("data must be bytes-like or a sequence of ints (0..255)")

    def _list_contains_bytes_like(self, data: Sequence) -> bool:
        """Return True if any element in the list is bytes-like."""
        return any(isinstance(item, (bytes, bytearray, memoryview)) for item in data)

    def _validate_int_list(self, data: Sequence) -> None:
        """Validate all items in the list are ints in range 0..255.

        Raises ValueError on invalid types or out-of-range values.
        """
        for idx, item in enumerate(data):
            if not isinstance(item, int):
                raise ValueError(f"Unsupported data type at index {idx}: {type(item)}")
            if item < 0 or item > 255:
                raise ValueError(
                    f"Integer value at index {idx} out of range for a byte: {item} (expected 0..255)"
                )

    def _convert_list_to_bytes(self, data: Sequence[Union[int, bytes]]) -> bytes:
        """Convert a validated sequence of ints and bytes-like elements to bytes.

        Uses the shared convert_to_bytes utility for consistent behavior.
        """
        return convert_to_bytes(data)

    def send_status_update(
        self, status_code: int, battery_level: int, signal_strength: int
    ) -> bool:
        """
        Send a status update message.

        Args:
            status_code: System status code
            battery_level: Battery level percentage (0-100)
            signal_strength: Signal strength percentage (0-100)

        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            data = [
                CONSTANTS.COMPACT_MESSAGES.STATUS,
                status_code & 0xFF,
                battery_level & 0xFF,
                signal_strength & 0xFF,
            ]
            return self.send_compact_message(data)
        except ValueError:
            raise
        except Exception:
            logger.exception("Failed to send status update")
            return False

    def send_error_code(self, error_code: int, severity: int) -> bool:
        """
        Send an error code message.

        Args:
            error_code: Error code
            severity: Error severity level (0-255)

        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            data = [
                CONSTANTS.COMPACT_MESSAGES.ERROR,
                error_code & 0xFF,
                severity & 0xFF,
            ]
            return self.send_compact_message(data)
        except ValueError:
            raise
        except Exception:
            logger.exception("Failed to send error code")
            return False

    def send_gps_position(self, latitude: float, longitude: float) -> bool:
        """
        Send GPS position data.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate

        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            lat_bytes = struct.pack(">f", latitude)  # latitude as float
            lon_bytes = struct.pack(">f", longitude)  # longitude as float

            data = [CONSTANTS.COMPACT_MESSAGES.GPS] + list(lat_bytes) + list(lon_bytes)
            return self.send_compact_message(data)
        except ValueError:
            raise
        except Exception:
            logger.exception("Failed to send GPS position")
            return False

    def send_sensor_reading(self, sensor_id: int, reading: int) -> bool:
        """
        Send a sensor reading.

        Args:
            sensor_id: Sensor identifier
            reading: Sensor reading value (integer 0-65535 inclusive). The value
                     will be sent as two bytes (high byte followed by low byte).
                     Units depend on the sensor; callers must supply a unit-
                     appropriate integer value.

        Returns:
            bool: True if sent successfully, False otherwise
        """
        # Validate reading is a 16-bit integer (0..65535) and raise ValueError for invalid values.
        if not isinstance(reading, int):
            raise ValueError(
                f"reading must be an int in range 0..65535; got {type(reading)!r}"
            )
        if reading < 0 or reading > 0xFFFF:
            raise ValueError(f"reading out of bounds: {reading} (expected 0..65535)")

        try:
            # Split the 2-byte reading into two 1-byte values
            low_byte = reading & 0xFF
            high_byte = (reading >> 8) & 0xFF

            data = [
                CONSTANTS.COMPACT_MESSAGES.SENSOR,
                sensor_id & 0xFF,
                high_byte,
                low_byte,
            ]
            return self.send_compact_message(data)
        except ValueError:
            raise
        except Exception:
            logger.exception("Failed to send sensor reading")
            return False
