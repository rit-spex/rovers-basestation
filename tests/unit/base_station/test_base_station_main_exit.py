import pytest

import xbee.core.base_station as bs


def test_main_re_raises_system_exit(monkeypatch):
    """
    Verify that SystemExit raised by display.run() is propagated out of main()
    (not swallowed), so the application shuts down as expected.
    """

    class DummyDisplay:
        headless = False

        def run(self):
            raise SystemExit("test exit")

        def update_communication_status(self, *args, **kwargs):
            # No-op display method used for tests
            return None

        def update_modes(self, *args, **kwargs):
            pass

    # Patch the display factory to return the dummy
    monkeypatch.setattr(bs, "create_display", lambda: DummyDisplay())

    # Minimal dummy BaseStation to satisfy main() expectations
    class DummyHB:
        @staticmethod
        def get_interval():
            return 1

    class DummyBaseStation:
        frequency = 1
        heartbeat_manager = DummyHB()
        xbee_enabled = False
        creep_mode = False
        reverse_mode = False
        quit = True

        def __init__(self):
            # Minimal initialization; no state to maintain for tests
            return None

        def send_quit_message(self):
            # No-op used during testing
            return None

        def cleanup(self, display):
            # No-op used during testing
            return None

    monkeypatch.setattr(bs, "BaseStation", DummyBaseStation)

    # Avoid the actual control loop running by returning a noop
    monkeypatch.setattr(
        bs, "_create_control_loop", lambda base_station, display: (lambda: None)
    )

    with pytest.raises(SystemExit):
        bs.main()
