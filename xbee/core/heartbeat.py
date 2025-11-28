"""
Heartbeat module for XBee comms.
Sends periodic signals with timestamp data for ROS comms verification.
"""

import logging
import time

from .command_codes import CONSTANTS
from .communication import CommunicationManager

logger = logging.getLogger(__name__)


class HeartbeatManager:
    """
    Manages heartbeat signals for XBee comms.
    """

    def __init__(self, communication_manager: CommunicationManager):
        """
        Init heartbeat manager.

        Args:
            communication_manager: CommunicationManager instance for handling XBee comms
        """
        self._communication_manager = communication_manager
        self._last_heartbeat_time = 0
        self._heartbeat_interval = CONSTANTS.HEARTBEAT.INTERVAL

    def should_send_heartbeat(self) -> bool:
        """
        Checks if it's time to send a heartbeat signal.

        Returns:
            bool: True if heartbeat should be sent, False otherwise
        """
        current_time = (
            time.time_ns()
        )  # Nanosecond precision required for accurate interval timing
        return (current_time - self._last_heartbeat_time) >= self._heartbeat_interval

    def send_heartbeat(self) -> bool:
        """
        Sends a heartbeat message if XBee comms is available.

        Returns:
            bool: True if heartbeat sent successfully, False otherwise
        """
        if not self._communication_manager.enabled:
            return False

        success = self._communication_manager.send_heartbeat()

        if success:
            self._last_heartbeat_time = time.time_ns()

        return success

    def update(self) -> bool:
        """
        Update heartbeat - check if it's time to send and send if needed.

        Returns:
            bool: True if heartbeat was sent successfully, False otherwise
        """
        if self.should_send_heartbeat():
            return self.send_heartbeat()
        return False

    def set_interval(self, interval_ns: int):
        """
        Sets the heartbeat interval.

        Args:
            interval_ns: Interval in nanoseconds between heartbeats
        """
        self._heartbeat_interval = interval_ns

    def get_interval(self) -> int:
        """
        Gets the current heartbeat interval.

        Returns:
            int: Heartbeat interval in nanoseconds
        """
        return self._heartbeat_interval

    def reset_heartbeat(self) -> None:
        """
        Reset the last heartbeat time (useful for tests and manual resets).

        After calling this, the manager will consider a heartbeat due immediately
        (i.e., should_send_heartbeat() will return True until a heartbeat is sent).
        """
        self._last_heartbeat_time = 0


if __name__ == "__main__":
    import logging as _logging

    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Example usage of HeartbeatManager for manual testing; not a test.
    class _FakeComm:
        def __init__(self):
            self.enabled = True

        def send_heartbeat(self):
            return True

    comm_manager = _FakeComm()
    # Type-ignore for demo purposes - the fake comm is compatible with the interface
    mgr = HeartbeatManager(comm_manager)  # type: ignore[arg-type]
    mgr.set_interval(CONSTANTS.CONVERSION.ONE_HUNDRED_MS_TO_NS)
    logger.info("HeartbeatManager demo run: sending a single heartbeat")
    mgr.send_heartbeat()
    logger.info("Demo complete")
