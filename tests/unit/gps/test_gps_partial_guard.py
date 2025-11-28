import importlib
import logging
from types import SimpleNamespace

import pytest


def test_partial_buffer_truncates_and_warns(monkeypatch, caplog):
    # Make MAX_PARTIAL small to force truncation quickly during the test
    monkeypatch.setenv("GPS_MAX_PARTIAL", "100")
    mod = importlib.import_module("utils.gps")

    # Replace real board & busio modules with fakes
    monkeypatch.setattr(mod, "board", SimpleNamespace(SCL=1, SDA=2))

    # Clear any previous test instances
    class FakeI2C:
        instances = []

        def __init__(self, scl, sda, frequency=None, *args, **kwargs):
            FakeI2C.instances.append(self)
            self.read_count = 0
            self.deinit_called = False

        def scan(self):
            # Return one device that matches the GPS address
            return [mod.GPS_I2C_ADDRESS]

        def readfrom_into(self, device, buffer):
            # Fill buffer with data containing no newline characters
            sample = b"$TEST,NONL," * 6  # ~60 bytes
            for i in range(len(buffer)):
                buffer[i] = sample[i % len(sample)]
            self.read_count += 1
            # After many reads, raise an exception to break out of the reader loop
            if self.read_count >= 25:
                raise RuntimeError("stop test")

        def deinit(self):
            self.deinit_called = True

    monkeypatch.setattr(mod, "busio", SimpleNamespace(I2C=FakeI2C))
    # speed up test by no-op'ing sleeps
    monkeypatch.setattr(mod.time, "sleep", lambda _: None)

    caplog.set_level(logging.WARNING)

    # The reader will raise RuntimeError from our FakeI2C to stop; we catch it
    with pytest.raises(RuntimeError):
        mod.run_gps_reader()

    # The warning about truncation should be present
    assert any(
        "GPS partial buffer exceeded" in rec.getMessage() for rec in caplog.records
    )

    # Confirm deinit was called on the FakeI2C instance
    assert FakeI2C.instances and FakeI2C.instances[0].deinit_called is True
