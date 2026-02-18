from __future__ import annotations

from unittest.mock import Mock

from xbee.controller.manager import ControllerManager, InputProcessor
from xbee.controller.events import JOYBUTTONDOWN


def test_joystick_add_remove_and_get_joystick():
    cm = ControllerManager()
    # Add using internal method (hotplug would also call this)
    cm._add_device(7, "Xbox Controller", "guid-7")
    assert cm.has_joysticks() is True
    device = cm.get_joystick(7)
    assert isinstance(device, dict)
    assert device.get("name") == "Xbox Controller"

    # Remove and check
    cm._remove_device(7)
    assert cm.has_joysticks() is False
    assert cm.get_joystick(7) is None


def test_input_processor_handles_missing_joystick():
    cm = ControllerManager()
    ip = InputProcessor(cm)

    # Create an event for a button press referencing a non-existent joystick
    event = Mock()
    event.instance_id = 123
    event.button = 1
    event.type = JOYBUTTONDOWN

    # Ensure no exception is raised if joystick is missing and that it returns None
    assert ip.process_button(event) is None
