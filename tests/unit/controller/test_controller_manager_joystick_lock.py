from __future__ import annotations

from unittest.mock import Mock

import pygame

from xbee.core.controller_manager import ControllerManager, InputProcessor


def test_joystick_add_remove_and_get_joystick():
    cm = ControllerManager()
    # Create a fake joystick mock
    fake_joy = Mock()
    fake_joy.get_instance_id.return_value = 7
    fake_joy.get_name.return_value = "Xbox Controller"

    # Add using internal method (hotplug would also call this)
    cm._add_joystick(fake_joy)
    assert cm.has_joysticks() is True
    assert cm.get_joystick(7) is fake_joy

    # Remove and check
    cm._remove_joystick_instance(7)
    assert cm.has_joysticks() is False
    assert cm.get_joystick(7) is None


def test_input_processor_handles_missing_joystick():
    cm = ControllerManager()
    ip = InputProcessor(cm)

    # Create an event for a button press referencing a non-existent joystick
    event = Mock()
    event.instance_id = 123
    event.button = 1
    event.type = pygame.JOYBUTTONDOWN

    # Ensure no exception is raised if joystick is missing and that it returns None
    assert ip.process_button(event) is None
