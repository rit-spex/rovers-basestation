"""
Tests for tkinter_display.py covering both HeadlessDisplay and TkinterDisplay.

Tests cover display initialization, update methods, and factory function.
"""

from unittest.mock import Mock, patch

import pytest

from xbee.display.base import HeadlessDisplay, create_display
from xbee.display.gui import TkinterDisplay


class TestHeadlessDisplay:
    """Test HeadlessDisplay implementation."""

    def test_headless_display_initialization(self):
        """Test HeadlessDisplay initializes without errors."""
        display = HeadlessDisplay()
        # Guard test to catch future regression in initialization.
        assert display is not None  # NOSONAR

    @patch("xbee.display.base.logger")
    def test_update_controller_display_logs_debug(self, mock_logger):
        """Test update_controller_display logs debug information."""
        display = HeadlessDisplay()

        display.update_controller_display(0, {"ly": 0.5, "ry": 0.5})

        mock_logger.debug.assert_called_once()
        assert "HeadlessDisplay updated controller" in mock_logger.debug.call_args[0][0]

    @patch("xbee.display.base.logger")
    def test_update_controller_values_logs_debug(self, mock_logger):
        """Test update_controller_values logs debug information."""
        display = HeadlessDisplay()

        display.update_controller_values({"ly": 0.5})

        mock_logger.debug.assert_called_once()

    @patch("xbee.display.base.logger")
    def test_update_modes_logs_debug(self, mock_logger):
        """Test update_modes logs debug information."""
        display = HeadlessDisplay()

        display.update_modes(creep=True, reverse=False)

        mock_logger.debug.assert_called_once()

    @patch("xbee.display.base.logger")
    def test_update_telemetry_logs_debug(self, mock_logger):
        """Test update_telemetry logs debug information."""
        display = HeadlessDisplay()

        telemetry = {"battery_voltage": 12.6}
        display.update_telemetry(telemetry)

        mock_logger.debug.assert_called_once()

    @patch("xbee.display.base.logger")
    def test_update_communication_status_logs_info(self, mock_logger):
        """Test update_communication_status logs info message."""
        display = HeadlessDisplay()

        display.update_communication_status(connected=True, message_count=42)

        mock_logger.info.assert_called_once()
        assert "Connected" in mock_logger.info.call_args[0][0]

    def test_run_does_nothing(self):
        """Test run method does nothing gracefully."""
        display = HeadlessDisplay()
        display.run()  # Should not raise

    def test_quit_does_nothing(self):
        """Test quit method does nothing gracefully."""
        display = HeadlessDisplay()
        display.quit()  # Should not raise

    def test_default_creep_mode_is_true(self):
        """HeadlessDisplay should default to creep enabled."""
        display = HeadlessDisplay()
        assert display.creep_mode is True


class TestTkinterDisplayInitialization:
    """Test TkinterDisplay initialization."""

    @patch.dict("os.environ", {"XBEE_NO_GUI": ""}, clear=False)
    @patch("xbee.display.gui.TK_AVAILABLE", True)
    @patch("xbee.display.gui.ttk")
    @patch("xbee.display.gui.tk")
    def test_tkinter_display_initialization_success(self, mock_tk, mock_ttk):
        """Test TkinterDisplay initializes with tkinter available."""
        mock_root = Mock()
        mock_tk.Tk.return_value = mock_root

        display = TkinterDisplay()

        assert display.root == mock_root
        # Default mode flag should show creep enabled on startup
        assert display.creep_mode is True
        display.quit()

    @patch.dict("os.environ", {"XBEE_NO_GUI": ""}, clear=False)
    @patch("xbee.display.gui.TK_AVAILABLE", True)
    @patch("xbee.display.gui.ttk")
    @patch("xbee.display.gui.tk")
    @patch("xbee.display.gui.logger")
    def test_tkinter_display_initialization_failure(
        self, mock_logger, mock_tk, mock_ttk
    ):
        """Test TkinterDisplay initialization failure is logged."""
        mock_tk.Tk.side_effect = RuntimeError("No display")

        with pytest.raises(RuntimeError):
            TkinterDisplay()

        mock_logger.error.assert_called_once()


class TestCreateDisplayFactory:
    """Test create_display factory function."""

    @patch("xbee.display.base.os.getenv")
    @patch("xbee.display.base.logger")
    def test_create_display_headless_when_no_gui_env(self, mock_logger, mock_getenv):
        """Test create_display returns HeadlessDisplay when XBEE_NO_GUI is set."""
        mock_getenv.return_value = "1"

        display = create_display()

        assert isinstance(display, HeadlessDisplay)
        mock_logger.info.assert_called_once()
        assert "HeadlessDisplay" in mock_logger.info.call_args[0][0]

    @patch.dict("os.environ", {"XBEE_TEST_OVERRIDE_GUI": "1"}, clear=False)
    @patch("xbee.display.base.os.getenv")
    @patch("xbee.display.gui.TkinterDisplay")
    def test_create_display_tkinter_when_gui_available(
        self, mock_tkinter_display, mock_getenv
    ):
        """Test create_display returns TkinterDisplay when GUI is available."""
        # Ensure our mock returns the correct values depending on the key asked
        def fake_getenv(key, default=None):
            if key == "XBEE_TEST_OVERRIDE_GUI":
                return "1"
            if key == "XBEE_NO_GUI":
                return None
            return default

        mock_getenv.side_effect = fake_getenv
        mock_instance = Mock()
        mock_tkinter_display.return_value = mock_instance

        display = create_display()

        assert display == mock_instance

    @patch.dict("os.environ", {"XBEE_TEST_OVERRIDE_GUI": "1"}, clear=False)
    @patch("xbee.display.base.os.getenv")
    @patch("xbee.display.gui.TkinterDisplay")
    @patch("xbee.display.base.logger")
    def test_create_display_falls_back_to_headless_on_error(
        self, mock_logger, mock_tkinter_display, mock_getenv
    ):
        """Test create_display falls back to HeadlessDisplay on TkinterDisplay error."""
        # Ensure the function correctly reports the XBEE_TEST_OVERRIDE_GUI variable so
        # the create_display function will attempt to instantiate a TkinterDisplay
        def fake_getenv(key, default=None):
            if key == "XBEE_TEST_OVERRIDE_GUI":
                return "1"
            if key == "XBEE_NO_GUI":
                return None
            return default

        mock_getenv.side_effect = fake_getenv
        mock_tkinter_display.side_effect = Exception("Display error")

        display = create_display()

        assert isinstance(display, HeadlessDisplay)
        mock_logger.warning.assert_called_once()
