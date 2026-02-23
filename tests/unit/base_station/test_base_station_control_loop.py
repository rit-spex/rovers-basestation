"""
Tests for BaseStation control loop and helper functions.
"""

import time
from unittest.mock import Mock, patch

from xbee.app import (
    _cleanup_on_exit,
    _handle_fatal_error,
    _handle_fatal_loop_error,
    _handle_recoverable_error,
    _handle_shutdown_signal,
    _process_controller_events,
    _process_single_iteration,
    _run_update_cycle,
    _should_run_update,
    _update_display_data,
)
from xbee.controller.events import JOYDEVICEADDED, QUIT, InputEvent
from xbee.controller.input_source import InputSourceError


class TestControlLoopHelpers:
    """Test control loop helper functions."""

    def test_should_run_update_true(self):
        """Test should_run_update returns True when enough time has passed."""
        current_time = 1000
        timer = 0
        frequency = 100

        assert _should_run_update(current_time, timer, frequency) is True

    def test_should_run_update_false(self):
        """Test should_run_update returns False when not enough time has passed."""
        current_time = 50
        timer = 0
        frequency = 100

        assert _should_run_update(current_time, timer, frequency) is False


class TestErrorHandlers:
    """Test error handling functions."""

    @patch("xbee.app.logger")
    @patch("time.sleep")
    def test_handle_recoverable_error(self, mock_sleep, mock_logger):
        """Test recoverable error handler logs warning and sleeps."""
        exc = OSError("Connection lost")

        _handle_recoverable_error(exc)

        mock_logger.warning.assert_called_once()
        mock_sleep.assert_called_once_with(0.1)

    @patch("xbee.app.logger")
    def test_handle_fatal_error(self, mock_logger):
        """Test fatal error handler logs and sets quit."""
        mock_base = Mock()

        _handle_fatal_error(mock_base)

        mock_logger.exception.assert_called_once()
        assert mock_base.quit is True

    @patch("xbee.app.logger")
    def test_handle_shutdown_signal(self, mock_logger):
        """Test shutdown signal handler logs and sets quit."""
        mock_base = Mock()

        _handle_shutdown_signal(mock_base)

        mock_logger.info.assert_called_once()
        assert mock_base.quit is True

    @patch("xbee.app.logger")
    def test_handle_fatal_loop_error(self, mock_logger):
        """Test fatal loop error handler logs and sets quit."""
        mock_base = Mock()

        _handle_fatal_loop_error(mock_base)

        mock_logger.exception.assert_called_once()
        assert mock_base.quit is True


class TestCleanupOnExit:
    """Test cleanup_on_exit function."""

    @patch("xbee.app.logger")
    def test_cleanup_on_exit(self, mock_logger):
        """Test cleanup_on_exit calls all cleanup functions."""
        mock_base = Mock()
        mock_display = Mock()

        _cleanup_on_exit(mock_base, mock_display)

        mock_base.send_quit_message.assert_called_once()
        mock_base.cleanup.assert_called_once_with(mock_display)
        assert mock_logger.info.call_count == 2


class TestProcessSingleIteration:
    """Test _process_single_iteration function."""

    @patch("time.sleep")
    def test_process_single_iteration_not_time_yet(self, mock_sleep):
        """Test iteration returns early when not enough time has passed."""
        mock_base = Mock()
        mock_base.frequency = 1000000000  # 1 second in ns
        mock_display = Mock()
        timer = time.time_ns()
        update_count = 0

        with patch("time.time_ns", return_value=timer + 100):
            new_timer, new_count, should_break = _process_single_iteration(
                mock_base, mock_display, timer, update_count
            )

        assert new_timer == timer
        assert new_count == 0
        assert should_break is False
        mock_sleep.assert_called_once_with(0.001)

    def test_process_single_iteration_runs_update(self):
        """Test iteration runs update cycle when time has passed."""
        mock_base = Mock()
        mock_base.frequency = 0  # Always run
        mock_base.input_source = Mock()
        mock_base.input_source.poll_events.return_value = []
        mock_base.controller_manager.controller_state.get_controller_values.return_value = (
            {}
        )
        mock_base.get_telemetry_data.return_value = {}
        mock_base.creep_mode = False
        mock_base.reverse_mode = False
        mock_display = Mock()
        timer = 0
        update_count = 0

        current_time = time.time_ns()
        with patch("time.time_ns", return_value=current_time):
            new_timer, new_count, should_break = _process_single_iteration(
                mock_base, mock_display, timer, update_count
            )

        assert new_timer == current_time
        assert new_count == 1
        assert should_break is False

    def test_process_single_iteration_handles_oserror(self):
        """Test iteration handles OSError without breaking."""
        mock_base = Mock()
        mock_base.frequency = 0
        mock_base.input_source = Mock()
        mock_base.input_source.poll_events.return_value = []
        mock_base.update_info.side_effect = OSError("Connection lost")
        mock_display = Mock()

        with (
            patch("time.time_ns", return_value=time.time_ns()),
            patch("time.sleep"),
            patch("xbee.app.logger"),
        ):
            _timer, _count, should_break = _process_single_iteration(
                mock_base, mock_display, 0, 0
            )

        assert should_break is False

    @patch("time.time_ns")
    def test_process_single_iteration_handles_input_source_error(self, mock_time):
        """Test iteration handles InputSourceError without breaking."""
        mock_base = Mock()
        mock_base.frequency = 0
        mock_base.input_source = Mock()
        mock_base.input_source.poll_events.return_value = []
        mock_base.update_info.side_effect = InputSourceError("Input error")
        mock_display = Mock()

        with (
            patch("time.time_ns", return_value=time.time_ns()),
            patch("time.sleep"),
            patch("xbee.app.logger"),
        ):
            _timer, _count, should_break = _process_single_iteration(
                mock_base, mock_display, 0, 0
            )

        assert should_break is False

    def test_process_single_iteration_handles_fatal_exception(self):
        """Test iteration handles fatal exceptions by breaking."""
        mock_base = Mock()
        mock_base.frequency = 0
        mock_base.input_source = Mock()
        mock_base.input_source.poll_events.return_value = []
        mock_base.update_info.side_effect = RuntimeError("Fatal error")
        mock_display = Mock()

        with (
            patch("time.time_ns", return_value=time.time_ns()),
            patch("xbee.app.logger"),
        ):
            _timer, _count, should_break = _process_single_iteration(
                mock_base, mock_display, 0, 0
            )

        assert should_break is True
        assert mock_base.quit is True


