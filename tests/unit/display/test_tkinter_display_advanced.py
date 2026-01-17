"""
Tests for TkinterDisplay advanced functionality.
"""

from unittest.mock import Mock, patch

import pytest

from xbee.core.command_codes import CONSTANTS
from xbee.core.tkinter_display import (
    HeadlessDisplay,
    TkinterDisplay,
    _GenericWidgetStub,
    create_display,
)


class TestGenericWidgetStub:
    """Test _GenericWidgetStub class."""

    def test_stub_grid(self):
        """Test stub grid method returns None."""
        stub = _GenericWidgetStub()
        assert stub.grid() is None

    def test_stub_configure(self):
        """Test stub configure method returns None."""
        stub = _GenericWidgetStub()
        assert stub.configure(text="test") is None

    def test_stub_delete(self):
        """Test stub delete method returns None."""
        stub = _GenericWidgetStub()
        assert stub.delete(1.0, "end") is None

    def test_stub_insert(self):
        """Test stub insert method returns None."""
        stub = _GenericWidgetStub()
        assert stub.insert("end", "text") is None


class TestHeadlessDisplayAdvanced:
    """Test HeadlessDisplay advanced functionality."""

    def test_update_telemetry_exception_handling(self):
        """Test update_telemetry handles exceptions."""
        display = HeadlessDisplay()
        display._telemetry_lock = Mock()
        display._telemetry_lock.__enter__ = Mock()
        display._telemetry_lock.__exit__ = Mock(return_value=False)
        display.telemetry_data = Mock()
        display.telemetry_data.update = Mock(side_effect=RuntimeError("Test error"))

        with pytest.raises(RuntimeError):
            display.update_telemetry({"key": "value"})

    def test_headless_flag_is_true(self):
        """Test headless display has headless=True."""
        display = HeadlessDisplay()
        assert display.headless is True

    def test_quit_sets_running_false(self):
        """Test quit sets running to False."""
        display = HeadlessDisplay()
        assert display.running is True

        display.quit()

        assert display.running is False


