"""
XBee radio hardware transport backend.

Sends byte payloads over XBee radio via the digi.xbee library.
Includes inflight message deduplication to prevent sending the
same payload twice simultaneously.

This is used by CommunicationManager when simulation_mode=False.
"""

import logging
import os
import threading
import time
from typing import Callable, Dict, Optional, Sequence, Tuple, TypeAlias, Union

from utils.bytes import convert_to_bytes

logger = logging.getLogger(__name__)

ByteElement: TypeAlias = Union[int, bytes, bytearray, memoryview]
PayloadLike: TypeAlias = Union[bytes, bytearray, memoryview, Sequence[ByteElement]]


class XbeeCommunicationManager:
    """Features:
        - Duplicate message suppression (skips if same as last sent)
        - Inflight tracking (if another thread is sending the same payload,
          wait for its result instead of sending again)
        - Configurable timeouts via environment variables
    """

    def __init__(self, xbee_device=None, remote_xbee=None):
        self.xbee_device = xbee_device
        self.remote_xbee = remote_xbee
        self.enabled = True
        self.last_message: Optional[bytes] = None
        self._telemetry_handler: Optional[Callable[[dict], None]] = None

        # Inflight tracking: {message_bytes: (Event, result_dict, timestamp)}
        self._inflight_messages: Dict[bytes, Tuple[threading.Event, dict, float]] = {}
        self._message_lock = threading.RLock()

        # Timeout configuration from environment
        timeout_str = os.environ.get("XBEE_INFLIGHT_WAIT_TIMEOUT", "30.0")
        try:
            self.inflight_wait_timeout = float(timeout_str)
        except ValueError as e:
            raise ValueError(
                f"Invalid XBEE_INFLIGHT_WAIT_TIMEOUT value: '{timeout_str}'"
            ) from e
        if self.inflight_wait_timeout <= 0:
            raise ValueError(
                f"XBEE_INFLIGHT_WAIT_TIMEOUT must be a positive number, got: {self.inflight_wait_timeout}"
            )

        # Stale entry cleanup threshold (default: 3x wait timeout)
        default_max_age = self.inflight_wait_timeout * 3.0
        max_age_str = os.environ.get(
            "XBEE_INFLIGHT_ENTRY_MAX_AGE", str(default_max_age)
        )
        try:
            self.inflight_entry_max_age = float(max_age_str)
            if self.inflight_entry_max_age <= 0:
                raise ValueError(
                    f"Must be a positive number, got: {self.inflight_entry_max_age}"
                )
        except ValueError:
            logger.warning(
                "Invalid XBEE_INFLIGHT_ENTRY_MAX_AGE '%s', using default %s",
                max_age_str,
                default_max_age,
            )
            self.inflight_entry_max_age = default_max_age

    def send_package(
        self,
        data: PayloadLike,
        skip_duplicate_check: bool = False,
    ) -> bool:
        """Send a message over XBee.

        Returns True if sent successfully or duplicate suppressed.
        """
        if not self.enabled or not self.xbee_device or not self.remote_xbee:
            return False

        try:
            message_bytes = self._convert_to_bytes(data)
            message_key = message_bytes

            with self._message_lock:
                # Duplicate check
                if not skip_duplicate_check and self.last_message == message_key:
                    logger.debug("Duplicate message skipped (XBee)")
                    return True

                # Check inflight
                inflight = self._inflight_messages.get(message_key)
                if inflight is not None and self._is_stale(inflight):
                    logger.warning(
                        "Stale inflight entry (age %.1fs); cleaning up",
                        time.time() - inflight[2],
                    )
                    self._cleanup_stale(message_key, inflight)
                    inflight = None

                if inflight is None:
                    # We're the sender
                    event_obj, result, _ = self._create_inflight(message_key)
                    do_send = True
                else:
                    # Another thread is already sending this; wait for its result
                    event_obj, result, _ = inflight
                    do_send = False

            if not do_send:
                return self._wait_for_result(event_obj, result)

            return self._perform_send(message_key, message_bytes, event_obj)

        except ValueError:
            raise
        except Exception:
            logger.exception("Failed to send message")
            return False

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def register_telemetry_handler(self, handler: Callable[[dict], None]) -> None:
        """Register telemetry callback (reserved for future receive-path support)."""
        self._telemetry_handler = handler

    def _convert_to_bytes(self, data: PayloadLike) -> bytes:
        return convert_to_bytes(data)

    # --- Internal helpers ---

    def _is_stale(self, entry: Tuple[threading.Event, dict, float]) -> bool:
        return time.time() - entry[2] > self.inflight_entry_max_age

    def _create_inflight(self, key: bytes) -> Tuple[threading.Event, dict, float]:
        event = threading.Event()
        result: dict = {}
        entry = (event, result, time.time())
        self._inflight_messages[key] = entry
        return entry

    def _cleanup_stale(self, key: bytes, entry: Tuple[threading.Event, dict, float]):
        try:
            entry[1]["sent"] = False
            entry[0].set()
        except Exception:
            logger.exception("Failed to clean up stale inflight entry")
        self._inflight_messages.pop(key, None)

    def _wait_for_result(self, event: threading.Event, result: dict) -> bool:
        if not event.wait(timeout=self.inflight_wait_timeout):
            logger.warning(
                "Timed out waiting for inflight message after %ss",
                self.inflight_wait_timeout,
            )
            return False
        return result.get("sent", False)

    def _perform_send(
        self, key: bytes, payload: bytes, our_event: threading.Event
    ) -> bool:
        sent = False
        try:
            if self.xbee_device:
                self.xbee_device.send_data(self.remote_xbee, payload)
                sent = True
            with self._message_lock:
                if sent:
                    self.last_message = key
        finally:
            with self._message_lock:
                curr = self._inflight_messages.get(key)
                if curr is not None and curr[0] is our_event:
                    entry = self._inflight_messages.pop(key, None)
                    if entry:
                        entry[1]["sent"] = sent
                        entry[0].set()
        return sent
