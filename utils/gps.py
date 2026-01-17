"""GPS helper module.

This module provides a robust, test-friendly GPS interface that reads
NMEA lines from an I2C-attached GPS device.

The implementation deliberately tolerates the absence of hardware
and of Adafruit's Blinka (`board`/`busio`) by falling back to a
no-op behavior in non-hardware environments.
"""

from __future__ import annotations

import logging
import os
import signal
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

shutdown_event = threading.Event()


def stop_gps_reader() -> None:
    """Request a clean shutdown of the GPS reader loop.

    The reader checks :data:`shutdown_event` and exits the read loop when
    signaled. Tests may set this event to terminate the running thread.
    """
    shutdown_event.set()


try:
    import warnings

    warnings.filterwarnings(
        "ignore",
        category=UserWarning,
        message="pkg_resources is deprecated as an API.*",
    )
    warnings.filterwarnings(
        "ignore",
        category=UserWarning,
        message="pkg_resources package is slated for removal.*",
    )
    import board  # type: ignore
    import busio  # type: ignore
except (ImportError, NotImplementedError):
    board = None  # type: ignore
    busio = None  # type: ignore


try:
    GPS_I2C_ADDRESS = int(os.environ.get("GPS_I2C_ADDRESS", "0x42"), 0)
except ValueError:
    logger.warning("Invalid GPS_I2C_ADDRESS in environment, using default 0x42")
    GPS_I2C_ADDRESS = 0x42


try:
    GPS_MAX_PARTIAL = int(os.environ.get("GPS_MAX_PARTIAL", "1024"))
except ValueError:
    logger.warning("Invalid GPS_MAX_PARTIAL in environment, using default 1024")
    GPS_MAX_PARTIAL = 1024

# Module-level cache for I2C API signature
_i2c_api_signature = None
_i2c_signature_lock = threading.Lock()


def _detect_i2c_signature(i2c) -> str:
    """Detect which readfrom_into signature the I2C library uses.

    Some I2C implementations provide ``readfrom_into(device, buffer)`` while
    others implement ``readfrom_into(buffer)``; detect and return a nominal
    string to allow conditional calls.
    """
    import inspect

    try:
        sig = inspect.signature(i2c.readfrom_into)
        params = list(sig.parameters.keys())
        if len(params) >= 2:
            return "device_buffer"
        else:
            return "buffer_only"
    except Exception:
        return "device_buffer"


def _reset_i2c_signature_cache() -> None:
    """Reset the I2C API signature cache (used by tests)."""
    global _i2c_api_signature
    with _i2c_signature_lock:
        _i2c_api_signature = None


def _init_i2c_bus():
    """Initialize I2C bus using board and busio modules.

    Raises
    ------
    RuntimeError
        If no compatible bus driver is available.
    """
    if board is None or busio is None:
        raise RuntimeError("board/busio not available")
    try:
        return busio.I2C(board.SCL, board.SDA, frequency=100000)
    except Exception as e:  # pragma: no cover - platform error reporting
        msg = f"Failed to initialize I2C bus: {e}"
        logger.exception(msg)
        raise RuntimeError(msg) from e


def _scan_for_gps(i2c, gps_address: int) -> Optional[int]:
    """Scan the I2C bus for a GPS device and return its address.

    Returns
    -------
    Optional[int]
        The 7-bit address of the GPS device or ``None`` if not found.
    """
    try:
        devices = i2c.scan()
    except Exception as e:  # pragma: no cover - hardware error
        msg = f"Failed to scan I2C bus: {e}"
        logger.exception(msg)
        raise RuntimeError(msg) from e

    if len(devices) == 0:
        logger.warning("No I2C devices found")
        return None

    for dev in devices:
        if dev == gps_address:
            return dev
    available = ", ".join(hex(d) for d in devices)
    logger.warning(
        "No GPS device found at expected address %s. Available I2C addresses: %s",
        hex(gps_address),
        available,
    )
    return None


def _read_i2c_data(i2c, device, buffer):
    """Read data using the I2C API, supporting both signature formats."""
    global _i2c_api_signature
    if _i2c_api_signature is None:
        with _i2c_signature_lock:
            if _i2c_api_signature is None:
                _i2c_api_signature = _detect_i2c_signature(i2c)

    if _i2c_api_signature == "buffer_only":
        i2c.readfrom_into(buffer)
    else:
        i2c.readfrom_into(device, buffer)

    return bytes(buffer).rstrip(b"\x00")


def _decode_line(line: bytes) -> Optional[str]:
    """Decode bytes to a text line with safe fallbacks for encoding errors."""
    try:
        return line.decode("ascii").strip()
    except Exception:
        try:
            return line.decode("utf-8", errors="ignore").strip()
        except Exception:
            return None


