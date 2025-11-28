"""
Tests for auto_boot.py advanced functionality.

NOTE: Basic launch script tests are in test_auto_boot.py. This module
contains specialized tests for stubs and config value helpers.
"""

from unittest.mock import Mock, patch

import pytest


class TestWaitForXBeeConnection:
    """Test wait_for_xbee_connection edge cases."""

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


class TestLaunchXBeeScriptInterrupt:
    """Test interrupt handling in launch_xbee_script."""

    @patch("auto_boot.auto_boot.os.chdir")
    @patch("auto_boot.auto_boot.subprocess.run")
    def test_launch_xbee_script_keyboard_interrupt(self, mock_run, mock_chdir):
        """Test launch_xbee_script propagates KeyboardInterrupt."""
        from auto_boot.auto_boot import launch_xbee_script

        mock_run.side_effect = KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            launch_xbee_script()


class TestXBeeDeviceStub:
    """Test _XBeeDeviceStub class."""

    def test_stub_open_raises(self):
        """Test stub open raises XBeeException."""
        from auto_boot.auto_boot import XBeeException, _XBeeDeviceStub

        stub = _XBeeDeviceStub()

        with pytest.raises(XBeeException):
            stub.open()

    def test_stub_send_data_raises(self):
        """Test stub send_data raises XBeeException."""
        from auto_boot.auto_boot import XBeeException, _XBeeDeviceStub

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
