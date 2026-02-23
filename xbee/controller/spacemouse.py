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
from typing import Any, Dict, Optional

from xbee.config.constants import CONSTANTS

logger = logging.getLogger(__name__)

# HID report IDs emitted by 3Dconnexion devices on Windows
_REPORT_6DOF = 0x01  # 6DOF combined translation + rotation
_REPORT_BUTTONS = 0x03  # button state

# Minimum payload lengths (excluding report ID) for each report type
_MIN_6DOF_LEN = 13  # 1 byte report ID + 12 bytes (6 × int16)
_MIN_BUTTON_LEN = 3  # 1 byte report ID + 2 bytes (uint16 button mask)


class SpaceMouse:
    """HID-based reader for 3Dconnexion SpaceMouse devices.

    Parameters
    ----------
    vendor_id : int, optional
        USB vendor ID.  Defaults to the value from ``protocol.yaml``.
    product_id : int, optional
        USB product ID.  Defaults to the value from ``protocol.yaml``.
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
    ) -> None:
        self._vendor_id = vendor_id or CONSTANTS.SPACEMOUSE.VENDOR_ID
        self._product_id = product_id or CONSTANTS.SPACEMOUSE.PRODUCT_ID
        self._poll_interval = poll_interval
        self._reconnect_interval = reconnect_interval

        # Thread-safe state
        self._lock = threading.Lock()
        self._state: Dict[str, int] = {
            CONSTANTS.SPACEMOUSE.AXIS_X: 0,
            CONSTANTS.SPACEMOUSE.AXIS_Y: 0,
            CONSTANTS.SPACEMOUSE.AXIS_Z: 0,
            CONSTANTS.SPACEMOUSE.AXIS_RX: 0,
            CONSTANTS.SPACEMOUSE.AXIS_RY: 0,
            CONSTANTS.SPACEMOUSE.AXIS_RZ: 0,
            CONSTANTS.SPACEMOUSE.BUTTONS: 0,
        }
        self._connected = False

        # Background thread
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._dev: Any = None  # hid.device instance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background HID polling thread."""
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
        """Stop the background thread and close the HID device."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        self._close_device()
        logger.info("SpaceMouse reader stopped")

    def get_state(self) -> Dict[str, int]:
        """Return a snapshot of the current 6DOF + button state."""
        with self._lock:
            return self._state.copy()

    def is_connected(self) -> bool:
        """Return whether the HID device is currently open."""
        with self._lock:
            return self._connected

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

            # Device lost – close and attempt reconnect on next iteration
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
        """Try to open the HID device.  Returns True on success."""
        try:
            import hid  # type: ignore[import-not-found]
        except ImportError:
            logger.warning(
                "hidapi (hid) library not installed – SpaceMouse unavailable. "
                "Install with: pip install hidapi"
            )
            return False

        try:
            dev = hid.device()
            dev.open(self._vendor_id, self._product_id)
            dev.set_nonblocking(True)
            self._dev = dev
            with self._lock:
                self._connected = True
            logger.info("SpaceMouse connected")
            return True
        except Exception:
            logger.debug(
                "SpaceMouse not found (VID=0x%04X, PID=0x%04X)",
                self._vendor_id,
                self._product_id,
            )
            return False

    def _close_device(self) -> None:
        """Close the HID device if open."""
        with self._lock:
            self._connected = False
        if self._dev is not None:
            try:
                self._dev.close()
            except Exception:
                pass
            self._dev = None

    # ------------------------------------------------------------------
    # Report parsing
    # ------------------------------------------------------------------

    def _process_report(self, data: list[int]) -> None:
        """Parse a single HID report and update internal state."""
        if not data:
            return

        report_id = data[0]

        if report_id == _REPORT_6DOF and len(data) >= _MIN_6DOF_LEN:
            self._parse_6dof(data)
        elif report_id == _REPORT_BUTTONS and len(data) >= _MIN_BUTTON_LEN:
            self._parse_buttons(data)

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
