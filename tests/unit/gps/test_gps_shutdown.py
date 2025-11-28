import importlib
import logging
import threading
import time
from types import SimpleNamespace


def test_run_gps_reader_shutdown(monkeypatch, caplog):
    mod = importlib.import_module("utils.gps")

    class FakeI2C:
        instances = []

        def __init__(self, scl, sda, frequency=None, *args, **kwargs):
            FakeI2C.instances.append(self)
            self._running = True
            self.deinit_called = False
            self.read_count = 0

        def scan(self):
            return [mod.GPS_I2C_ADDRESS]

        def readfrom_into(self, device, buffer):
            # Fill buffer with a valid NMEA line so the parser will be happy
            sample = b"$TEST,DATA*00\n"
            for i in range(len(buffer)):
                buffer[i] = sample[i % len(sample)]
            self.read_count += 1

        def deinit(self):
            self.deinit_called = True

    # Clear any previous test instances
    FakeI2C.instances.clear()

    monkeypatch.setattr(mod, "board", SimpleNamespace(SCL=1, SDA=2))
    monkeypatch.setattr(mod, "busio", SimpleNamespace(I2C=FakeI2C))
    # speed up test by no-op sleeps
    monkeypatch.setattr(mod.time, "sleep", lambda _: None)

    caplog.set_level(logging.INFO)

    # ensure shutdown flag is clear
    mod.shutdown_event.clear()

    # Run the GPS reader in a thread and request shutdown
    t = threading.Thread(
        target=mod.run_gps_reader, kwargs={"gps_address": None}, daemon=True
    )
    t.start()

    # Wait a small time to let it run a bit
    time.sleep(0.05)

    # Request a clean shutdown
    mod.stop_gps_reader()

    # Wait for thread to finish
    t.join(timeout=1)
    assert not t.is_alive(), "GPS reader thread did not stop"

    assert FakeI2C.instances and FakeI2C.instances[0].deinit_called is True
    assert any(
        "GPS reader stopped by user" in rec.getMessage() for rec in caplog.records
    )
