# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : comms.py
# purpose       : send protocol messages to the rover and receive
#                 telemetry, over XBee radio or UDP simulation
# created on    : 7/12/2026 - Ryan
# last modified : 7/14/2026 - Ryan
# ------------------------------------------------------------------
"""Rover link.

Uses the XBee radio when the digi-xbee library and serial port are
available; otherwise falls back to UDP loopback, which is what the
rovers-ros xbee_udp node listens on. Telemetry comes back on the XBee
data callback (radio) or the UDP telemetry port (simulation).
"""

import logging
import os
import socket
import threading

from basestation.protocol import CONSTANTS, MSG, MessageEncoder, env_flag

log = logging.getLogger(__name__)

COMM = CONSTANTS.COMMUNICATION
QUIT_SEND_ATTEMPTS = 3


class Link:
    """Encodes and transmits messages; decodes incoming telemetry.

    Consecutive duplicate payloads are suppressed per message id to keep
    radio traffic down. Pass force=True to always transmit (heartbeats).
    """

    def __init__(self, on_telemetry=None, connect: bool = True):
        self.encoder = MessageEncoder()
        self._on_telemetry = on_telemetry
        self._last = {}  # message id -> last transmitted payload
        self._stop = threading.Event()
        self._xbee = None
        self._remote = None
        self._udp = None
        self._rx = None

        self.simulation = True
        if connect:
            self.simulation = not self._open_xbee()
            if self.simulation:
                # this is for headless so a dead radio shouldnt degrade
                # into loopback simulation that nobody can see (systemd
                # will probs restart this until the XBee comes back)
                sim_requested = (env_flag("BASESTATION_SIMULATION")
                                 or CONSTANTS.SIMULATION_MODE)
                if env_flag("XBEE_NO_GUI") and not sim_requested:
                    raise SystemExit(
                        "XBee unavailable while headless - refusing UDP "
                        "simulation fallback (set BASESTATION_SIMULATION=1 "
                        "to simulate on purpose)")
                self._open_udp()
        # Tracing is always on in simulation - verifying comms is the point.
        self.trace = env_flag("ROVER_PROTOCOL_TRACE", default=self.simulation)

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    def send(self, message_id: int, values: dict, force: bool = False) -> bool:
        """Encode and transmit one message. Returns True if handled."""
        payload = self.encoder.encode_data(values, message_id)
        if not force and self._last.get(message_id) == payload:
            return True  # duplicate suppressed
        if self.trace:
            log.info("[protocol tx] %s %s bytes=%s",
                     self.encoder.get_message_name(message_id), values,
                     payload.hex(" "))
        if not self._transmit(payload):
            return False
        self._last[message_id] = payload
        return True

    def send_quit(self):
        """Tell the rover to stop. Retried because it is the critical one."""
        payload = self.encoder.encode_data({}, MSG.QUIT_ID)
        for _ in range(QUIT_SEND_ATTEMPTS):
            if self._transmit(payload):
                log.info("Quit message sent")
                return
        log.error("Failed to send quit message")

    def _transmit(self, payload: bytes) -> bool:
        try:
            if self._udp is not None:
                self._udp.sendto(payload, (COMM.UDP_HOST, COMM.UDP_ROVER_PORT))
            elif self._xbee is not None:
                self._xbee.send_data(self._remote, payload)
            else:
                return False
            return True
        except Exception:
            log.exception("Transmit failed")
            return False

    # ------------------------------------------------------------------
    # Receiving
    # ------------------------------------------------------------------

    def _handle_telemetry(self, data: bytes):
        try:
            decoded, message_id = self.encoder.decode_data(data)
        except Exception:
            log.debug("Undecodable packet: %s", data.hex(" "))
            return
        if not self.encoder.is_from_rover(message_id):
            return
        name = self.encoder.get_message_name(message_id)
        if self.trace:
            log.info("[protocol rx] %s %s bytes=%s", name, decoded, data.hex(" "))
        decoded["_message_name"] = name
        if self._on_telemetry:
            try:
                self._on_telemetry(decoded)
            except Exception:
                log.exception("Telemetry handler error")

    def _receive_loop(self):
        while not self._stop.is_set():
            try:
                data, _ = self._rx.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                return  # socket closed during shutdown
            self._handle_telemetry(data)

    # ------------------------------------------------------------------
    # Backends
    # ------------------------------------------------------------------

    def _open_xbee(self) -> bool:
        """Try the XBee radio; False means fall back to UDP simulation."""
        if env_flag("BASESTATION_SIMULATION") or CONSTANTS.SIMULATION_MODE:
            log.info("Simulation mode requested - using UDP")
            return False
        try:
            from digi.xbee.devices import (RemoteXBeeDevice, XBee64BitAddress,
                                           XBeeDevice)
        except ImportError:
            log.info("digi-xbee not installed - using UDP simulation")
            return False

        port = os.environ.get("XBEE_PORT") or (
            COMM.DEFAULT_PORT_WINDOWS if os.name == "nt" else COMM.DEFAULT_PORT)
        baud = int(os.environ.get("XBEE_BAUD") or COMM.DEFAULT_BAUD_RATE)
        if port.startswith("/dev/") and not os.path.exists(port):
            log.info("XBee port %s not present - using UDP simulation", port)
            return False
        try:
            self._xbee = XBeeDevice(port, baud)
            self._xbee.open()
            self._remote = RemoteXBeeDevice(
                self._xbee,
                XBee64BitAddress.from_hex_string(COMM.REMOTE_XBEE_ADDRESS))
            self._xbee.add_data_received_callback(
                lambda message: self._handle_telemetry(bytes(message.data)))
            log.info("XBee open on %s @ %d baud", port, baud)
            return True
        except Exception as exc:
            log.warning("XBee init failed (%s) - using UDP simulation", exc)
            if self._xbee is not None:
                try:
                    self._xbee.close()
                except Exception:
                    pass
                self._xbee = None
            return False

    def _open_udp(self):
        self._udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._rx.bind((COMM.UDP_HOST, COMM.UDP_TELEMETRY_PORT))
        self._rx.settimeout(1.0)
        threading.Thread(target=self._receive_loop, daemon=True,
                         name="telemetry-rx").start()
        log.info("UDP simulation: commands to %s:%d, telemetry on :%d",
                 COMM.UDP_HOST, COMM.UDP_ROVER_PORT, COMM.UDP_TELEMETRY_PORT)

    def close(self):
        self._stop.set()
        for sock in (self._udp, self._rx):
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
        if self._xbee is not None:
            try:
                self._xbee.close()
                log.info("XBee closed")
            except Exception:
                log.exception("Error closing XBee")