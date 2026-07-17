# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : gps_reader.py
# purpose       : read and log NMEA sentences from the I2C GPS module
# created on    : 7/12/2026 - Ryan
# last modified : 7/12/2026 - Ryan
# ------------------------------------------------------------------
"""Standalone GPS reader: logs NMEA lines from an I2C GPS module.

Requires Adafruit Blinka (board/busio), so it only runs on the Pi:
    pip install Adafruit-Blinka
    python tools/gps_reader.py
"""

import logging
import os
import time

log = logging.getLogger("gps")

GPS_I2C_ADDRESS = int(os.environ.get("GPS_I2C_ADDRESS", "0x42"), 0)
MAX_PARTIAL_BYTES = 1024


def checksum_ok(sentence: str) -> bool:
    """Validate an NMEA checksum; sentences without one pass."""
    star = sentence.rfind("*")
    if star == -1 or star + 3 > len(sentence):
        return True
    try:
        sent = int(sentence[star + 1:star + 3], 16)
    except ValueError:
        return False
    calculated = 0
    for char in sentence[1:star]:
        calculated ^= ord(char)
    return calculated == sent


def run(address: int = GPS_I2C_ADDRESS):
    try:
        import board
        import busio
    except (ImportError, NotImplementedError):
        log.error("board/busio unavailable - install Adafruit-Blinka on the Pi")
        return

    i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
    if address not in i2c.scan():
        log.error("No GPS at %s (found: %s)", hex(address),
                  ", ".join(hex(d) for d in i2c.scan()))
        return

    log.info("Reading GPS at %s", hex(address))
    buffer = bytearray(64)
    partial = b""
    while True:
        i2c.readfrom_into(address, buffer)
        partial += bytes(buffer).rstrip(b"\x00")
        partial = partial[-MAX_PARTIAL_BYTES:]  # cap runaway garbage
        while b"\n" in partial:
            line, partial = partial.split(b"\n", 1)
            text = line.decode("ascii", errors="ignore").strip()
            if text.startswith("$"):
                log.info("%s %s", "ok " if checksum_ok(text) else "BAD", text)
        time.sleep(0.5)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    try:
        run()
    except KeyboardInterrupt:
        pass