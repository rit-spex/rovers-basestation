"""
UDP simulation transport backend.

Used for testing without real XBee hardware. Sends encoded messages
as JSON-wrapped UDP packets to localhost.

Classes:
    UdpMessage                    - JSON-serializable message wrapper
    UdpCommunicationManager       - UDP socket transport
    SimulationCommunicationManager - Convenience wrapper for simulation mode
"""

import json
import logging
import os
import socket
import threading
import time
from typing import Any, Callable, Dict, Optional, Sequence, Tuple, TypeAlias, Union

from utils.bytes import convert_to_bytes, validate_byte_sequence
from xbee.config.constants import CONSTANTS
from xbee.protocol.encoding import MessageEncoder

logger = logging.getLogger(__name__)

ByteElement: TypeAlias = Union[int, bytes, bytearray, memoryview]
PayloadLike: TypeAlias = Union[bytes, bytearray, memoryview, Sequence[ByteElement]]

try:
    DEFAULT_INFLIGHT_WAIT_TIMEOUT = float(
        os.environ.get("XBEE_INFLIGHT_WAIT_TIMEOUT", "30.0")
    )
except ValueError as e:
    logger.warning(
        "Invalid XBEE_INFLIGHT_WAIT_TIMEOUT value, using default 30.0: %s", e
    )
    DEFAULT_INFLIGHT_WAIT_TIMEOUT = 30.0


class UdpMessage:
    def __init__(
        self, message_type: str, data: Dict[str, Any], timestamp: Optional[float] = None
    ):
        self.message_type = message_type
        self.data = data
        self.timestamp = timestamp

    def to_json(self) -> str:
        ts = self.timestamp if self.timestamp is not None else time.time()
        return json.dumps(
            {"type": self.message_type, "data": self.data, "timestamp": ts}
        )

    @classmethod
    def from_json(cls, json_str: str) -> "UdpMessage":
        data = json.loads(json_str)
        if "type" not in data:
            raise ValueError("Missing required field 'type' in JSON message")
        if "data" not in data:
            raise ValueError("Missing required field 'data' in JSON message")
        # Leave timestamp unset if not provided so callers can distinguish missing vs. parsed timestamps.
        timestamp = data.get("timestamp")
        return cls(data["type"], data["data"], timestamp=timestamp)


class SimulationCommunicationManager:
    """Convenience wrapper for UdpCommunicationManager with telemetry handler support.

    This class provides a simplified interface for simulation mode, automatically
    starting the UDP manager and providing telemetry handler registration.
    """

    def __init__(self, auto_start: bool = True):
        self.udp_manager = UdpCommunicationManager(auto_start=auto_start)
        logger.info("Simulation communication manager initialized with UDP")

    def send_controller_data(
        self,
        xbox_values: Dict[Any, Any],
        n64_values: Dict[Any, Any],
        reverse_mode: bool,
    ) -> bool:
        return self.udp_manager.send_controller_data(
            xbox_values, n64_values, reverse_mode
        )

    def send_quit_message(self) -> bool:
        return self.udp_manager.send_quit_message()

    def send_heartbeat(self) -> bool:
        return self.udp_manager.send_heartbeat()

    def register_telemetry_handler(self, handler: Callable[[Dict[str, Any]], None]):
        def message_handler(udp_message: UdpMessage):
            try:
                handler(udp_message.data)
            except Exception:
                logger.exception("Error in telemetry handler")

        self.udp_manager.register_message_handler("telemetry", message_handler)

    def get_statistics(self) -> Dict[str, Any]:
        return self.udp_manager.get_statistics()

    def cleanup(self):
        self.udp_manager.stop()


