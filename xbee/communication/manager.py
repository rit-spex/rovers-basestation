"""
High-level communication manager.

CommunicationManager is the main interface for sending data to the rover.
It handles:
    - Message formatting (converting controller values to wire format)
    - Duplicate message suppression
    - Retry logic for critical messages
    - Routing to the correct backend (XBee or UDP)

MessageFormatter creates the actual byte payloads from controller value dicts.

Usage:
    comm = CommunicationManager(xbee_device, remote_xbee, simulation_mode=False)
    comm.send_controller_data(xbox_values, n64_values)
    comm.send_heartbeat()
    comm.send_quit_message()
"""

import logging
import os
import threading
from collections.abc import Sequence as AbcSequence
from typing import Dict, Sequence, TypeAlias, Union

from utils.bytes import convert_to_bytes
from xbee.communication.udp_backend import UdpCommunicationManager
from xbee.communication.xbee_backend import XbeeCommunicationManager
from xbee.config.constants import CONSTANTS
from xbee.protocol.encoding import MessageEncoder

logger = logging.getLogger(__name__)

_TRUTHY_ENV = frozenset(("1", "true", "yes", "on"))

ByteElement: TypeAlias = Union[int, bytes, bytearray, memoryview]
PayloadLike: TypeAlias = Union[bytes, bytearray, memoryview, Sequence[ByteElement]]


class MessageFormatter:
    def __init__(self):
        self.encoder = MessageEncoder()

    def create_xbox_message(self, values: Dict, reverse_mode: bool = False) -> list:
        """Create Xbox controller msg for transmission."""

        temp_dict = values.copy()

        if reverse_mode:
            # In reverse mode, swap the Y axes
            left_y_num = values.get(
                CONSTANTS.XBOX.JOYSTICK.AXIS_LY, CONSTANTS.XBOX.JOYSTICK.NEUTRAL_INT
            )
            right_y_num = values.get(
                CONSTANTS.XBOX.JOYSTICK.AXIS_RY, CONSTANTS.XBOX.JOYSTICK.NEUTRAL_INT
            )

            # ControllerState typically exposes both numeric keys and alias-string
            # keys (e.g., AXIS_LY and AXIS_LY_STR). Keep both representations in
            # sync so encoding preference for alias keys does not defeat reverse
            # mode swapping.
            left_y_alias = values.get(CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR, left_y_num)
            right_y_alias = values.get(CONSTANTS.XBOX.JOYSTICK.AXIS_RY_STR, right_y_num)

            # update the values in the dict for packing
            temp_dict[CONSTANTS.XBOX.JOYSTICK.AXIS_LY] = right_y_num
            temp_dict[CONSTANTS.XBOX.JOYSTICK.AXIS_RY] = left_y_num
            temp_dict[CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR] = right_y_alias
            temp_dict[CONSTANTS.XBOX.JOYSTICK.AXIS_RY_STR] = left_y_alias

        # Return as a list[int] for testability while keeping encoding binary-safe.
        return list(
            self.encoder.encode_data(temp_dict, CONSTANTS.COMPACT_MESSAGES.XBOX_ID)
        )

    def create_n64_message(self, values: Dict) -> list:
        """Create N64 controller msg for transmission."""

        # Pack N64 button data.
        #
        # IMPORTANT: N64 joystick axis indices overlap with N64 button indices
        # (e.g., AXIS_X=0 conflicts with C_DOWN=0). To prevent accidental axis
        # values being interpreted as 2-bit button values, only pass the
        # expected N64 button fields (string keys) to the encoder.

        expected_keys = self.encoder.get_messages()[CONSTANTS.COMPACT_MESSAGES.N64_ID][
            "values"
        ].keys()
        filtered_values = {k: values[k] for k in expected_keys if k in values}

        return list(
            self.encoder.encode_data(filtered_values, CONSTANTS.COMPACT_MESSAGES.N64_ID)
        )

    def create_combined_message(self, xbox_values: Dict, n64_values: Dict) -> list:
        """Create a combined Xbox + N64 message with START_MESSAGE prefix."""
        # Create individual messages
        xbox_message = self.create_xbox_message(xbox_values)
        n64_message = self.create_n64_message(n64_values)

        # Prepend START_MESSAGE so integrated messages are easily recognized by the
        # human test harness. START_MESSAGE is a single byte.
        start_byte = int.from_bytes(CONSTANTS.START_MESSAGE, byteorder="big")
        return [start_byte] + xbox_message + n64_message

    def create_spacemouse_message(self, values: Dict) -> list:
        """Create SpaceMouse 6DOF message for transmission."""
        return list(
            self.encoder.encode_data(
                values, CONSTANTS.COMPACT_MESSAGES.SPACEMOUSE_ID
            )
        )

    def create_keyboard_message(self, values: Dict) -> list:
        """Create keyboard input message for transmission."""
        return list(
            self.encoder.encode_data(
                values, CONSTANTS.COMPACT_MESSAGES.KEYBOARD_ID
            )
        )


