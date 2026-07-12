# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : auto_boot.py
# purpose       : wait until the rover XBee answers a ping, then
#                 launch the basestation headless
# created on    : 7/12/2026 - Ryan
# last modified : 7/12/2026 - Ryan
# ------------------------------------------------------------------
"""Boot helper for the Raspberry Pi: block until the rover's XBee is
reachable, then start the basestation. Run by the systemd service."""

import logging
import os
import subprocess
import sys
import time

log = logging.getLogger("auto_boot")

RETRY_SECONDS = 1
MAX_RETRIES = 300  # about 5 minutes


def wait_for_rover() -> bool:
    """Ping the rover XBee until it answers (or we give up)."""
    try:
        from digi.xbee.devices import (RemoteXBeeDevice, XBee64BitAddress,
                                       XBeeDevice, XBeeException)
    except ImportError:
        log.error("digi-xbee not installed")
        return False

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from basestation.protocol import CONSTANTS

    comm = CONSTANTS.COMMUNICATION
    port = os.environ.get("XBEE_PORT", comm.DEFAULT_PORT)
    baud = int(os.environ.get("XBEE_BAUD", comm.DEFAULT_BAUD_RATE))

    log.info("Waiting for rover XBee on %s...", port)
    for _ in range(MAX_RETRIES):
        try:
            device = XBeeDevice(port, baud)
            device.open()
            try:
                remote = RemoteXBeeDevice(
                    device,
                    XBee64BitAddress.from_hex_string(comm.REMOTE_XBEE_ADDRESS))
                device.send_data(remote, "ping")
                log.info("Rover XBee reachable")
                return True
            except XBeeException as exc:
                log.warning("Rover not responding yet: %s", exc)
            finally:
                device.close()
        except Exception as exc:
            log.warning("Connection failed: %s", exc)
        time.sleep(RETRY_SECONDS)
    log.error("Rover unreachable after %d attempts", MAX_RETRIES)
    return False


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s - %(name)s - %(message)s")
    if not wait_for_rover():
        return 1
    env = os.environ.copy()
    env["XBEE_NO_GUI"] = "1"
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return subprocess.run([sys.executable, "-m", "basestation"],
                          cwd=repo_root, env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main())