class UdpCommunicationManager:
    def __init__(self, auto_start: bool = False):
        self.host = CONSTANTS.COMMUNICATION.UDP_HOST
        self.basestation_port = CONSTANTS.COMMUNICATION.UDP_BASESTATION_PORT
        self.rover_port = CONSTANTS.COMMUNICATION.UDP_ROVER_PORT
        self.telemetry_port = CONSTANTS.COMMUNICATION.UDP_TELEMETRY_PORT

        self.send_socket: Optional[socket.socket] = None
        self.receive_socket: Optional[socket.socket] = None
        self._create_sockets()

        self.running = False
        self.receive_thread: Optional[threading.Thread] = None

        self.message_handlers: Dict[str, Callable[[UdpMessage], None]] = {}

        self.messages_sent = 0
        self.messages_received = 0
        self.last_telemetry: Dict[str, Any] = {}
        self.last_message: Optional[bytes] = None
        self._inflight_messages: Dict[bytes, Tuple[threading.Event, dict]] = {}
        self.inflight_wait_timeout = DEFAULT_INFLIGHT_WAIT_TIMEOUT
        self._message_lock = threading.RLock()
        self._telemetry_handler: Optional[Callable[[Dict[str, Any]], None]] = None
        self._decoder = MessageEncoder()

        self._setup_sockets()

        if auto_start:
            self.start()

    def _create_sockets(self):
        self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.send_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.receive_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def _setup_sockets(self):
        if self.receive_socket is None or self.send_socket is None:
            raise RuntimeError("UDP sockets are not initialized")

        receive_socket = self.receive_socket
        try:
            receive_socket.bind((self.host, self.telemetry_port))
            receive_socket.settimeout(1.0)
            logger.info("UDP receiver bound to %s:%d", self.host, self.telemetry_port)
            logger.info("UDP sender configured for %s:%d", self.host, self.rover_port)

        except Exception:
            logger.exception("Failed to setup UDP sockets")
            raise

    def start(self):
        if self.running:
            return

        if self.send_socket is None or self.receive_socket is None:
            self._create_sockets()
            self._setup_sockets()

        self.running = True

        self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receive_thread.start()

        logger.info("UDP communication started")

    def stop(self):
        was_running = self.running
        self.running = False

        if was_running and self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=2.0)

        try:
            send_socket = self.send_socket
            if send_socket is not None:
                send_socket.close()
                self.send_socket = None
            receive_socket = self.receive_socket
            if receive_socket is not None:
                receive_socket.close()
                self.receive_socket = None
        except Exception:
            logger.exception("Error closing UDP sockets")

        logger.info("UDP communication stopped")

    def _send_message(self, message: bytes) -> bool:
        try:
            if self.send_socket is None:
                logger.error("UDP send socket unavailable")
                return False
            self.send_socket.sendto(message, (self.host, self.rover_port))
            with self._message_lock:
                self.messages_sent += 1
            return True
        except Exception:
            logger.exception("Failed to send UDP message")
            return False

    def _validate_payload(self, data: PayloadLike):
        if isinstance(data, (bytes, bytearray, memoryview)):
            return
        validate_byte_sequence(data)

    def _convert_to_bytes(self, data: PayloadLike) -> bytes:
        """Convert data to bytes using the shared utility."""
        return convert_to_bytes(data)

    def _extract_recvfrom_bytes(self, result) -> Optional[bytes]:
        """
        Attempt to extract a bytes object from a recvfrom() result.

        Supports the typical (bytes, address) tuple, bytes directly, or
        a Mock-like object with `return_value` set to one of the above.
        Returns None if no bytes could be extracted.
        """
        try:
            if isinstance(result, (tuple, list)):
                maybe = result[0]
            elif isinstance(result, (bytes, bytearray)):
                maybe = result
            else:
                maybe = getattr(result, "return_value", None)

            if isinstance(maybe, bytes):
                return maybe
            if isinstance(maybe, bytearray):
                return bytes(maybe)
            return None
        except Exception:
            logger.exception("Error extracting bytes from recvfrom result")
            return None

    def _receive_loop(self) -> None:
        while self.running:
            try:
                if self.receive_socket is None:
                    logger.error("UDP receive socket unavailable")
                    break
                result = self.receive_socket.recvfrom(4096)
                data = self._extract_recvfrom_bytes(result)
                if data is None:
                    # Unexpected return; skip and continue loop
                    continue
                with self._message_lock:
                    self.messages_received += 1
                self._handle_received_message(data)

            except socket.timeout:
                continue
            except Exception:
                if self.running:
                    logger.exception("Error receiving UDP message")

    def _handle_received_message(self, message: bytes) -> None:
        if self._try_handle_json_message(message):
            return
        self._try_handle_protocol_message(message)

    def _try_handle_json_message(self, message: bytes) -> bool:
        try:
            json_str = message.decode("utf-8")
            udp_message = UdpMessage.from_json(json_str)

            if udp_message.message_type == "telemetry":
                with self._message_lock:
                    self.last_telemetry = udp_message.data.copy()

            # Read handler under lock for consistent visibility; avoid holding the lock while invoking the handler to prevent deadlocks.
            with self._message_lock:
                handler = self.message_handlers.get(udp_message.message_type)
            if handler:
                try:
                    handler(udp_message)
                except Exception:
                    logger.exception(
                        "Error in message handler for %s", udp_message.message_type
                    )
            return True
        except Exception:
            return False

    def _try_handle_protocol_message(self, message: bytes) -> bool:
        try:
            decoded, message_id = self._decoder.decode_data(message)
            if not self._decoder.is_from_rover(message_id):
                return False

            telemetry_payload = dict(decoded)
            telemetry_payload["_message_id"] = message_id
            telemetry_payload["_message_name"] = self._decoder.get_message_name(
                message_id
            )

            with self._message_lock:
                self.last_telemetry = telemetry_payload.copy()
                telemetry_handler = self._telemetry_handler

            if telemetry_handler:
                telemetry_handler(telemetry_payload)
            return True
        except Exception:
            logger.exception("Error parsing compact telemetry message")
            return False

    def register_telemetry_handler(
        self, handler: Callable[[Dict[str, Any]], None]
    ) -> None:
        with self._message_lock:
            self._telemetry_handler = handler

    def register_message_handler(
        self, message_type: str, handler: Callable[[UdpMessage], None]
    ):
        with self._message_lock:
            self.message_handlers[message_type] = handler

    def get_statistics(self) -> Dict[str, Any]:
        with self._message_lock:
            last_telemetry_snapshot = self.last_telemetry.copy()
            messages_sent = self.messages_sent
            messages_received = self.messages_received
            running = self.running
        return {
            "messages_sent": messages_sent,
            "messages_received": messages_received,
            "last_telemetry": last_telemetry_snapshot,
            "running": running,
        }

    def send_controller_data(
        self, xbox_values: Dict, n64_values: Dict, reverse_mode: bool = False
    ) -> bool:
        try:
            ts = time.time()
            message = UdpMessage(
                "controller",
                {"xbox": xbox_values, "n64": n64_values, "reverse_mode": reverse_mode},
                timestamp=ts,
            )
            return self._send_message(message.to_json().encode())
        except Exception:
            logger.exception("Failed to send controller data")
            return False

    def send_quit_message(self) -> bool:
        try:
            ts = time.time()
            message = UdpMessage("quit", {}, timestamp=ts)
            return self._send_message(message.to_json().encode())
        except Exception:
            logger.exception("Failed to send quit message")
            return False

    def send_heartbeat(self) -> bool:
        try:
            ts = time.time()
            message = UdpMessage("heartbeat", {}, timestamp=ts)
            return self._send_message(message.to_json().encode())
        except Exception:
            logger.exception("Failed to send heartbeat")
            return False

    def send_package(
        self,
        data: PayloadLike,
        skip_duplicate_check: bool = False,
    ) -> bool:
        self._validate_payload(data)

        try:
            message_bytes = self._convert_to_bytes(data)
            # message_bytes is immutable; use it directly as the deduplication key.
            message_key = message_bytes
            with self._message_lock:
                if (
                    not skip_duplicate_check
                    and self.last_message is not None
                    and message_key == self.last_message
                ):
                    logger.debug("Duplicate message detected and skipped (UDP)")
                    return True

                inflight_entry = self._inflight_messages.get(message_key)
                if inflight_entry is None:
                    event_obj = threading.Event()
                    result_container: dict = {}
                    inflight_entry = (event_obj, result_container)
                    self._inflight_messages[message_key] = inflight_entry
                    do_send = True
                    event_obj_local = event_obj
                    result_container_local = result_container
                else:
                    do_send = False
                    event_obj_local, result_container_local = inflight_entry

            if not do_send:
                event_completed = event_obj_local.wait(
                    timeout=self.inflight_wait_timeout
                )
                if not event_completed:
                    logger.warning(
                        "Timed out waiting for in-flight message after %ss",
                        self.inflight_wait_timeout,
                    )
                    return False
                return result_container_local.get("sent", False)

            sent_result = False
            try:
                sent_result = self._send_message(message_bytes)
                if sent_result:
                    with self._message_lock:
                        self.last_message = message_key
            finally:
                with self._message_lock:
                    curr = self._inflight_messages.get(message_key)
                    # Ensure we only remove the entry we created; don't remove newer entries
                    if curr is not None and curr[0] is event_obj_local:
                        entry = self._inflight_messages.pop(message_key, None)
                        if entry is not None:
                            event_obj, result_container = entry
                            result_container["sent"] = sent_result
                            event_obj.set()
            return sent_result

        except Exception:
            logger.exception("Failed to send compact message")
            return False
