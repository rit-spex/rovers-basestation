"""
Tests for auto_boot.py advanced functionality.
"""

import subprocess
from unittest.mock import Mock, patch

import pytest


class TestAutoBoot:
    """Test auto_boot module functionality."""

    @patch("auto_boot.auto_boot.time.sleep")
    def test_wait_for_xbee_connection_no_libs(self, mock_sleep):
        """Test wait_for_xbee_connection returns False when libs unavailable."""
        import auto_boot.auto_boot as auto_boot_module

        with (
            patch("auto_boot.auto_boot.XBeeDevice", auto_boot_module._XBeeDeviceStub),
            patch("auto_boot.auto_boot.logger"),
        ):
            result = auto_boot_module.wait_for_xbee_connection()

        assert result is False

    @patch("auto_boot.auto_boot.os.chdir")
    @patch("auto_boot.auto_boot.subprocess.run")
    def test_launch_xbee_script_success(self, mock_run, mock_chdir):
        """Test launch_xbee_script succeeds."""
        from auto_boot.auto_boot import launch_xbee_script

        mock_run.return_value = Mock(returncode=0)

        result = launch_xbee_script()

        assert result is True
        mock_chdir.assert_called_once()
        mock_run.assert_called_once()

    @patch("auto_boot.auto_boot.os.chdir")
    def test_launch_xbee_script_chdir_fails(self, mock_chdir):
        """Test launch_xbee_script handles chdir failure."""
        from auto_boot.auto_boot import launch_xbee_script

        mock_chdir.side_effect = OSError("Directory not found")

        with patch("auto_boot.auto_boot.logger"):
            result = launch_xbee_script()

        assert result is False

    @patch("auto_boot.auto_boot.os.chdir")
    def test_launch_xbee_script_chdir_fails_exit(self, mock_chdir):
        """Test launch_xbee_script exits on chdir failure with exit_on_error."""
        from auto_boot.auto_boot import launch_xbee_script

        mock_chdir.side_effect = OSError("Directory not found")

        with (
            patch("auto_boot.auto_boot.logger"),
            pytest.raises(SystemExit) as exc_info,
        ):
            launch_xbee_script(exit_on_error=True)

        assert exc_info.value.code == 1

    @patch("auto_boot.auto_boot.os.chdir")
    @patch("auto_boot.auto_boot.subprocess.run")
    def test_launch_xbee_script_called_process_error(self, mock_run, mock_chdir):
        """Test launch_xbee_script handles CalledProcessError."""
        from auto_boot.auto_boot import launch_xbee_script

        mock_run.side_effect = subprocess.CalledProcessError(1, "test")

        with patch("auto_boot.auto_boot.logger"):
            result = launch_xbee_script()

        assert result is False

    @patch("auto_boot.auto_boot.os.chdir")
    @patch("auto_boot.auto_boot.subprocess.run")
    def test_launch_xbee_script_called_process_error_exit(self, mock_run, mock_chdir):
        """Test launch_xbee_script exits on CalledProcessError with exit_on_error."""
        from auto_boot.auto_boot import launch_xbee_script

        mock_run.side_effect = subprocess.CalledProcessError(42, "test")

        with (
            patch("auto_boot.auto_boot.logger"),
            pytest.raises(SystemExit) as exc_info,
        ):
            launch_xbee_script(exit_on_error=True)

        assert exc_info.value.code == 42

    @patch("auto_boot.auto_boot.os.chdir")
    @patch("auto_boot.auto_boot.subprocess.run")
    def test_launch_xbee_script_keyboard_interrupt(self, mock_run, mock_chdir):
        """Test launch_xbee_script propagates KeyboardInterrupt."""
        from auto_boot.auto_boot import launch_xbee_script

        mock_run.side_effect = KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            launch_xbee_script()

    @patch("auto_boot.auto_boot.os.chdir")
    @patch("auto_boot.auto_boot.subprocess.run")
    def test_launch_xbee_script_generic_exception(self, mock_run, mock_chdir):
        """Test launch_xbee_script handles generic exceptions."""
        from auto_boot.auto_boot import launch_xbee_script

        mock_run.side_effect = RuntimeError("Unknown error")

        with patch("auto_boot.auto_boot.logger"):
            result = launch_xbee_script()

        assert result is False

    @patch("auto_boot.auto_boot.os.chdir")
    @patch("auto_boot.auto_boot.subprocess.run")
    def test_launch_xbee_script_generic_exception_exit(self, mock_run, mock_chdir):
        """Test launch_xbee_script exits on generic exception with exit_on_error."""
        from auto_boot.auto_boot import launch_xbee_script

        mock_run.side_effect = RuntimeError("Unknown error")

        with (
            patch("auto_boot.auto_boot.logger"),
            pytest.raises(SystemExit) as exc_info,
        ):
            launch_xbee_script(exit_on_error=True)

        assert exc_info.value.code == 1


class TestXBeeDeviceStub:
    """Test _XBeeDeviceStub class."""

    def test_stub_open_raises(self):
        """Test stub open raises XBeeException."""
        from auto_boot.auto_boot import _XBeeDeviceStub, XBeeException

        stub = _XBeeDeviceStub()

        with pytest.raises(XBeeException):
            stub.open()

    def test_stub_send_data_raises(self):
        """Test stub send_data raises XBeeException."""
        from auto_boot.auto_boot import _XBeeDeviceStub, XBeeException

        stub = _XBeeDeviceStub()

        with pytest.raises(XBeeException):
            stub.send_data("remote", "data")

    def test_stub_close_no_error(self):
        """Test stub close returns None."""
        from auto_boot.auto_boot import _XBeeDeviceStub

        stub = _XBeeDeviceStub()

        result = stub.close()

        assert result is None


class TestConfigValues:
    """Test config value parsing."""

    def test_get_config_value_no_constants(self):
        """Test _get_config_value with no CONSTANTS."""
        from auto_boot.auto_boot import _get_config_value

        with patch("auto_boot.auto_boot.CONSTANTS", None):
            result = _get_config_value("DEFAULT_PORT", "/dev/default")

        assert result == "/dev/default"

    def test_get_config_value_no_communication(self):
        """Test _get_config_value with no COMMUNICATION attr."""
        from auto_boot.auto_boot import _get_config_value

        mock_constants = Mock(spec=[])  # No COMMUNICATION

        with patch("auto_boot.auto_boot.CONSTANTS", mock_constants):
            result = _get_config_value("DEFAULT_PORT", "/dev/default")

        assert result == "/dev/default"

    def test_get_config_value_success(self):
        """Test _get_config_value returns config value."""
        from auto_boot.auto_boot import _get_config_value

        mock_constants = Mock()
        mock_constants.COMMUNICATION.DEFAULT_PORT = "/dev/ttyUSB1"

        with patch("auto_boot.auto_boot.CONSTANTS", mock_constants):
            result = _get_config_value("DEFAULT_PORT", "/dev/default")

        assert result == "/dev/ttyUSB1"
