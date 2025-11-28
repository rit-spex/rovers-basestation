import logging
import os
import threading
import time
from typing import Dict, Optional, Sequence, Tuple, Union

from utils.bytes import convert_to_bytes

logger = logging.getLogger(__name__)


class XbeeCommunicationManager:
    def __init__(self, xbee_device=None, remote_xbee=None):
        self.xbee_device = xbee_device
        self.remote_xbee = remote_xbee
        self.enabled = True
        self.last_message: Optional[bytes] = None
        # Track inflight messages with an event, result container and timestamp
        # Tuple contents: (Event, result_container, timestamp)
        self._inflight_messages: Dict[bytes, Tuple[threading.Event, dict, float]] = {}
        self._message_lock = threading.RLock()
        timeout_str = os.environ.get("XBEE_INFLIGHT_WAIT_TIMEOUT", "30.0")
        try:
            self.inflight_wait_timeout = float(timeout_str)
        except ValueError as e:
            raise ValueError(
                f"Invalid XBEE_INFLIGHT_WAIT_TIMEOUT value: '{timeout_str}'. Expected a numeric value."
            ) from e
        # Ensure wait timeout is positive; threading.Event.wait requires a positive timeout.
        if self.inflight_wait_timeout <= 0:
            raise ValueError(
                f"XBEE_INFLIGHT_WAIT_TIMEOUT must be a positive number, got: {self.inflight_wait_timeout}"
            )
        # When inflight entry is very old, consider it stale and allow cleanup
        # Default to 3x the wait_timeout to prevent premature cleanup
        default_max_age = self.inflight_wait_timeout * 3.0
        max_age_str = os.environ.get(
            "XBEE_INFLIGHT_ENTRY_MAX_AGE", str(default_max_age)
        )
        try:
            self.inflight_entry_max_age = float(max_age_str)
            if self.inflight_entry_max_age <= 0:
                raise ValueError(
                    f"XBEE_INFLIGHT_ENTRY_MAX_AGE must be positive, got: {self.inflight_entry_max_age}"
                )
        except ValueError:
            logger.warning(
                "Invalid XBEE_INFLIGHT_ENTRY_MAX_AGE value '%s', using default %s",
                max_age_str,
                default_max_age,
            )
            self.inflight_entry_max_age = default_max_age

    def _convert_to_bytes(
        self,
        data: Union[
            bytes,
            bytearray,
            memoryview,
            Sequence[Union[int, bytes, bytearray, memoryview]],
        ],
    ) -> bytes:
        """Convert data to bytes using the shared utility."""
        return convert_to_bytes(data)

    def _is_inflight_entry_stale(
        self, inflight_entry: Tuple[threading.Event, dict, float]
    ) -> bool:
        """Return True if the provided inflight entry is older than the configured max age.

        Kept as a helper to keep send_package flow simple and testable.
        """
        _, _result, ts = inflight_entry
        return time.time() - ts > self.inflight_entry_max_age

    def _create_inflight_entry(
        self, message_key: bytes
    ) -> Tuple[threading.Event, dict, float]:
        event_obj = threading.Event()
        result_container: dict = {}
        entry = (event_obj, result_container, time.time())
        self._inflight_messages[message_key] = entry
        return entry

    def _cleanup_stale_inflight_entry(
        self, message_key: bytes, inflight_entry: Tuple[threading.Event, dict, float]
    ) -> None:
        """Tidy up a stale inflight entry so the message can be retried.

        This method will try to wake any waiters for the stale entry with a
        failure indicator (sent=False) and remove the mapping from the dict.
        Locking should be managed by the caller.
        """
        try:
            event_obj_old, result_container_old, _ = inflight_entry
            result_container_old["sent"] = False
            event_obj_old.set()
        except Exception:
            logger.exception("Failed to clean up stale inflight entry")
        # Make sure the mapping is removed so we can create a fresh entry
        self._inflight_messages.pop(message_key, None)

    def _wait_for_inflight_result(
        self, event_obj: threading.Event, result_container: dict
    ) -> bool:
        event_completed = event_obj.wait(timeout=self.inflight_wait_timeout)
        if not event_completed:
            logger.warning(
                "Timed out waiting for in-flight message after %ss",
                self.inflight_wait_timeout,
            )
            return False
        return result_container.get("sent", False)

    def _perform_send(
        self, message_key: bytes, message_bytes: bytes, event_obj_local: threading.Event
    ) -> bool:
        sent_result = False
        try:
            if self.xbee_device:
                self.xbee_device.send_data(self.remote_xbee, message_bytes)
                sent_result = True
            # Update last_message only after a successful send
            with self._message_lock:
                if sent_result:
                    self.last_message = message_key
        finally:
            # Only remove inflight entry if it's the same entry we started sending to avoid removing newer entries.
            with self._message_lock:
                curr = self._inflight_messages.get(message_key)
                if curr is not None and curr[0] is event_obj_local:
                    entry = self._inflight_messages.pop(message_key, None)
                    if entry is not None:
                        event_obj, result_container, _ = entry
                        result_container["sent"] = sent_result
                        event_obj.set()

        return sent_result

    def send_package(
        self,
        data: Union[bytes, bytearray, memoryview, Sequence[Union[int, bytes]]],
        skip_duplicate_check: bool = False,
    ) -> bool:
        if not self.enabled or not self.xbee_device or not self.remote_xbee:
            return False

        try:
            message_bytes = self._convert_to_bytes(data)
            message_key = message_bytes

            # Prepare inflight entry / duplicate detection
            with self._message_lock:
                if (
                    not skip_duplicate_check
                    and self.last_message is not None
                    and message_key == self.last_message
                ):
                    logger.debug("Duplicate message detected and skipped (XBee)")
                    return True

                inflight_entry = self._inflight_messages.get(message_key)
                if inflight_entry is not None and self._is_inflight_entry_stale(
                    inflight_entry
                ):
                    logger.warning(
                        "Found stale inflight entry for message (age %.1fs); allowing new send",
                        time.time() - inflight_entry[2],
                    )
                    # Wake waiters and remove stale entry
                    self._cleanup_stale_inflight_entry(message_key, inflight_entry)
                    inflight_entry = None

                if inflight_entry is None:
                    (
                        event_obj_local,
                        result_container_local,
                        _,
                    ) = self._create_inflight_entry(message_key)
                    do_send = True
                else:
                    event_obj_local, result_container_local, _ = inflight_entry
                    do_send = False

            if not do_send:
                return self._wait_for_inflight_result(
                    event_obj_local, result_container_local
                )

            return self._perform_send(message_key, message_bytes, event_obj_local)

        except ValueError:
            raise
        except Exception:
            logger.exception("Failed to send compact message")
            return False

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False
