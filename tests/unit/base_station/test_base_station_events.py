"""
Tests for BaseStation event dispatching via send_command().

All tests exercise the real production entry point (send_command) instead of
now-removed _dispatch_* helper methods.
"""

from unittest.mock import Mock, patch

from xbee.controller.events import (
    JOYAXISMOTION,
    JOYBUTTONDOWN,
    JOYBUTTONUP,
    JOYDEVICEADDED,
    JOYDEVICEREMOVED,
    JOYHATMOTION,
)


class TestSendCommandDispatching:
    """Test that send_command routes each event type to the correct handler."""

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_send_command_routes_device_added(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test JOYDEVICEADDED event is routed to handle_controller_added."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.has_joysticks.return_value = False
        base.controller_manager.handle_controller_added.return_value = False

        event = Mock()
        event.type = JOYDEVICEADDED

        base.send_command(event)

        base.controller_manager.handle_controller_added.assert_called_once_with(event)

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_send_command_routes_device_removed(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test JOYDEVICEREMOVED event is routed to handle_controller_removed."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.has_joysticks.return_value = False
        base.controller_manager.handle_controller_removed.return_value = False

        event = Mock()
        event.type = JOYDEVICEREMOVED

        base.send_command(event)

        base.controller_manager.handle_controller_removed.assert_called_once_with(event)

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_send_command_device_added_triggers_quit(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test JOYDEVICEADDED sets quit when handler returns True."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.has_joysticks.return_value = False
        base.controller_manager.handle_controller_added.return_value = True

        event = Mock()
        event.type = JOYDEVICEADDED

        base.send_command(event)

        assert base.quit is True

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_send_command_device_removed_triggers_quit(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test JOYDEVICEREMOVED sets quit when handler returns True."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.has_joysticks.return_value = False
        base.controller_manager.handle_controller_removed.return_value = True

        event = Mock()
        event.type = JOYDEVICEREMOVED

        base.send_command(event)

        assert base.quit is True

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_send_command_routes_axis_motion(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test JOYAXISMOTION event is routed to handle_axis_motion."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.has_joysticks.return_value = True

        event = Mock()
        event.type = JOYAXISMOTION

        base.send_command(event)

        base.controller_manager.handle_axis_motion.assert_called_once_with(event)

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_send_command_routes_button_down(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test JOYBUTTONDOWN event is routed to handle_button_down."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.has_joysticks.return_value = True

        event = Mock()
        event.type = JOYBUTTONDOWN

        base.send_command(event)

        base.controller_manager.handle_button_down.assert_called_once_with(event)

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_send_command_routes_button_up(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test JOYBUTTONUP event is routed to handle_button_up."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.has_joysticks.return_value = True

        event = Mock()
        event.type = JOYBUTTONUP

        base.send_command(event)

        base.controller_manager.handle_button_up.assert_called_once_with(event)

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    @patch("xbee.app.ControllerManager")
    def test_send_command_routes_joyhat(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test JOYHATMOTION event is routed to handle_joypad."""
        from xbee.app import BaseStation

        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.has_joysticks.return_value = True

        event = Mock()
        event.type = JOYHATMOTION

        base.send_command(event)

        base.controller_manager.handle_joypad.assert_called_once_with(event)


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


class TestPeripheralDisconnectTriggersQuit:
    """Keyboard and SpaceMouse disconnects should trigger quit (e-stop)."""

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    def test_keyboard_disconnect_triggers_quit(self, mock_heartbeat, mock_comm):
        """Keyboard on_disconnect callback should set base.quit = True."""
        from xbee.app import BaseStation

        base = BaseStation()
        assert base.quit is False

        # Simulate keyboard disconnect callback
        base._on_keyboard_disconnect()

        assert base.quit is True, (
            "BaseStation should quit when keyboard disconnects"
        )
        assert base._keyboard_disconnect_pending.is_set()

    @patch("xbee.app.CommunicationManager")
    @patch("xbee.app.HeartbeatManager")
    def test_spacemouse_disconnect_triggers_quit(self, mock_heartbeat, mock_comm):
        """SpaceMouse on_disconnect callback should set base.quit = True."""
        from xbee.app import BaseStation

        base = BaseStation()
        assert base.quit is False

        # Simulate SpaceMouse disconnect callback
        base._on_spacemouse_disconnect()

        assert base.quit is True, (
            "BaseStation should quit when SpaceMouse disconnects"
        )
        assert base._spacemouse_disconnect_pending.is_set()