def _validate_nmea_checksum(text: str) -> bool:
    """Return ``True`` if the provided NMEA text has a valid checksum.

    The function treats messages without an explicit checksum as valid.
    """
    star_idx = text.rfind("*")
    if star_idx == -1 or star_idx + 3 > len(text):
        logger.debug("NMEA (no checksum): %s", text)
        return True

    try:
        cs_field = text[star_idx + 1 : star_idx + 3]
        sent_cs = int(cs_field, 16)
        calc = 0
        for ch in text[1:star_idx]:
            calc ^= ord(ch)

        if calc == sent_cs:
            logger.debug("NMEA (valid): %s", text)
            return True
        else:
            logger.debug("NMEA checksum mismatch: %s", text)
            return False
    except Exception:
        logger.debug("NMEA checksum parse error: %s", text)
        return False


def _process_nmea_line(line: bytes) -> None:
    """Process and validate a single NMEA line."""
    text = _decode_line(line)
    if text is None:
        return

    if not text.startswith("$"):
        logger.debug("Unknown GPS payload (non-NMEA): %s", text)
        return

    _validate_nmea_checksum(text)


def _process_partial_buffer(partial: bytes, max_size: int) -> bytes:
    """Process partial buffer and extract newlines, returning the remaining
    partial buffer.
    """
    if len(partial) > max_size:
        cutoff = len(partial) - max_size
        newline_idx = partial.find(b"\n", cutoff)
        dollar_idx = partial.find(b"$", cutoff)

        if newline_idx != -1 and dollar_idx != -1:
            truncate_at = min(newline_idx, dollar_idx)
        elif newline_idx != -1:
            truncate_at = newline_idx
        elif dollar_idx != -1:
            truncate_at = dollar_idx
        else:
            truncate_at = -1

        if truncate_at > 0:
            partial = partial[truncate_at:]
        else:
            partial = partial[-max_size:]
        logger.warning(
            "GPS partial buffer exceeded %d bytes; truncated to %d bytes",
            max_size,
            len(partial),
        )

    while b"\n" in partial:
        line, partial = partial.split(b"\n", 1)
        line = line.rstrip(b"\r\n \t")
        if line:
            _process_nmea_line(line)

    return partial


def _read_and_parse_nmea(i2c, device):
    """Read raw bytes from the I2C device and parse NMEA lines continuously.

    This routine exits once :data:`shutdown_event` is set or after a number
    of consecutive I/O errors triggered by the device.
    """
    buffer = bytearray(64)
    partial = b""
    consecutive_errors = 0
    max_consecutive_errors = 10

    while not shutdown_event.is_set():
        try:
            new_bytes = _read_i2c_data(i2c, device, buffer)
            if not new_bytes:
                time.sleep(0.1)
                continue

            partial += new_bytes
            partial = _process_partial_buffer(partial, GPS_MAX_PARTIAL)
            consecutive_errors = 0  # Reset on success

            time.sleep(0.5)
        except OSError:
            logger.exception("Error reading from I2C device")
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                logger.error("Too many consecutive I2C errors, stopping GPS reader")
                break
            time.sleep(1)
            continue


def _register_signal_handlers() -> None:
    """Register signal handlers that set :data:`shutdown_event` on shutdown
    signals.
    """

    def _handle_shutdown(signum, frame):
        shutdown_event.set()

    try:
        signal.signal(signal.SIGINT, _handle_shutdown)
    except Exception as e:  # pragma: no cover - platform specific
        logger.debug("Could not register SIGINT handler: %s", e)
    try:
        signal.signal(signal.SIGTERM, _handle_shutdown)
    except Exception as e:  # pragma: no cover - platform specific
        logger.debug("Could not register SIGTERM handler: %s", e)


def cleanup_i2c_bus(i2c) -> None:
    """Cleanup I2C bus resources when finishing the reader loop."""
    if i2c is None:
        return
    try:
        deinit_fn = getattr(i2c, "deinit", None)
        if callable(deinit_fn):
            deinit_fn()
        else:
            close_fn = getattr(i2c, "close", None)
            if callable(close_fn):
                close_fn()
    except Exception:  # pragma: no cover - best-effort cleanup
        logger.exception("Failed to close I2C bus")


def _log_shutdown_status() -> None:
    """Log the final shutdown status.

    This is a lightweight, test-friendly helper called by :func:`run_gps_reader`.
    """
    if shutdown_event.is_set():
        logger.info("GPS reader stopped by user")


def run_gps_reader(gps_address: Optional[int] = None) -> None:
    """Start the GPS reader loop.

    If ``board``/``busio`` cannot be imported, the function logs a warning and
    returns without raising, enabling test and CI environments to import this
    module without needing the hardware drivers.
    """
    if gps_address is None:
        gps_address = GPS_I2C_ADDRESS
    if board is None or busio is None:
        logger.warning(
            "board/busio modules not available. GPS reader requires Adafruit Blinka and board/busio."
        )
        return

    _register_signal_handlers()

    i2c = None
    try:
        i2c = _init_i2c_bus()
        device = _scan_for_gps(i2c, gps_address)
        if device is None:
            return
        logger.info("reading off device %s", hex(device))
        _read_and_parse_nmea(i2c, device)
    finally:
        cleanup_i2c_bus(i2c)
        _log_shutdown_status()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    run_gps_reader()
