"""
SpaceMouse 3D mouse HID input reader.

Reads 6DOF (x, y, z, rx, ry, rz) translation/rotation data and button
state from a 3Dconnexion SpaceMouse via the HID protocol.  Runs a background
thread that continuously polls the device and exposes the latest state in a
thread-safe manner.

The SpaceMouse is fundamentally different from gamepad controllers (Xbox/N64):
it communicates over HID rather than the ``inputs`` library, so it has its own
dedicated reader instead of going through :class:`InputEventSource`.

Usage::

    sm = SpaceMouse()
    sm.start()          # begins background polling
    ...
    state = sm.get_state()   # {"x": 0, "y": 0, ..., "buttons": 0}
    ...
    sm.stop()           # stops background thread and closes HID device
"""

from __future__ import annotations

import logging
import struct
import threading
import time
from typing import Any, Callable, Dict, Optional

from xbee.config.constants import CONSTANTS

logger = logging.getLogger(__name__)

# HID report IDs emitted by 3Dconnexion devices on Windows
_REPORT_TRANSLATION = 0x01  # translation (or combined 6DOF on some models)
_REPORT_ROTATION = 0x02  # rotation on models that split reports
_REPORT_BUTTONS = 0x03  # button state

# Minimum payload lengths (excluding report ID) for each report type
_MIN_3AXIS_LEN = 7  # 1 byte report ID + 6 bytes (3 × int16)
_MIN_6DOF_LEN = 13  # 1 byte report ID + 12 bytes (6 × int16)
_MIN_BUTTON_LEN = 3  # 1 byte report ID + 2 bytes (uint16 button mask)