class TestTkinterDisplayAdvanced:
    """Test TkinterDisplay advanced functionality."""

    @patch("xbee.core.tkinter_display.TK_AVAILABLE", False)
    def test_tkinter_display_raises_when_tk_unavailable(self):
        """Test TkinterDisplay raises when tkinter unavailable."""
        # Temporarily remove XBEE_NO_GUI to test TK_AVAILABLE check
        import os

        old_val = os.environ.pop("XBEE_NO_GUI", None)
        try:
            with pytest.raises(RuntimeError, match="Tkinter unavailable"):
                TkinterDisplay()
        finally:
            if old_val is not None:
                os.environ["XBEE_NO_GUI"] = old_val

    def test_tkinter_display_raises_when_no_gui_env(self):
        """Test TkinterDisplay raises when XBEE_NO_GUI is set."""
        # XBEE_NO_GUI is already set in conftest.py
        with pytest.raises(RuntimeError, match="Tkinter unavailable"):
            TkinterDisplay()

    @patch.dict("os.environ", {"XBEE_NO_GUI": ""}, clear=False)
    @patch("xbee.core.tkinter_display.TK_AVAILABLE", True)
    @patch("xbee.core.tkinter_display.ttk")
    @patch("xbee.core.tkinter_display.tk")
    def test_update_controller_display_thread_safe(self, mock_tk, mock_ttk):
        """Test update_controller_display is thread-safe."""
        mock_root = Mock()
        mock_tk.Tk.return_value = mock_root

        display = TkinterDisplay()
        display.update_controller_display(0, {"name": "Xbox", "guid": "123"})
        display.update_controller_display(1, {"name": "N64", "guid": "456"})

        assert len(display.controllers) == 2
        display.quit()

    @patch.dict("os.environ", {"XBEE_NO_GUI": ""}, clear=False)
    @patch("xbee.core.tkinter_display.TK_AVAILABLE", True)
    @patch("xbee.core.tkinter_display.ttk")
    @patch("xbee.core.tkinter_display.tk")
    def test_update_controller_values_thread_safe(self, mock_tk, mock_ttk):
        """Test update_controller_values is thread-safe."""
        mock_root = Mock()
        mock_tk.Tk.return_value = mock_root

        display = TkinterDisplay()
        display.update_controller_values({"ly": 0.5, "ry": 0.3})

        assert display.controller_values["ly"] == pytest.approx(0.5)
        assert display.controller_values["ry"] == pytest.approx(0.3)
        display.quit()

    @patch.dict("os.environ", {"XBEE_NO_GUI": ""}, clear=False)
    @patch("xbee.core.tkinter_display.TK_AVAILABLE", True)
    @patch("xbee.core.tkinter_display.ttk")
    @patch("xbee.core.tkinter_display.tk")
    def test_update_modes_thread_safe(self, mock_tk, mock_ttk):
        """Test update_modes is thread-safe."""
        mock_root = Mock()
        mock_tk.Tk.return_value = mock_root

        display = TkinterDisplay()
        display.update_modes(creep=False, reverse=True)

        assert display.creep_mode is False
        assert display.reverse_mode is True
        display.quit()

    @patch.dict("os.environ", {"XBEE_NO_GUI": ""}, clear=False)
    @patch("xbee.core.tkinter_display.TK_AVAILABLE", True)
    @patch("xbee.core.tkinter_display.ttk")
    @patch("xbee.core.tkinter_display.tk")
    def test_update_telemetry_thread_safe(self, mock_tk, mock_ttk):
        """Test update_telemetry is thread-safe."""
        mock_root = Mock()
        mock_tk.Tk.return_value = mock_root

        display = TkinterDisplay()
        display.update_telemetry({"battery": 12.6, "temp": 25})

        assert display.telemetry_data["battery"] == pytest.approx(12.6)
        assert display.telemetry_data["temp"] == 25
        display.quit()

    @patch.dict("os.environ", {"XBEE_NO_GUI": ""}, clear=False)
    @patch("xbee.core.tkinter_display.TK_AVAILABLE", True)
    @patch("xbee.core.tkinter_display.ttk")
    @patch("xbee.core.tkinter_display.tk")
    def test_update_communication_status_labels(self, mock_tk, mock_ttk):
        """Test update_communication_status updates labels."""
        mock_root = Mock()
        mock_tk.Tk.return_value = mock_root

        display = TkinterDisplay()
        display.comm_status_label = Mock()
        display.update_counter_label = Mock()

        display.update_communication_status(connected=True, message_count=100)

        display.comm_status_label.config.assert_called()
        display.update_counter_label.config.assert_called()
        display.quit()

    @patch.dict("os.environ", {"XBEE_NO_GUI": ""}, clear=False)
    @patch("xbee.core.tkinter_display.TK_AVAILABLE", True)
    @patch("xbee.core.tkinter_display.ttk")
    @patch("xbee.core.tkinter_display.tk")
    def test_quit_stops_running(self, mock_tk, mock_ttk):
        """Test quit sets running to False."""
        mock_root = Mock()
        mock_tk.Tk.return_value = mock_root

        display = TkinterDisplay()
        display.running = True

        display.quit()

        assert display.running is False
        mock_root.quit.assert_called_once()

    @patch.dict("os.environ", {"XBEE_NO_GUI": ""}, clear=False)
    @patch("xbee.core.tkinter_display.TK_AVAILABLE", True)
    @patch("xbee.core.tkinter_display.ttk")
    @patch("xbee.core.tkinter_display.tk")
    def test_run_skips_mainloop_under_pytest_without_override(self, mock_tk, mock_ttk):
        """Test run() skips mainloop under pytest when override not set."""
        mock_root = Mock()
        mock_root.after_idle = Mock()
        mock_root.mainloop = Mock()
        mock_tk.Tk.return_value = mock_root

        display = TkinterDisplay()

        # Ensure the update thread started
        assert display.running is True

        # Run should return early under pytest without override
        display.run()
        mock_root.mainloop.assert_not_called()
        # Ensure we clean up and join the update thread
        display.quit()

    @patch.dict(
        "os.environ", {"XBEE_NO_GUI": "", "XBEE_TEST_OVERRIDE_GUI": "1"}, clear=False
    )
    @patch("xbee.core.tkinter_display.TK_AVAILABLE", True)
    @patch("xbee.core.tkinter_display.ttk")
    @patch("xbee.core.tkinter_display.tk")
    def test_run_calls_mainloop_under_pytest_with_override(self, mock_tk, mock_ttk):
        """Test run() calls mainloop under pytest when XBEE_TEST_OVERRIDE_GUI=1."""
        mock_root = Mock()
        mock_root.after_idle = Mock()
        mock_root.mainloop = Mock()
        mock_tk.Tk.return_value = mock_root

        display = TkinterDisplay()

        # Ensure the update thread started
        assert display.running is True

        display.run()

        mock_root.mainloop.assert_called()
        # mainloop should end and running flag cleared
        assert display.running is False
        # Ensure we clean up and join the update thread
        display.quit()

    @patch.dict("os.environ", {"XBEE_NO_GUI": ""}, clear=False)
    @patch("xbee.core.tkinter_display.TK_AVAILABLE", True)
    @patch("xbee.core.tkinter_display.ttk")
    @patch("xbee.core.tkinter_display.tk")
    def test_controller_type_metadata_drives_value_mapping(self, mock_tk, mock_ttk):
        """Controller type metadata should override name-based detection."""
        mock_root = Mock()
        mock_tk.Tk.return_value = mock_root

        display = TkinterDisplay()
        display._insert_controller_values = Mock()

        controller_data = {
            "name": "Generic Gamepad",
            "guid": "123",
            "type": CONSTANTS.XBOX.NAME,
        }
        controller_values = {
            CONSTANTS.XBOX.NAME: {"A": 2},
            CONSTANTS.N64.NAME: {"B": 1},
        }

        display._insert_controller_info(0, controller_data, controller_values, True)

        display._insert_controller_values.assert_called_once_with(
            controller_values[CONSTANTS.XBOX.NAME]
        )
        display.quit()


