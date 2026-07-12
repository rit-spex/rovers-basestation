# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : spacemouse.py
# purpose       : read 6DOF motion and buttons from a 3Dconnexion
#                 SpaceMouse over HID
# created on    : 7/12/2026 - Ryan
# last modified : 7/12/2026 - Ryan
# ------------------------------------------------------------------
"""SpaceMouse HID reader.

A background thread opens the device, reads reports, and keeps the latest
state under the protocol signal names (x, y, z, rx, ry, rz, buttons).
Reconnects automatically; calls on_disconnect when the device goes away.

Sign conventions follow the 3Dconnexion Windows driver: y, z, and rz are
inverted. Each axis runs through a small sign filter (the last 5 samples
must agree in sign) to suppress sensor noise around zero.
"""

import logging
import struct
import threading
from collections import deque

from basestation.protocol import CONSTANTS

log = logging.getLogger(__name__)

# HID report ids emitted by 3Dconnexion devices
_REPORT_TRANSLATION = 0x01  # x, y, z (or full 6DOF on some models)
_REPORT_ROTATION = 0x02     # rx, ry, rz on models that split reports
_REPORT_BUTTONS = 0x03      # uint16 button bitmask

_AXES = ("x", "y", "z", "rx", "ry", "rz")
_FILTER_LENGTH = 5  # ponytail: fixed noise-filter window, tune if too laggy
_RECONNECT_SECONDS = 2.0


class SpaceMouse:
    """Background HID reader for the SpaceMouse."""

    def __init__(self, on_disconnect=None):
        self._vendor_id = CONSTANTS.SPACEMOUSE.VENDOR_ID
        self._product_id = CONSTANTS.SPACEMOUSE.PRODUCT_ID
        self._on_disconnect = on_disconnect
        self._lock = threading.Lock()
        self._state = self.zero_state()
        self._connected = False
        self._stop = threading.Event()
        self._thread = None
        self._device = None
        self._seen_split_rotation = False
        self._history = {axis: deque(maxlen=_FILTER_LENGTH) for axis in _AXES}

    @staticmethod
    def zero_state() -> dict:
        return dict.fromkeys(_AXES, 0) | {"buttons": 0}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="spacemouse-reader")
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._on_disconnect = None  # shutting down on purpose, don't re-quit
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        self._close()

    def get_state(self) -> dict:
        with self._lock:
            return dict(self._state)

    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run(self):
        while not self._stop.is_set():
            if not self._open():
                self._stop.wait(_RECONNECT_SECONDS)
                continue
            while not self._stop.is_set():
                try:
                    data = self._device.read(64)
                except Exception:
                    log.warning("SpaceMouse read error - reconnecting")
                    break
                if not data:
                    self._stop.wait(0.001)
                    continue
                self._process_report(data)
            self._close()

    def _open(self) -> bool:
        try:
            import hid
        except ImportError:
            log.warning("hidapi not installed - SpaceMouse disabled")
            self._stop.set()
            return False
        try:
            # Enumerate all 3Dconnexion interfaces; connection mode (cable,
            # receiver, Bluetooth) changes the product id, so prefer the
            # configured one but accept any interface that looks right.
            devices = sorted(
                hid.enumerate(self._vendor_id, 0),
                key=lambda d: d.get("product_id") != self._product_id)
            for info in devices:
                if not self._looks_like_spacemouse(info):
                    continue
                device = hid.device()
                try:
                    device.open_path(info["path"])
                    device.set_nonblocking(True)
                except Exception:
                    continue
                self._device = device
                with self._lock:
                    self._connected = True
                log.info("SpaceMouse connected (PID=0x%04X)",
                         info.get("product_id", 0))
                return True
        except Exception:
            log.debug("SpaceMouse open failed", exc_info=True)
        return False

    def _looks_like_spacemouse(self, info: dict) -> bool:
        if info.get("product_id") == self._product_id:
            return True
        product = str(info.get("product_string") or "").lower()
        if "space" in product:
            return True
        # Generic Desktop page: multi-axis controller (0x08) or joystick (0x04)
        return info.get("usage_page") == 0x01 and info.get("usage") in (0x04, 0x08)

    def _close(self):
        with self._lock:
            was_connected = self._connected
            self._connected = False
            self._state = self.zero_state()
        if self._device is not None:
            try:
                self._device.close()
            except Exception:
                pass
            self._device = None
        if was_connected and self._on_disconnect is not None:
            log.info("SpaceMouse disconnected")
            self._on_disconnect()

    # ------------------------------------------------------------------
    # Report parsing
    # ------------------------------------------------------------------

    def _process_report(self, data):
        report_id, body = data[0], bytes(data[1:])
        if report_id == _REPORT_ROTATION and len(body) >= 6:
            self._seen_split_rotation = True
            self._set_axes(("rx", "ry", "rz"), struct.unpack("<hhh", body[:6]),
                           invert=("rz",))
        elif report_id == _REPORT_TRANSLATION and len(body) >= 6:
            if len(body) >= 12 and not self._seen_split_rotation:
                values = struct.unpack("<hhhhhh", body[:12])
                self._set_axes(_AXES, values, invert=("y", "z", "rz"))
            else:
                self._set_axes(("x", "y", "z"), struct.unpack("<hhh", body[:6]),
                               invert=("y", "z"))
        elif report_id == _REPORT_BUTTONS and len(body) >= 2:
            with self._lock:
                self._state["buttons"] = struct.unpack("<H", body[:2])[0]

    def _set_axes(self, axes, values, invert=()):
        with self._lock:
            for axis, value in zip(axes, values):
                if axis in invert:
                    value = -value
                self._state[axis] = self._filtered(axis, value)

    def _filtered(self, axis, value):
        """Return value only when the last N samples agree in sign."""
        history = self._history[axis]
        history.append(value)
        if len(history) < _FILTER_LENGTH:
            return 0
        if all(v > 0 for v in history) or all(v < 0 for v in history):
            return value
        return 0