class TestProcessControllerEvents:
    """Test _process_controller_events function."""

    def test_process_quit_event(self):
        """Test QUIT event sets base_station.quit."""
        quit_event = InputEvent(type=QUIT)
        mock_base = Mock()
        mock_base.input_source = Mock()
        mock_base.input_source.poll_events.return_value = [quit_event]
        mock_display = Mock()

        with patch("xbee.app.logger"):
            _process_controller_events(mock_base, mock_display)

        assert mock_base.quit is True

    def test_process_joydeviceadded_event(self):
        """Test JOYDEVICEADDED event updates display."""
        add_event = InputEvent(
            type=JOYDEVICEADDED,
            instance_id=0,
            name="Xbox Controller",
            guid="12345",
        )
        mock_base = Mock()
        mock_base.input_source = Mock()
        mock_base.input_source.poll_events.return_value = [add_event]
        mock_display = Mock()

        _process_controller_events(mock_base, mock_display)

        mock_base.send_command.assert_called_once_with(add_event)
        mock_display.update_controller_display.assert_called_once()


class TestUpdateDisplayData:
    """Test _update_display_data function."""

    def test_update_display_data_with_telemetry(self):
        """Test display data update with telemetry."""
        from xbee.config.constants import CONSTANTS

        mock_base = Mock()
        mock_base.creep_mode = True
        mock_base.reverse_mode = False
        mock_base.xbee_enabled = True
        mock_base.get_telemetry_data.return_value = {"battery": 12.6}
        mock_base.controller_manager.controller_state.get_controller_values.side_effect = [
            {"ly": 0.5},
            {"cx": 0.1},
        ]
        # SpaceMouse not connected → should not appear in controller values
        mock_base.spacemouse.is_connected.return_value = False

        mock_display = Mock()

        _update_display_data(mock_base, mock_display, 42)

        mock_display.update_modes.assert_called_once_with(creep=True, reverse=False)
        mock_display.update_communication_status.assert_called_once_with(True, 42)
        # Now passes both Xbox and N64 values in a nested dict
        mock_display.update_controller_values.assert_called_once_with(
            {
                CONSTANTS.XBOX.NAME: {"ly": 0.5},
                CONSTANTS.N64.NAME: {"cx": 0.1},
            }
        )
        mock_display.update_telemetry.assert_called_once_with({"battery": 12.6})

    def test_update_display_data_no_telemetry(self):
        """Test display data update without telemetry."""
        mock_base = Mock()
        mock_base.creep_mode = False
        mock_base.reverse_mode = True
        mock_base.xbee_enabled = False
        mock_base.get_telemetry_data.return_value = {}
        mock_base.controller_manager.controller_state.get_controller_values.return_value = (
            {}
        )

        mock_display = Mock()

        _update_display_data(mock_base, mock_display, 0)

        mock_display.update_modes.assert_called_once_with(creep=False, reverse=True)
        mock_display.update_communication_status.assert_called_once_with(False, 0)
        # Empty telemetry should not call update_telemetry
        mock_display.update_telemetry.assert_not_called()


class TestRunUpdateCycle:
    """Test _run_update_cycle function."""

    def test_run_update_cycle_increments_count(self):
        """Test update cycle increments update count."""
        mock_base = Mock()
        mock_base.creep_mode = False
        mock_base.reverse_mode = False
        mock_base.xbee_enabled = True
        mock_base.input_source = Mock()
        mock_base.input_source.poll_events.return_value = []
        mock_base.get_telemetry_data.return_value = {}
        mock_base.controller_manager.controller_state.get_controller_values.return_value = (
            {}
        )

        mock_display = Mock()

        new_count = _run_update_cycle(mock_base, mock_display, 0)

        assert new_count == 1
        mock_base.update_info.assert_called_once()