class SpaceMouse:
    """HID-based reader for 3Dconnexion SpaceMouse devices.

    Parameters
    ----------
    poll_interval : float
        Seconds to sleep when no HID data is available (default 0.001).
    reconnect_interval : float
        Seconds between reconnection attempts when the device is not
        present (default 2.0).
    """

    def __init__(
        self,
        vendor_id: Optional[int] = None,
        product_id: Optional[int] = None,
        *,
        poll_interval: float = 0.001,
        reconnect_interval: float = 2.0,
        on_disconnect: Optional[Callable[[], None]] = None,
    ) -> None:
        self._vendor_id = vendor_id or CONSTANTS.SPACEMOUSE.VENDOR_ID
        self._product_id = product_id or CONSTANTS.SPACEMOUSE.PRODUCT_ID
        self._poll_interval = poll_interval
        self._reconnect_interval = reconnect_interval
        self._on_disconnect = on_disconnect

        # Thread-safe state
        self._lock = threading.Lock()
        self._state: Dict[str, int] = self._zero_state()
        self._connected = False

        # Background thread
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._dev: Any = None  # hid.device instance
        self._seen_split_rotation_report = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="spacemouse-reader", daemon=True
        )
        self._thread.start()
        logger.info(
            "SpaceMouse reader started (VID=0x%04X, PID=0x%04X)",
            self._vendor_id,
            self._product_id,
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        self._close_device()
        logger.info("SpaceMouse reader stopped")

    def get_state(self) -> Dict[str, int]:
        with self._lock:
            return self._state.copy()

    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    @staticmethod
    def _zero_state() -> Dict[str, int]:
        return {
            CONSTANTS.SPACEMOUSE.AXIS_X: 0,
            CONSTANTS.SPACEMOUSE.AXIS_Y: 0,
            CONSTANTS.SPACEMOUSE.AXIS_Z: 0,
            CONSTANTS.SPACEMOUSE.AXIS_RX: 0,
            CONSTANTS.SPACEMOUSE.AXIS_RY: 0,
            CONSTANTS.SPACEMOUSE.AXIS_RZ: 0,
            CONSTANTS.SPACEMOUSE.BUTTONS: 0,
        }

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main loop: attempt to open device, read continuously, reconnect."""
        while not self._stop_event.is_set():
            if not self._open_device():
                self._stop_event.wait(self._reconnect_interval)
                continue

            self._read_loop()

            # Device lost – close, reset state to zeros, and attempt reconnect
            self._close_device()

    def _read_loop(self) -> None:
        """Read HID reports until the device disconnects or stop is requested."""
        while not self._stop_event.is_set():
            try:
                data = self._dev.read(64)
            except Exception:
                logger.warning("SpaceMouse read error – will attempt reconnect")
                break

            if not data:
                time.sleep(self._poll_interval)
                continue

            self._process_report(data)

    # ------------------------------------------------------------------
    # HID device management
    # ------------------------------------------------------------------

    def _open_device(self) -> bool:
        """Try to open the HID device.  Returns True on success.

        Calls ``hid.enumerate()`` before opening so that the OS device
        list is refreshed.  Without this, hot-plugging a SpaceMouse
        after the basestation has already started may not be detected
        on Windows.
        """
        try:
            import hid  # type: ignore[import-not-found]
        except ImportError:
            logger.warning(
                "hidapi (hid) library not installed – SpaceMouse unavailable. "
                "Install with: pip install hidapi"
            )
            return False

        try:
            # Refresh and inspect the vendor device list.  Different connection
            # modes (USB cable, universal receiver, Bluetooth) can expose
            # different product IDs/interfaces.
            devices = hid.enumerate(self._vendor_id, 0)

            # Prefer configured PID first, then try other likely SpaceMouse
            # interfaces from the same vendor.
            devices.sort(
                key=lambda d: 0
                if int(d.get("product_id", 0)) == int(self._product_id)
                else 1
            )

            for info in devices:
                if not self._is_likely_spacemouse_interface(info):
                    continue
                dev = self._try_open_device_info(hid, info)
                if dev is None:
                    continue
                self._dev = dev
                with self._lock:
                    self._connected = True
                logger.info(
                    "SpaceMouse connected (VID=0x%04X PID=0x%04X usage_page=%s usage=%s)",
                    int(info.get("vendor_id", 0)),
                    int(info.get("product_id", 0)),
                    info.get("usage_page"),
                    info.get("usage"),
                )
                return True

            # Fallback: try exact VID/PID open directly (legacy path).
            dev = hid.device()
            dev.open(self._vendor_id, self._product_id)
            dev.set_nonblocking(True)
            self._dev = dev
            with self._lock:
                self._connected = True
            logger.info(
                "SpaceMouse connected via direct open (VID=0x%04X PID=0x%04X)",
                self._vendor_id,
                self._product_id,
            )
            return True
        except Exception:
            logger.debug(
                "SpaceMouse not found (VID=0x%04X, PID=0x%04X)",
                self._vendor_id,
                self._product_id,
            )
            return False

    def _is_likely_spacemouse_interface(self, info: Dict[str, Any]) -> bool:
        """Heuristic filter for SpaceMouse HID interfaces."""
        pid = int(info.get("product_id", 0) or 0)
        if pid == int(self._product_id):
            return True

        manufacturer = str(info.get("manufacturer_string") or "").lower()
        product = str(info.get("product_string") or "").lower()
        if "3dconnexion" in manufacturer and (
            "spacemouse" in product or "space mouse" in product
        ):
            return True
        if "spacemouse" in product or "space mouse" in product:
            return True

        usage_page = int(info.get("usage_page", 0) or 0)
        usage = int(info.get("usage", 0) or 0)
        # Generic Desktop: Multi-axis controller (0x08) / Joystick (0x04)
        if usage_page == 0x01 and usage in (0x08, 0x04):
            return True

        return False

    def _try_open_device_info(self, hid_module: Any, info: Dict[str, Any]) -> Any | None:
        dev = hid_module.device()
        try:
            path = info.get("path")
            if path:
                dev.open_path(path)
            else:
                dev.open(
                    int(info.get("vendor_id", self._vendor_id) or self._vendor_id),
                    int(info.get("product_id", self._product_id) or self._product_id),
                )
            dev.set_nonblocking(True)
            return dev
        except Exception:
            try:
                dev.close()
            except Exception:
                pass
            return None

    def _close_device(self) -> None:
        was_connected = False
        with self._lock:
            was_connected = self._connected
            self._connected = False
            self._state = self._zero_state()
        if self._dev is not None:
            try:
                self._dev.close()
            except Exception:
                pass
            self._dev = None
        # Notify the app so it can send a final zeros message to the rover
        if was_connected and self._on_disconnect is not None:
            try:
                self._on_disconnect()
            except Exception:
                logger.warning("SpaceMouse on_disconnect callback error", exc_info=True)

    # ------------------------------------------------------------------
    # Report parsing
    # ------------------------------------------------------------------

    def _process_report(self, data: list[int]) -> None:
        if not data:
            return

        report_id = data[0]

        if report_id == _REPORT_ROTATION and len(data) >= _MIN_3AXIS_LEN:
            self._parse_rotation(data)
            self._seen_split_rotation_report = True
        elif report_id == _REPORT_TRANSLATION and len(data) >= _MIN_3AXIS_LEN:
            # Some devices use split reports (0x01 translation, 0x02 rotation)
            # and may still deliver padded 0x01 packets with length >= 13.  Once
            # we've observed split rotation packets, keep parsing 0x01 strictly as
            # translation to avoid clobbering rx/ry/rz with padding bytes.
            if self._seen_split_rotation_report:
                self._parse_translation(data)
            elif len(data) >= _MIN_6DOF_LEN:
                self._parse_6dof(data)
            else:
                self._parse_translation(data)
        elif report_id == _REPORT_BUTTONS and len(data) >= _MIN_BUTTON_LEN:
            self._parse_buttons(data)

    def _parse_translation(self, data: list[int]) -> None:
        """Parse translation-only report: x, y, z (3 × int16)."""
        x, y, z = struct.unpack("<hhh", bytes(data[1:7]))
        with self._lock:
            self._state[CONSTANTS.SPACEMOUSE.AXIS_X] = x
            self._state[CONSTANTS.SPACEMOUSE.AXIS_Y] = -y
            self._state[CONSTANTS.SPACEMOUSE.AXIS_Z] = -z

    def _parse_rotation(self, data: list[int]) -> None:
        """Parse rotation-only report: rx, ry, rz (3 × int16)."""
        rx, ry, rz = struct.unpack("<hhh", bytes(data[1:7]))
        with self._lock:
            self._state[CONSTANTS.SPACEMOUSE.AXIS_RX] = rx
            self._state[CONSTANTS.SPACEMOUSE.AXIS_RY] = ry
            self._state[CONSTANTS.SPACEMOUSE.AXIS_RZ] = -rz

    def _parse_6dof(self, data: list[int]) -> None:
        """Parse a 6DOF combined translation/rotation report.

        Byte layout (little-endian int16 values):
            data[1:3]   = X translation
            data[3:5]   = Y translation
            data[5:7]   = Z translation
            data[7:9]   = RX rotation
            data[9:11]  = RY rotation
            data[11:13] = RZ rotation

        The sign conventions follow the 3Dconnexion Windows driver:
        Y and Z translations and RZ rotation are inverted.
        """
        vals = struct.unpack("<hhhhhh", bytes(data[1:13]))
        with self._lock:
            self._state[CONSTANTS.SPACEMOUSE.AXIS_X] = vals[0]
            self._state[CONSTANTS.SPACEMOUSE.AXIS_Y] = -vals[1]
            self._state[CONSTANTS.SPACEMOUSE.AXIS_Z] = -vals[2]
            self._state[CONSTANTS.SPACEMOUSE.AXIS_RX] = vals[3]
            self._state[CONSTANTS.SPACEMOUSE.AXIS_RY] = vals[4]
            self._state[CONSTANTS.SPACEMOUSE.AXIS_RZ] = -vals[5]

    def _parse_buttons(self, data: list[int]) -> None:
        """Parse a button-state report (uint16 bitmask)."""
        buttons = struct.unpack("<H", bytes(data[1:3]))[0]
        with self._lock:
            self._state[CONSTANTS.SPACEMOUSE.BUTTONS] = buttons