class CommunicationManager:
    def __init__(
        self, xbee_device=None, remote_xbee=None, simulation_mode: bool = False
    ):
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
        self.last_auto_state_message: list = []
        self.last_spacemouse_message: list = []
        self.last_keyboard_message: list = []
        self.simulation_mode = simulation_mode
        self.enabled = True
        # In simulation mode the whole point is verifying communication, so
        # protocol tracing is always enabled.  In production (XBee) mode it
        # can still be toggled via the ROVER_PROTOCOL_TRACE env var.
        if simulation_mode:
            self.protocol_trace = True
        else:
            self.protocol_trace = (
                os.environ.get("ROVER_PROTOCOL_TRACE", "0").strip().lower()
                in _TRUTHY_ENV
            )

        # Also propagate to the UDP backend so RX tracing is on too.
        if simulation_mode and hasattr(self.hardware_com, "_protocol_trace"):
            self.hardware_com._protocol_trace = True

    def _trace_outgoing_protocol_packet(self, data: PayloadLike) -> None:
        """Best-effort protocol trace logging for outgoing payloads."""
        try:
            if isinstance(data, (bytes, bytearray, memoryview)):
                raw = bytes(data)
            else:
                raw = self._convert_list_to_bytes(data)

            decoded, message_id = self.formatter.encoder.decode_data(raw)
            message_name = self.formatter.encoder.get_message_name(message_id)
            logger.info(
                "[protocol tx] id=0x%02X name=%s payload=%s bytes=%s",
                message_id,
                message_name,
                decoded,
                raw.hex(" "),
            )
        except Exception:
            try:
                fallback_raw = (
                    bytes(data)
                    if isinstance(data, (bytes, bytearray, memoryview))
                    else self._convert_list_to_bytes(data)
                )
                logger.info("[protocol tx/raw] bytes=%s", fallback_raw.hex(" "))
            except Exception:
                logger.debug("[protocol tx] unable to render payload for tracing")

    def send_controller_data(
        self, xbox_values: Dict, n64_values: Dict, reverse_mode: bool = False
    ) -> bool:
        """Send controller data to the rover."""

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

            # Invalidate combined-default dedup cache after any non-empty send.
            # This prevents suppressing a subsequent "reset/default" combined payload
            # when controller data previously changed.
            if message_sent and (xbox_values or n64_values):
                with self._send_lock:
                    self.last_combined_message = []

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

    def send_spacemouse_data(self, spacemouse_values: Dict) -> bool:
        """Send SpaceMouse 6DOF data to the rover."""
        if not spacemouse_values:
            return True

        try:
            sm_message = self.formatter.create_spacemouse_message(spacemouse_values)
            with self._send_lock:
                if sm_message == self.last_spacemouse_message:
                    return True  # duplicate suppressed
            success = self.send_package(bytes(sm_message))
            if success:
                with self._send_lock:
                    self.last_spacemouse_message = sm_message
            return success
        except Exception:
            logger.exception("Failed to send SpaceMouse data")
            return False

    def clear_spacemouse_dedup(self) -> None:
        """Clear the SpaceMouse duplicate-suppression cache.

        Called after a disconnect so the first message on reconnect is
        guaranteed to be sent even if it matches the previous value.
        """
        with self._send_lock:
            self.last_spacemouse_message = []

    def send_keyboard_data(self, keyboard_values: Dict) -> bool:
        """Send keyboard input data to the rover."""
        if not keyboard_values:
            return True

        try:
            kb_message = self.formatter.create_keyboard_message(keyboard_values)
            with self._send_lock:
                if kb_message == self.last_keyboard_message:
                    return True  # duplicate suppressed
            success = self.send_package(bytes(kb_message))
            if success:
                with self._send_lock:
                    self.last_keyboard_message = kb_message
            return success
        except Exception:
            logger.exception("Failed to send keyboard data")
            return False

    def clear_keyboard_dedup(self) -> None:
        with self._send_lock:
            self.last_keyboard_message = []

    def send_heartbeat(self, timestamp_ms: int = 0) -> bool:
        """
        Send a compact heartbeat message (3 bytes total).

        Format: [HEARTBEAT_ID (1 byte)] [TIMESTAMP (2 bytes)]
        """

        if timestamp_ms == 0:
            import time

            timestamp_ms = int(time.time() * 1000) % 65536  # Keep in 2-byte range

        heartbeat_data = self.formatter.encoder.encode_data(
            {CONSTANTS.HEARTBEAT.TIMESTAMP_MESSAGE: timestamp_ms},
            CONSTANTS.COMPACT_MESSAGES.HEARTBEAT_ID,
        )

        return self.send_package(heartbeat_data, skip_duplicate_check=True)

    def send_auto_state(self, auto_state: int) -> bool:
        """Send current autonomous state command (0..5) to rover."""
        clamped = max(
            CONSTANTS.AUTO_STATE.MIN, min(CONSTANTS.AUTO_STATE.MAX, int(auto_state))
        )
        payload = list(
            self.formatter.encoder.encode_data(
                {CONSTANTS.AUTO_STATE.NAME: clamped},
                CONSTANTS.COMPACT_MESSAGES.AUTO_STATE_ID,
            )
        )

        with self._send_lock:
            if payload == self.last_auto_state_message:
                return True

        success = self.send_package(bytes(payload))
        if success:
            with self._send_lock:
                self.last_auto_state_message = payload
        return success

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def cleanup(self) -> None:
        cleanup_fn = getattr(self.hardware_com, "cleanup", None)
        if callable(cleanup_fn):
            cleanup_fn()
            return

        stop_fn = getattr(self.hardware_com, "stop", None)
        if callable(stop_fn):
            stop_fn()

    def register_telemetry_handler(self, handler) -> None:
        """Register a telemetry callback if the active backend supports it."""
        register_fn = getattr(self.hardware_com, "register_telemetry_handler", None)
        if callable(register_fn):
            register_fn(handler)

        # In simulation mode, ensure the UDP receive loop is running so incoming
        # rover telemetry can reach the registered callback and GUI.
        if self.simulation_mode:
            start_fn = getattr(self.hardware_com, "start", None)
            is_running = bool(getattr(self.hardware_com, "running", False))
            if callable(start_fn) and not is_running:
                start_fn()

    def send_package(
        self,
        data: PayloadLike,
        skip_duplicate_check: bool = False,
        retry_count: int = 0,
    ) -> bool:
        """
        Send a compact custom message (as few bytes as possible).

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

        if self.protocol_trace:
            self._trace_outgoing_protocol_packet(data)

        try:
            # Try initial send
            if self.hardware_com.send_package(
                data, skip_duplicate_check=skip_duplicate_check
            ):
                return True

            # If initial send failed and retries are configured, try again
            for attempt in range(retry_count):
                logger.debug(
                    "Retrying send (attempt %d/%d)",
                    attempt + 1,
                    retry_count,
                )
                if self.hardware_com.send_package(
                    data, skip_duplicate_check=skip_duplicate_check
                ):
                    logger.info("Send succeeded on retry attempt %d", attempt + 1)
                    return True

            # All attempts failed
            if retry_count > 0:
                logger.warning("Send failed after %d attempts", retry_count + 1)
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
        self, data: Sequence[ByteElement], skip_duplicate_check: bool = False
    ) -> bool:
        """Send a compact custom message (as few bytes as possible)."""
        # Validate/normalize items first: ensure all list elements are ints or bytes-like
        self._validate_compact_message_list(data)

        # Attempt to send via the hardware abstraction and handle the list->bytes
        # fallback conversion in the helper.
        return self._hardware_send_or_convert(data, skip_duplicate_check)

    def _validate_compact_message_list(self, data: Sequence[ByteElement]) -> None:
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

    def _hardware_send_or_convert(
        self, data: Sequence[ByteElement], skip_duplicate_check: bool
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
                    message, skip_duplicate_check=skip_duplicate_check
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

    def _normalize_package_payload(self, data: PayloadLike) -> PayloadLike:
        """Normalize package payloads for `send_package`."""
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
        return any(isinstance(item, (bytes, bytearray, memoryview)) for item in data)

    def _validate_int_list(self, data: Sequence) -> None:
        for idx, item in enumerate(data):
            if not isinstance(item, int):
                raise ValueError(f"Unsupported data type at index {idx}: {type(item)}")
            if item < 0 or item > 255:
                raise ValueError(
                    f"Integer value at index {idx} out of range for a byte: {item} (expected 0..255)"
                )

    def _convert_list_to_bytes(self, data: Sequence[ByteElement]) -> bytes:
        return convert_to_bytes(data)
