"""Tests for InputEventSource device hotplug refresh (issue #23)."""

from __future__ import annotations

from unittest.mock import patch

from xbee.controller.input_source import InputEventSource


class _FakeDeviceManager:
    """Stand-in for ``inputs.DeviceManager`` that records construction."""

    construction_count = 0

    def __init__(self):
        type(self).construction_count += 1
        self.gamepads: list = []


def test_sync_devices_refreshes_input_device_manager():
    """_sync_devices must rebuild the inputs DeviceManager so hotplugs appear.

    Without this, the inputs library only enumerates devices at import time
    and any controller plugged in after startup is invisible to the loop.
    """
    source = InputEventSource(enable=False)

    fake_inputs_module = type("FakeInputs", (), {"DeviceManager": _FakeDeviceManager})
    fake_inputs_module.devices = _FakeDeviceManager()
    initial_construction_count = _FakeDeviceManager.construction_count

    with patch("xbee.controller.input_source.inputs", fake_inputs_module):
        with patch("xbee.controller.input_source.INPUTS_AVAILABLE", True):
            source._sync_devices()

    assert _FakeDeviceManager.construction_count > initial_construction_count


def test_refresh_swallows_device_manager_errors():
    """A failure to rebuild DeviceManager must not crash the monitor loop."""
    source = InputEventSource(enable=False)

    class _Boom:
        def __init__(self):
            raise RuntimeError("device manager exploded")

    fake_inputs_module = type("FakeInputs", (), {"DeviceManager": _Boom})
    fake_inputs_module.devices = type("_DummyDevices", (), {"gamepads": []})()

    with patch("xbee.controller.input_source.inputs", fake_inputs_module):
        with patch("xbee.controller.input_source.INPUTS_AVAILABLE", True):
            # Should not raise – the refresh is best-effort
            source._refresh_input_devices()
