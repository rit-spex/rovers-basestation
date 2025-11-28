"""
Tests for BaseStation event dispatching.
"""

from unittest.mock import Mock, patch

import pygame


class TestEventDispatching:
    """Test event dispatching methods."""

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_dispatch_hotplug_event_added(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test JOYDEVICEADDED event is dispatched correctly."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.handle_controller_added = Mock()

        event = Mock()
        event.type = pygame.JOYDEVICEADDED

        base._dispatch_hotplug_event(event)

        base.controller_manager.handle_controller_added.assert_called_once_with(event)

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_dispatch_hotplug_event_removed(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test JOYDEVICEREMOVED event is dispatched correctly."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.handle_controller_removed = Mock()

        event = Mock()
        event.type = pygame.JOYDEVICEREMOVED

        base._dispatch_hotplug_event(event)

        base.controller_manager.handle_controller_removed.assert_called_once_with(event)

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_dispatch_hotplug_falls_back_to_internal_handler(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test fallback to internal handler when controller_manager lacks method."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()
        base.controller_manager = Mock(spec=[])  # No methods
        base._handle_controller_hotplug = Mock()

        event = Mock()
        event.type = pygame.JOYDEVICEADDED

        base._dispatch_hotplug_event(event)

        base._handle_controller_hotplug.assert_called_once_with(event)

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_dispatch_axis_event(self, mock_controller, mock_heartbeat, mock_comm):
        """Test axis motion event is dispatched correctly."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.handle_axis_motion = Mock()

        event = Mock()

        base._dispatch_axis_event(event)

        base.controller_manager.handle_axis_motion.assert_called_once_with(event)

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_dispatch_axis_falls_back_to_internal_handler(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test fallback to internal handler for axis event."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()
        base.controller_manager = Mock(spec=[])
        base._handle_axis_motion = Mock()

        event = Mock()

        base._dispatch_axis_event(event)

        base._handle_axis_motion.assert_called_once_with(event)

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_dispatch_button_down_event(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test button down event is dispatched correctly."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.handle_button_down = Mock()

        event = Mock()
        event.type = pygame.JOYBUTTONDOWN

        base._dispatch_button_event(event)

        base.controller_manager.handle_button_down.assert_called_once_with(event)

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_dispatch_button_up_event(self, mock_controller, mock_heartbeat, mock_comm):
        """Test button up event is dispatched correctly."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.handle_button_up = Mock()

        event = Mock()
        event.type = pygame.JOYBUTTONUP

        base._dispatch_button_event(event)

        base.controller_manager.handle_button_up.assert_called_once_with(event)

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_dispatch_button_falls_back(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test fallback to internal handler for button event."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()
        base.controller_manager = Mock(spec=[])
        base._handle_button_event = Mock()

        event = Mock()
        event.type = pygame.JOYBUTTONDOWN

        base._dispatch_button_event(event)

        base._handle_button_event.assert_called_once_with(event)

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_dispatch_joypad_event(self, mock_controller, mock_heartbeat, mock_comm):
        """Test joypad event is dispatched correctly."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.handle_joypad = Mock()

        event = Mock()

        base._dispatch_joypad_event(event)

        base.controller_manager.handle_joypad.assert_called_once_with(event)

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_dispatch_joypad_falls_back(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test fallback to internal handler for joypad event."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()
        base.controller_manager = Mock(spec=[])
        base._handle_joypad_motion = Mock()

        event = Mock()

        base._dispatch_joypad_event(event)

        base._handle_joypad_motion.assert_called_once_with(event)


class TestInternalEventHandlers:
    """Test internal event handler methods."""

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_handle_controller_hotplug_quit(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test controller hotplug can trigger quit."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.handle_hotplug_event.return_value = True

        event = Mock()

        with patch("xbee.core.base_station.logger"):
            base._handle_controller_hotplug(event)

        assert base.quit is True

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_handle_controller_hotplug_no_quit(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test controller hotplug does not trigger quit."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.handle_hotplug_event.return_value = False

        event = Mock()

        base._handle_controller_hotplug(event)

        assert base.quit is False

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_handle_axis_motion_joystick_axis(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test handling joystick axis motion."""
        from xbee.core.base_station import BaseStation
        from xbee.core.command_codes import CONSTANTS

        base = BaseStation()
        base.input_processor = Mock()

        event = Mock()
        event.axis = CONSTANTS.XBOX.JOYSTICK.AXIS_LX

        base._handle_axis_motion(event)

        base.input_processor.process_joystick_axis.assert_called_once_with(event)

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_handle_axis_motion_trigger_axis(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test handling trigger axis motion."""
        from xbee.core.base_station import BaseStation
        from xbee.core.command_codes import CONSTANTS

        base = BaseStation()
        base.input_processor = Mock()

        event = Mock()
        event.axis = CONSTANTS.XBOX.TRIGGER.AXIS_LT

        base._handle_axis_motion(event)

        base.input_processor.process_trigger_axis.assert_called_once_with(event)

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_handle_button_event_quit(self, mock_controller, mock_heartbeat, mock_comm):
        """Test button event can trigger quit."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()
        base.input_processor = Mock()
        base.controller_manager = Mock()
        base.controller_manager.should_quit_on_button.return_value = True

        event = Mock()
        event.instance_id = 0

        with patch("xbee.core.base_station.logger"):
            base._handle_button_event(event)

        assert base.quit is True
        base.input_processor.process_button.assert_called_once_with(event)

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_handle_joypad_motion(self, mock_controller, mock_heartbeat, mock_comm):
        """Test handling joypad motion."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()
        base.input_processor = Mock()

        event = Mock()

        base._handle_joypad_motion(event)

        base.input_processor.process_joypad.assert_called_once_with(event)


class TestSendCommand:
    """Test send_command method."""

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_send_command_no_joysticks(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test send_command returns early when no joysticks connected."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.has_joysticks.return_value = False

        event = Mock()
        event.type = pygame.JOYAXISMOTION

        result = base.send_command(event)

        assert result is None

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_send_command_device_added_no_joysticks(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test send_command processes JOYDEVICEADDED even without joysticks."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.has_joysticks.return_value = False
        base.controller_manager.handle_controller_added = Mock()

        event = Mock()
        event.type = pygame.JOYDEVICEADDED

        _ = base.send_command(event)

        base.controller_manager.handle_controller_added.assert_called_once_with(event)

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_send_command_unknown_event_type(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test send_command handles unknown event types."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.has_joysticks.return_value = True

        event = Mock()
        event.type = 9999  # Unknown event type

        result = base.send_command(event)

        assert result is None