class TestCreateDisplayFactory:
    """Test create_display factory function."""

    @patch("xbee.core.tkinter_display.TK_AVAILABLE", False)
    def test_create_display_returns_headless_when_tk_unavailable(self):
        """Test factory returns HeadlessDisplay when tkinter unavailable."""
        display = create_display()

        assert isinstance(display, HeadlessDisplay)

    def test_create_display_prefer_gui_false(self):
        """Test factory returns HeadlessDisplay when prefer_gui=False."""
        display = create_display(prefer_gui=False)

        assert isinstance(display, HeadlessDisplay)

    @patch.dict("os.environ", {"XBEE_TEST_OVERRIDE_GUI": "1"}, clear=False)
    @patch("xbee.core.tkinter_display.TkinterDisplay")
    @patch("xbee.core.tkinter_display.TK_AVAILABLE", True)
    @patch("xbee.core.tkinter_display.os.getenv")
    def test_create_display_prefer_gui_true(self, mock_getenv, mock_tkinter_display):
        """Test factory tries TkinterDisplay when prefer_gui=True."""
        mock_getenv.return_value = None
        mock_instance = Mock()
        mock_tkinter_display.return_value = mock_instance

        display = create_display(prefer_gui=True)

        assert display == mock_instance

    @patch.dict("os.environ", {"XBEE_TEST_OVERRIDE_GUI": "1"}, clear=False)
    @patch("xbee.core.tkinter_display.TkinterDisplay")
    @patch("xbee.core.tkinter_display.TK_AVAILABLE", True)
    @patch("xbee.core.tkinter_display.os.getenv")
    def test_create_display_fallback_on_import_error(
        self, mock_getenv, mock_tkinter_display
    ):
        """Test factory falls back on ImportError."""

        def fake_getenv(key, default=None):
            if key == "XBEE_TEST_OVERRIDE_GUI":
                return "1"
            if key == "XBEE_NO_GUI":
                return None
            return default

        mock_getenv.side_effect = fake_getenv
        mock_tkinter_display.side_effect = ImportError("No module")

        display = create_display()

        assert isinstance(display, HeadlessDisplay)

    @patch.dict("os.environ", {"XBEE_TEST_OVERRIDE_GUI": "1"}, clear=False)
    @patch("xbee.core.tkinter_display.TkinterDisplay")
    @patch("xbee.core.tkinter_display.TK_AVAILABLE", True)
    @patch("xbee.core.tkinter_display.os.getenv")
    def test_create_display_fallback_on_runtime_error(
        self, mock_getenv, mock_tkinter_display
    ):
        """Test factory falls back on RuntimeError."""

        def fake_getenv(key, default=None):
            if key == "XBEE_TEST_OVERRIDE_GUI":
                return "1"
            if key == "XBEE_NO_GUI":
                return None
            return default

        mock_getenv.side_effect = fake_getenv
        mock_tkinter_display.side_effect = RuntimeError("Display error")

        display = create_display()

        assert isinstance(display, HeadlessDisplay)

    @patch.dict("os.environ", {"XBEE_TEST_OVERRIDE_GUI": "1"}, clear=False)
    @patch("xbee.core.tkinter_display.TkinterDisplay")
    @patch("xbee.core.tkinter_display.TK_AVAILABLE", True)
    @patch("xbee.core.tkinter_display.os.getenv")
    def test_create_display_fallback_on_value_error(
        self, mock_getenv, mock_tkinter_display
    ):
        """Test factory falls back on ValueError."""

        def fake_getenv(key, default=None):
            if key == "XBEE_TEST_OVERRIDE_GUI":
                return "1"
            if key == "XBEE_NO_GUI":
                return None
            return default

        mock_getenv.side_effect = fake_getenv
        mock_tkinter_display.side_effect = ValueError("Invalid value")

        display = create_display()

        assert isinstance(display, HeadlessDisplay)
