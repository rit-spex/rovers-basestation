"""Heartbeat manager.

Sends periodic heartbeat signals with timestamp data so the rover
knows the basestation is still alive.
"""

import time

from xbee.config.constants import CONSTANTS


class HeartbeatManager:
    """Timer-based heartbeat sender.

    Usage:
        hb = HeartbeatManager(comm_manager)
        # In main loop:
        hb.update()  # Sends heartbeat if interval has elapsed
    """

    def __init__(self, communication_manager):
        self._communication_manager = communication_manager
        self._last_heartbeat_time = 0
        self._heartbeat_interval = CONSTANTS.HEARTBEAT.INTERVAL

    def should_send_heartbeat(self) -> bool:
        return (time.time_ns() - self._last_heartbeat_time) >= self._heartbeat_interval

    def send_heartbeat(self) -> bool:
        """Send a heartbeat now (if communication is enabled)."""
        if not self._communication_manager.enabled:
            return False
        success = self._communication_manager.send_heartbeat()
        if success:
            self._last_heartbeat_time = time.time_ns()
        return success

    def update(self) -> bool:
        """Check timer and send heartbeat if due. Returns True if sent."""
        if self.should_send_heartbeat():
            return self.send_heartbeat()
        return False

    def set_interval(self, interval_ns: int):
        self._heartbeat_interval = interval_ns

    def get_interval(self) -> int:
        return self._heartbeat_interval

    def reset_heartbeat(self) -> None:
        """Reset timer so next update() will send immediately."""
        self._last_heartbeat_time = 0
