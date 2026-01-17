"""
Combined base station tests moved into a subpackage for organization and CI convenience.
"""

from __future__ import annotations

import threading
from unittest.mock import Mock, patch

import pytest

from xbee.core.base_station import (
    BaseStation,
    _create_control_loop,
    _process_controller_events,
    _update_display_data,
)
from xbee.core.input_events import (
    JOYAXISMOTION,
    JOYBUTTONDOWN,
    JOYDEVICEADDED,
    InputEvent,
)


class TestBaseStationInitialization:
    """Test BaseStation initialization."""

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_initialization_default_settings(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test default initialization without custom settings."""
        base = BaseStation()

        assert base.update_loop == 0  # Correct attribute name
        assert base.telemetry_data == {}
        assert mock_comm.called
        assert mock_heartbeat.called
        assert mock_controller.called

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_quit_property_threadsafe(self, mock_controller, mock_heartbeat, mock_comm):
        """Test that the quit property can be set and read safely (thread event)."""
        base = BaseStation()
        # Initially False
        assert base.quit is False
        base.quit = True
        assert base.quit is True
        base.quit = False
        assert base.quit is False

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_creep_mode_enabled_by_default(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """BaseStation should initialize with controller manager in creep mode."""
        mock_controller_instance = Mock()
        mock_controller_instance.creep_mode = True
        mock_controller.return_value = mock_controller_instance

        base = BaseStation()
        assert base.controller_manager.creep_mode is True

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_initialization_custom_log_summary(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test initialization with custom log summary interval."""
        base = BaseStation(log_summary_every=100)

        assert base.log_summary_every == 100

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.os.getenv")
    def test_initialization_uses_env_xbee_simulation(self, mock_getenv, mock_comm):
        """Test that initialization respects XBEE_SIMULATION env var."""
        mock_getenv.return_value = "1"

        with (
            patch("xbee.core.base_station.HeartbeatManager"),
            patch("xbee.core.base_station.ControllerManager"),
        ):
            BaseStation()  # Just verify it doesn't crash

        mock_comm.assert_called_once()


class TestEnvironmentVariableParsing:
    """Test environment variable parsing logic."""

    @patch("xbee.core.base_station.os.environ.get")
    def test_basestation_log_every_updates_valid(self, mock_get):
        """Test parsing valid BASESTATION_LOG_EVERY_UPDATES value."""
        from xbee.core.base_station import _get_log_every_updates_default

        mock_get.return_value = "50"
        assert _get_log_every_updates_default() == 50

    @patch("xbee.core.base_station.os.environ.get")
    @patch("xbee.core.base_station.logger")
    def test_basestation_log_every_updates_invalid(self, mock_logger, mock_get):
        """Test parsing invalid BASESTATION_LOG_EVERY_UPDATES value logs warning."""
        from xbee.core.base_station import _get_log_every_updates_default

        mock_get.return_value = "invalid"
        assert _get_log_every_updates_default() == 0
        mock_logger.warning.assert_called_once()


class TestTelemetryHandling:
    """Test telemetry data handling."""

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_handle_telemetry_data(self, mock_controller, mock_heartbeat, mock_comm):
        """Test telemetry data is stored correctly."""
        base = BaseStation()

        telemetry = {"battery_voltage": 12.6, "temperature": 25.0}
        base._handle_telemetry_data(telemetry)
        assert base.telemetry_data["battery_voltage"] == pytest.approx(
            telemetry["battery_voltage"]
        )
        assert base.telemetry_data["temperature"] == pytest.approx(
            telemetry["temperature"]
        )

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_get_telemetry_data(self, mock_controller, mock_heartbeat, mock_comm):
        """Test retrieving telemetry data."""
        base = BaseStation()
        base.telemetry_data = {"battery_voltage": 12.6}

        result = base.get_telemetry_data()
        assert result["battery_voltage"] == pytest.approx(12.6)


class TestControllerEventProcessing:
    """Test controller event processing."""

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_send_command_axis_motion(self, mock_controller, mock_heartbeat, mock_comm):
        """Test axis motion event is processed."""
        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.joysticks = {0: Mock()}

        base.input_processor = Mock()

        event = Mock()
        event.type = JOYAXISMOTION

        # Mock constants
        from xbee.core.command_codes import CONSTANTS

        event.axis = CONSTANTS.XBOX.JOYSTICK.AXIS_LX  # LX

        base.send_command(event)
        base.controller_manager.handle_axis_motion.assert_called_once_with(event)

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_send_command_button_down(self, mock_controller, mock_heartbeat, mock_comm):
        """Test button down event is processed."""
        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.joysticks = {0: Mock()}

        base.input_processor = Mock()

        event = Mock()
        event.type = JOYBUTTONDOWN

        base.send_command(event)
        base.controller_manager.handle_button_down.assert_called_once_with(event)

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_send_command_controller_added(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test controller connection event is processed."""
        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.joysticks = {}

        # Controller hotplug is handled by _handle_controller_hotplug which calls controller_manager

        event = Mock()
        event.type = JOYDEVICEADDED

        base.send_command(event)
        base.controller_manager.handle_controller_added.assert_called_once_with(event)


class TestUpdateInfo:
    """Test update_info method and controller data sending."""

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_update_info_sends_heartbeat(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test update_info sends heartbeat when needed."""
        base = BaseStation()
        base.heartbeat_manager = Mock()
        base.heartbeat_manager.should_send_heartbeat.return_value = True
        base.controller_manager = Mock()
        base.controller_manager.get_current_controller_data.return_value = {}

        base.update_info()

        base.update_info()

        base.update_info()

        # Should be called 3 times now
        assert base.heartbeat_manager.update.call_count == 3

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    @patch("xbee.core.base_station.logger")
    def test_update_info_logs_at_summary_interval(
        self, mock_logger, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test update_info logs summary at configured interval."""
        base = BaseStation(log_summary_every=10)
        base.heartbeat_manager = Mock()
        base.heartbeat_manager.should_send_heartbeat.return_value = False
        base.controller_manager = Mock()
        base.controller_manager.get_current_controller_data.return_value = {}

        # Call 10 times to trigger summary log
        for _ in range(10):
            base.update_info()

        # Should have INFO level log
        assert any(
            "Heartbeat sent" in call[0][0] or "Controller data sent" in call[0][0]
            for call in mock_logger.info.call_args_list
        )


class TestCleanup:
    """Test cleanup and resource management."""

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_cleanup_closes_communication(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test cleanup closes communication manager."""
        base = BaseStation()
        base.communication_manager = Mock()
        base.controller_manager = Mock()

        base.cleanup(None)

        base.communication_manager.cleanup.assert_called_once()


class TestModeProperties:
    """Test creep and reverse mode properties."""

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_creep_mode_property(self, mock_controller, mock_heartbeat, mock_comm):
        """Test creep mode property returns controller manager state."""
        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.creep_mode = True

        assert base.creep_mode is True

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_reverse_mode_property(self, mock_controller, mock_heartbeat, mock_comm):
        """Test reverse mode property returns controller manager state."""
        base = BaseStation()
        base.controller_manager = Mock()
        base.controller_manager.reverse_mode = False

        assert base.reverse_mode is False


class TestHelperFunctions:
    """Test module-level helper functions."""

    def test_process_controller_events(self):
        """Test controller event processing helper."""
        mock_base = Mock()
        mock_base.input_source = Mock()
        mock_display = Mock()

        mock_event = InputEvent(type=JOYAXISMOTION)
        mock_base.input_source.poll_events.return_value = [mock_event]

        _process_controller_events(mock_base, mock_display)

        mock_base.send_command.assert_called_once_with(mock_event)

    def test_update_display_data(self):
        """Test display data update helper."""
        mock_base = Mock()
        mock_base.get_telemetry_data.return_value = {"battery": 12.6}
        mock_base.creep_mode = False
        mock_base.reverse_mode = False
        mock_base.controller_manager.get_current_controller_data.return_value = {}
        mock_display = Mock()

        _update_display_data(mock_base, mock_display, 1)

        mock_display.update_telemetry.assert_called_once()
        mock_display.update_modes.assert_called_once()


def test_control_loop_exits_and_cleanup_called():
    # Patch CommunicationManager and HeartbeatManager to avoid external calls
    with (
        patch("xbee.core.base_station.CommunicationManager"),
        patch("xbee.core.base_station.HeartbeatManager"),
        patch("xbee.core.base_station.ControllerManager"),
    ):
        # Create base station and replace the communication manager with a mock
        base = BaseStation()
        base.communication_manager = Mock()
        base.input_source = Mock()
        base.input_source.poll_events.return_value = []
        base.send_quit_message = Mock()
        base.cleanup = Mock()
        display = Mock()

        control_loop = _create_control_loop(base, display)
        thread = threading.Thread(target=control_loop, daemon=True)
        # Use an event to reliably wait for the control loop to begin executing
        loop_started = threading.Event()
        original_update_info = base.update_info

        def update_info_with_signal():
            # Signal that the loop has started and then run the actual update
            loop_started.set()
            return original_update_info()

        base.update_info = update_info_with_signal
        thread.start()

        # Wait for loop to actually start (with timeout)
        assert loop_started.wait(timeout=1), "Control loop did not start"

        # Request shutdown
        base.quit = True

        # Wait for control loop to finish
        thread.join(timeout=1)
        assert not thread.is_alive()
        # Ensure cleanup functions were called
        base.send_quit_message.assert_called()
        base.cleanup.assert_called_once()
