from __future__ import annotations

import threading
import time

from xbee.controller.state import ControllerState


def test_controller_state_concurrent_read_and_write():
    state = ControllerState()

    # Writer that updates controller state repeatedly
    def writer():
        for i in range(100):
            # Toggle a few different keys to simulate real usage
            state.update_value("xbox", "ly", float(i % 101) / 100.0)
            state.update_value("xbox", "A", i % 2)
            time.sleep(0.001)

    # Reader that continuously takes snapshots of controller values
    errors = []

    def reader():
        try:
            for _ in range(1000):
                vals = state.get_controller_values("xbox")
                assert isinstance(vals, dict)
                time.sleep(0.0005)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer)]
    # Add multiple readers
    threads.extend(threading.Thread(target=reader) for _ in range(4))

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
        assert not t.is_alive()

    assert not errors, f"Reader encountered exceptions: {errors}"
