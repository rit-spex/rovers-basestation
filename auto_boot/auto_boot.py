"""Auto-boot helper for launching the basestation after XBee connectivity checks."""

import logging
import os
import subprocess
import sys
import time
from typing import Any, Optional, Type, cast

CONSTANTS: Any = None
try:
    # Try to import the CONSTANTS config; if import fails, leave as None.
    # This lets runtime logic fall back to defaults while keeping static typing
    # permissive for CI checks.
    from xbee.config.constants import CONSTANTS  # type: ignore
except Exception:
    CONSTANTS = None

# Module-level placeholders so code/tests can patch them at runtime.
XBeeException: Type[BaseException] = Exception


class _XBeeDeviceStub:
    """A minimal, non-operational XBee device implementation used as a
    module-level placeholder. This keeps the attribute callable so tests can
    monkeypatch it, and prevents static analysis from inferring the value is
    always None.
    """

    def __init__(self, *args, **kwargs):
        # Stub for tests/runtime: raises if used; do not perform hardware operations.
        self._args = args
        self._kwargs = kwargs

    def open(self):
        raise XBeeException(_XBEE_LIBS_NOT_AVAILABLE_MSG)

    def send_data(self, *args, **kwargs):
        raise XBeeException(_XBEE_LIBS_NOT_AVAILABLE_MSG)

    def close(self):
        # No-op for stub
        return None


XBeeDevice: Optional[Type] = _XBeeDeviceStub
# Module-level placeholder: tests can monkeypatch XBeeDevice; the stub raises on use.

logger = logging.getLogger(__name__)


def _get_config_value(attr_name: str, default_value: Any) -> Any:
    if CONSTANTS is None:
        return default_value
    communication = getattr(CONSTANTS, "COMMUNICATION", None)
    if communication is None:
        return default_value
    return getattr(communication, attr_name, default_value)


_DEFAULT_PORT = "/dev/ttyUSB0"
_DEFAULT_BAUD_RATE = 9600
_DEFAULT_REMOTE_ADDRESS = "0013A20040ABCDEF"

PORT = os.getenv("XBEE_PORT", _get_config_value("DEFAULT_PORT", _DEFAULT_PORT))
_baud_env = os.getenv(
    "XBEE_BAUD", str(_get_config_value("DEFAULT_BAUD_RATE", _DEFAULT_BAUD_RATE))
)
try:
    BAUD_RATE = int(_baud_env)
except ValueError:
    logger.error(
        "Invalid XBEE_BAUD environment variable '%s', using default", _baud_env
    )
    BAUD_RATE = int(_get_config_value("DEFAULT_BAUD_RATE", _DEFAULT_BAUD_RATE))
RETRY_DELAY = 1
MAX_CONNECTION_RETRIES = 300  # 5 minutes of retries with 1s delay
_DEFAULT_XBEE_SCRIPT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)
XBEE_SCRIPT_DIR = os.getenv("XBEE_SCRIPT_DIR", _DEFAULT_XBEE_SCRIPT_DIR)
XBEE_SCRIPT_NAME = "xbee"

REMOTE_XBEE = os.getenv(
    "XBEE_REMOTE_ADDRESS",
    _get_config_value("REMOTE_XBEE_ADDRESS", _DEFAULT_REMOTE_ADDRESS),
)

# reuse msg string for lib warnings
_XBEE_LIBS_NOT_AVAILABLE_MSG = (
    "Digi XBee libraries are not available - cannot attempt to connect."
)


def wait_for_xbee_connection() -> bool:  # NOSONAR S3516
    # false positive: returns diff vals based on runtime imports
    logger.info("Waiting for Digi XBee to connect to robot...")

    # Prefer using monkeypatched XBeeDevice (tests) or else import runtime Digi XBee classes.
    def _resolve_xbee_classes():
        # Return monkeypatched XBeeDevice if not our internal stub; otherwise import runtime classes.
        _xbee_device = globals().get("XBeeDevice")
        if (
            _xbee_device is not None
            and _xbee_device is not _XBeeDeviceStub
            and callable(_xbee_device)
        ):
            return _xbee_device, globals().get("XBeeException", Exception)
        try:
            # Use CamelCase aliasing for imported classes to satisfy stylistic rules
            from digi.xbee.devices import XBeeDevice as _XBeeDeviceCls
            from digi.xbee.devices import XBeeException as _XBeeExceptionCls

            return _XBeeDeviceCls, _XBeeExceptionCls
        except Exception as e:
            # Preserve the original error as the cause of the ImportError
            raise ImportError(_XBEE_LIBS_NOT_AVAILABLE_MSG) from e

    try:
        xbee_device_cls, xbee_exception_cls = _resolve_xbee_classes()
    except ImportError:
        logger.warning(_XBEE_LIBS_NOT_AVAILABLE_MSG)
        return False

    # Tell type checkers these variables are concrete classes (we'd have
    # already returned if import/resolution failed above).
    xbee_device_cls = cast(Type, xbee_device_cls)
    xbee_exception_cls = cast(Type[BaseException], xbee_exception_cls)

    retry_count = 0
    while retry_count < MAX_CONNECTION_RETRIES:
        retry_count += 1
        try:
            device = xbee_device_cls(PORT, BAUD_RATE)
            device.open()

            try:
                device.send_data(REMOTE_XBEE, "ping")
                logger.info("SUCCESS: Robot XBee reachable! Connection established.")
                return True
            except xbee_exception_cls as e:
                logger.warning("WARNING: Robot XBee not responding yet: %s", e)
                logger.info("Retrying in %d seconds...", RETRY_DELAY)
                time.sleep(RETRY_DELAY)
            finally:
                try:
                    device.close()
                except Exception:
                    pass
        except (xbee_exception_cls, OSError) as e:
            logger.warning("WARNING: Connection failed: %s", e)
            logger.info("Retrying in %d seconds...", RETRY_DELAY)
            time.sleep(RETRY_DELAY)
    logger.error("Failed to connect after %d attempts", MAX_CONNECTION_RETRIES)
    return False


def launch_xbee_script(exit_on_error: bool = False) -> bool:
    expanded_dir = os.path.expanduser(XBEE_SCRIPT_DIR)
    logger.info("Changing directory to: %s", expanded_dir)
    try:
        os.chdir(expanded_dir)
    except OSError as err:
        logger.error("Failed to change directory to '%s': %s", expanded_dir, err)
        if exit_on_error:
            sys.exit(1)
        return False
    logger.info("Launching xbee module...")

    env = os.environ.copy()
    env["XBEE_NO_GUI"] = "1"
    env["XBEE_PORT"] = PORT
    env["XBEE_BAUD"] = str(BAUD_RATE)
    try:
        subprocess.run([sys.executable, "-m", XBEE_SCRIPT_NAME], check=True, env=env)
        return True
    except KeyboardInterrupt:
        raise
    except subprocess.CalledProcessError as exc:
        logger.error("XBee process failed with return code %s", exc.returncode)
        if exit_on_error:
            sys.exit(exc.returncode)
        return False
    except Exception as exc:
        logger.exception("Unexpected error while launching XBee process: %s", exc)
        if exit_on_error:
            sys.exit(1)
        return False


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    if not wait_for_xbee_connection():
        logger.error("Failed to establish XBee connection. Exiting.")
        sys.exit(1)
    launch_xbee_script(exit_on_error=True)
