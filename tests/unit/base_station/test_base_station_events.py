"""
Tests for BaseStation event dispatching.
"""

from unittest.mock import Mock, patch

from xbee.controller.events import (
    JOYAXISMOTION,
    JOYBUTTONDOWN,
    JOYBUTTONUP,
    JOYDEVICEADDED,
    JOYDEVICEREMOVED,
)


class TestEventDispatching:
    """Test event dispatching methods."""

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_dispatch_hotplug_event_added(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test JOYDEVICEADDED event is dispatched correctly."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.handle_controller_added = Mock()

        event = Mock()
        event.type = JOYDEVICEADDED

        base._dispatch_hotplug_event(event)

        base.controller_manager.handle_controller_added.assert_called_once_with(event)

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_dispatch_hotplug_event_removed(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test JOYDEVICEREMOVED event is dispatched correctly."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.handle_controller_removed = Mock()

        event = Mock()
        event.type = JOYDEVICEREMOVED

        base._dispatch_hotplug_event(event)

        base.controller_manager.handle_controller_removed.assert_called_once_with(event)

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_dispatch_hotplug_falls_back_to_internal_handler(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test fallback to internal handler when controller_manager lacks method."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock(spec=[])  # No methods
        base._handle_controller_hotplug = Mock()

        event = Mock()
        event.type = JOYDEVICEADDED

        base._dispatch_hotplug_event(event)

        base._handle_controller_hotplug.assert_called_once_with(event)

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_dispatch_axis_event(self, mock_controller, mock_heartbeat, mock_comm):
        """Test axis motion event is dispatched correctly."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.handle_axis_motion = Mock()

        event = Mock()

        base._dispatch_axis_event(event)

        base.controller_manager.handle_axis_motion.assert_called_once_with(event)

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_dispatch_axis_falls_back_to_internal_handler(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test fallback to internal handler for axis event."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock(spec=[])
        base._handle_axis_motion = Mock()

        event = Mock()

        base._dispatch_axis_event(event)

        base._handle_axis_motion.assert_called_once_with(event)

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_dispatch_button_down_event(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test button down event is dispatched correctly."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.handle_button_down = Mock()

        event = Mock()
        event.type = JOYBUTTONDOWN

        base._dispatch_button_event(event)

        base.controller_manager.handle_button_down.assert_called_once_with(event)

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_dispatch_button_up_event(self, mock_controller, mock_heartbeat, mock_comm):
        """Test button up event is dispatched correctly."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.handle_button_up = Mock()

        event = Mock()
        event.type = JOYBUTTONUP

        base._dispatch_button_event(event)

        base.controller_manager.handle_button_up.assert_called_once_with(event)

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_dispatch_button_falls_back(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test fallback to internal handler for button event."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock(spec=[])
        base._handle_button_event = Mock()

        event = Mock()
        event.type = JOYBUTTONDOWN

        base._dispatch_button_event(event)

        base._handle_button_event.assert_called_once_with(event)

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_dispatch_joypad_event(self, mock_controller, mock_heartbeat, mock_comm):
        """Test joypad event is dispatched correctly."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.handle_joypad = Mock()

        event = Mock()

        base._dispatch_joypad_event(event)

        base.controller_manager.handle_joypad.assert_called_once_with(event)

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_dispatch_joypad_falls_back(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test fallback to internal handler for joypad event."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock(spec=[])
        base._handle_joypad_motion = Mock()

        event = Mock()

        base._dispatch_joypad_event(event)

        base._handle_joypad_motion.assert_called_once_with(event)


class TestInternalEventHandlers:
    """Test internal event handler methods."""

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_handle_controller_hotplug_quit(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test controller hotplug can trigger quit."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.handle_hotplug_event.return_value = True

        event = Mock()

        with patch("xbee.app.logger"):
            base._handle_controller_hotplug(event)

        assert base.quit is True

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_handle_controller_hotplug_no_quit(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test controller hotplug does not trigger quit."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.handle_hotplug_event.return_value = False

        event = Mock()

        base._handle_controller_hotplug(event)

        assert base.quit is False

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_handle_axis_motion_joystick_axis(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test handling joystick axis motion."""
        from xbee.app import BaseStation
        from xbee.config.constants import CONSTANTS

        base = BaseStation()
        base.input_processor = Mock()

        event = Mock()
        event.axis = CONSTANTS.XBOX.JOYSTICK.AXIS_LX

        base._handle_axis_motion(event)

        base.input_processor.process_joystick_axis.assert_called_once_with(event)

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_handle_axis_motion_trigger_axis(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test handling trigger axis motion."""
        from xbee.app import BaseStation
        from xbee.config.constants import CONSTANTS

        base = BaseStation()
        base.input_processor = Mock()

        event = Mock()
        event.axis = CONSTANTS.XBOX.TRIGGER.AXIS_LT

        base._handle_axis_motion(event)

        base.input_processor.process_trigger_axis.assert_called_once_with(event)

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_handle_button_event_quit(self, mock_controller, mock_heartbeat, mock_comm):
        """Test button event can trigger quit."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.input_processor = Mock()
        base.controller_manager = Mock()
        base.controller_manager.should_quit_on_button.return_value = True

        event = Mock()
        event.instance_id = 0

        with patch("xbee.app.logger"):
            base._handle_button_event(event)

        assert base.quit is True
        base.input_processor.process_button.assert_called_once_with(event)

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_handle_joypad_motion(self, mock_controller, mock_heartbeat, mock_comm):
        """Test handling joypad motion."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.input_processor = Mock()

        event = Mock()

        base._handle_joypad_motion(event)

        base.input_processor.process_joypad.assert_called_once_with(event)


class TestSendCommand:
    """Test send_command method."""

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_send_command_no_joysticks(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test send_command returns early when no joysticks connected."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.has_joysticks.return_value = False

        event = Mock()
        event.type = JOYAXISMOTION

        result = base.send_command(event)

        assert result is None

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_send_command_device_added_no_joysticks(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test send_command processes JOYDEVICEADDED even without joysticks."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.has_joysticks.return_value = False
        base.controller_manager.handle_controller_added = Mock()

        event = Mock()
        event.type = JOYDEVICEADDED

        _ = base.send_command(event)

        base.controller_manager.handle_controller_added.assert_called_once_with(event)

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_send_command_unknown_event_type(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test send_command handles unknown event types."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.has_joysticks.return_value = True

        event = Mock()
        event.type = 9999  # Unknown event type

        result = base.send_command(event)

        assert result is None


class TestControllerDisconnect:
    """Tests for controller disconnection behavior."""

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    def test_disconnect_triggers_quit_with_multiple_controllers(
        self, mock_heartbeat, mock_comm
    ):
        """Test that disconnecting one of multiple controllers triggers base station quit."""
        from xbee.app import BaseStation

        base = BaseStation()

        # Add two joysticks
        event_add1 = Mock()
        event_add1.type = JOYDEVICEADDED
        event_add1.instance_id = 1
        event_add1.name = "Xbox Controller"
        base.send_command(event_add1)

        event_add2 = Mock()
        event_add2.type = JOYDEVICEADDED
        event_add2.instance_id = 2
        event_add2.name = "N64 Controller"
        base.send_command(event_add2)

        assert base.controller_manager.has_joysticks() is True
        assert len(base.controller_manager.joysticks) == 2

        # Initially base.quit should be False
        assert base.quit is False

        # Disconnect one
        event_remove = Mock()
        event_remove.type = JOYDEVICEREMOVED
        event_remove.instance_id = 1

        base.send_command(event_remove)

        # Now base.quit SHOULD be True
        assert (
            base.quit is True
        ), "BaseStation should quit when one of the controllers is disconnected"
        assert len(base.controller_manager.joysticks) == 1
