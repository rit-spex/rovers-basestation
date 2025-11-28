"""
Tests for controller_manager.py focusing on event handling and mode toggling.

Tests cover joystick connect/disconnect, mode flags, and controller state updates.
"""

from unittest.mock import Mock, patch

import pygame

from xbee.core.command_codes import CONSTANTS
from xbee.core.controller_manager import ControllerManager, ControllerState


class TestControllerHotplug:
    """Test controller connection and disconnection events."""

    @patch("xbee.core.controller_manager.logger")
    @patch("xbee.core.controller_manager.pygame.joystick.Joystick")
    def test_controller_added_logged(self, mock_joystick_class, mock_logger):
        """Test controller connection is logged."""
        manager = ControllerManager()

        event = Mock()
        event.type = pygame.JOYDEVICEADDED
        event.device_index = 0

        mock_joy = Mock()
        mock_joy.get_instance_id.return_value = 0
        mock_joy.get_name.return_value = "Xbox Controller"
        mock_joystick_class.return_value = mock_joy

        manager.handle_hotplug_event(event)

        mock_logger.info.assert_called_once()
        assert "connected" in mock_logger.info.call_args[0][0].lower()

    @patch("xbee.core.controller_manager.logger")
    def test_controller_removed_logged(self, mock_logger):
        """Test controller disconnection is logged."""
        manager = ControllerManager()

        event = Mock()
        event.type = pygame.JOYDEVICEREMOVED
        event.instance_id = 0

        manager.handle_hotplug_event(event)

        mock_logger.info.assert_called_once()
        assert "disconnected" in mock_logger.info.call_args[0][0].lower()


class TestModeFlags:
    """Test creep and reverse mode flag updates."""

    @patch("xbee.core.controller_manager.logger")
    def test_creep_mode_toggle_on(self, mock_logger):
        """Test creep mode can be toggled on."""
        manager = ControllerManager()
        manager.creep_mode = False

        # Simulate dpad up + start to toggle creep on (start button ON), using module-level CONSTANTS

        start_key = CONSTANTS.XBOX.BUTTON.START + CONSTANTS.XBOX.BUTTON_INDEX_OFFSET
        manager.controller_state.update_value(
            CONSTANTS.XBOX.NAME, start_key, CONSTANTS.XBOX.BUTTON.ON
        )

        manager.update_mode_flags(joypad_direction=(0, 1), controller_type="xbox")

        # Creep mode should be toggled on
        assert manager.creep_mode is True
        mock_logger.info.assert_called()

    def test_default_creep_mode_is_true(self):
        """Test ControllerManager defaults to creep mode enabled on initialization."""
        manager = ControllerManager()
        assert manager.creep_mode is True


class TestControllerState:
    """Test ControllerState class."""

    def test_controller_state_initialization(self):
        """Test ControllerState initializes with default values."""
        state = ControllerState()

        # Should have xbox and n64 values; use module-level CONSTANTS for keys

        assert CONSTANTS.XBOX.NAME in state.values
        assert CONSTANTS.N64.NAME in state.values

    def test_update_value_axis(self):
        """Test updating an axis value."""
        state = ControllerState()

        # Update left Y axis using module-level CONSTANTS

        state.update_value(CONSTANTS.XBOX.NAME, "ly", 0.5)

        # Value should be updated
        assert "ly" in state.values[CONSTANTS.XBOX.NAME]

    def test_update_value_button(self):
        """Test updating a button value."""
        state = ControllerState()

        # Update A button using module-level CONSTANTS

        state.update_value(CONSTANTS.XBOX.NAME, "A", True)

        # Value should be updated (button press should be encoded as int 1 when True is passed)
        assert state.values[CONSTANTS.XBOX.NAME]["A"] == 1

    def test_get_controller_values(self):
        """Test retrieving controller values."""
        state = ControllerState()
        state.update_value(CONSTANTS.XBOX.NAME, "ly", 0.0)

        values = state.get_controller_values("xbox")

        assert isinstance(values, dict)
        assert "ly" in values


class TestControllerProcessing:
    """Test controller input processing."""

    def test_handle_hotplug_returns_bool(self):
        """Test handle_hotplug_event returns boolean."""
        manager = ControllerManager()

        event = Mock()
        event.type = pygame.JOYDEVICEADDED
        event.device_index = 0

        with patch("xbee.core.controller_manager.pygame.joystick.Joystick"):
            result = manager.handle_hotplug_event(event)

            assert isinstance(result, bool)
