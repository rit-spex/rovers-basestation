"""
Consolidated tests for auto_boot.py module.

Tests cover XBee connection waiting, subprocess launching, and error handling.
"""

import os
import subprocess
import sys as _sys
import types
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

# Avoid importing a real digi.xbee.devices module during tests; provide a fake
fake_digi = types.ModuleType("digi")
fake_xbee = types.ModuleType("digi.xbee")
fake_devices = types.ModuleType("digi.xbee.devices")
fake_devices.XBeeDevice = object  # type: ignore[attr-defined]
fake_devices.XBeeException = Exception  # type: ignore[attr-defined]
_sys.modules["digi"] = fake_digi
_sys.modules["digi.xbee"] = fake_xbee
_sys.modules["digi.xbee.devices"] = fake_devices

import auto_boot.auto_boot as autoboot  # noqa: E402


class TestWaitForXBeeConnection:
    """Test XBee connection waiting logic."""

    @patch("auto_boot.auto_boot.subprocess.run")
    def test_connection_found_immediately(self, mock_run):
        """Test returns immediately when XBee is connected."""
        with patch("auto_boot.auto_boot.XBeeDevice") as mock_device_class:
            mock_device = Mock()
            mock_device_class.return_value = mock_device
            mock_device.open = Mock()
            mock_device.send_data = Mock()
            mock_device.close = Mock()

            result = autoboot.wait_for_xbee_connection()

            assert result is True

    @patch("auto_boot.auto_boot.time.sleep")
    def test_connection_after_retries(self, mock_sleep):
        """Test returns true after XBee connects on retry."""
        with patch("auto_boot.auto_boot.XBeeDevice") as mock_device_class:
            call_count = [0]

            def create_device(*args):
                call_count[0] += 1
                mock_device = Mock()
                mock_device.open = Mock()
                mock_device.close = Mock()

                if call_count[0] < 3:
                    mock_device.send_data = Mock(side_effect=Exception("Not ready"))
                else:
                    mock_device.send_data = Mock()

                return mock_device

            mock_device_class.side_effect = create_device

            result = autoboot.wait_for_xbee_connection()

            assert result is True


class TestLaunchXBeeScript:
    """Test XBee script launching."""

    @patch("auto_boot.auto_boot.subprocess.run")
    @patch("auto_boot.auto_boot.sys.executable", "/usr/bin/python3")
    def test_launch_success(self, mock_run):
        """Test successful launch of XBee script."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = autoboot.launch_xbee_script()

        assert result is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "/usr/bin/python3" in args or "python" in args[0]
        assert "-m" in args
        assert "xbee" in args

    @patch("auto_boot.auto_boot.subprocess.run")
    @patch("auto_boot.auto_boot.BAUD_RATE", 115200)
    def test_launch_with_custom_baud(self, mock_run):
        """Test launch uses module-level BAUD_RATE."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        autoboot.launch_xbee_script()

        env = mock_run.call_args[1].get("env", {})
        assert env.get("XBEE_BAUD") == "115200"

    @patch("auto_boot.auto_boot.subprocess.run")
    @patch("auto_boot.auto_boot.logger")
    def test_launch_subprocess_failure(self, mock_logger, mock_run):
        """Test subprocess failure is logged."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")

        result = autoboot.launch_xbee_script()

        assert result is False
        mock_logger.error.assert_called()

    @patch("auto_boot.auto_boot.subprocess.run")
    @patch("auto_boot.auto_boot.logger")
    def test_launch_unexpected_exception(self, mock_logger, mock_run):
        """Test unexpected exception is logged."""
        mock_run.side_effect = Exception("Unexpected error")

        result = autoboot.launch_xbee_script()

        assert result is False
        mock_logger.exception.assert_called_once()


class TestLaunchXBeeScriptExitOnError:
    """Test launch_xbee_script with exit_on_error=True."""

    def test_launch_xbee_chdir_raises_oserror(self, monkeypatch, caplog):
        """Test chdir OSError triggers SystemExit with proper logging."""
        caplog.set_level("ERROR")

        monkeypatch.setattr(autoboot, "XBEE_SCRIPT_DIR", "~/nonexistent")
        monkeypatch.setattr(os.path, "expanduser", lambda p: "/nonexistent")

        def fake_chdir(path):
            raise OSError("No such file or directory")

        monkeypatch.setattr(os, "chdir", fake_chdir)

        with pytest.raises(SystemExit) as exc:
            autoboot.launch_xbee_script(exit_on_error=True)

        assert exc.value.code == 1
        assert any(
            "Failed to change directory to" in rec.getMessage()
            for rec in caplog.records
        )

    def test_launch_xbee_subprocess_calledprocesserror(self, monkeypatch, caplog):
        """Test CalledProcessError triggers SystemExit with exit code."""
        caplog.set_level("ERROR")

        monkeypatch.setattr(autoboot, "XBEE_SCRIPT_DIR", "~/tmp")
        monkeypatch.setattr(os.path, "expanduser", lambda p: "/tmp")
        monkeypatch.setattr(os, "chdir", lambda p: None)

        def fake_run(cmd, check=True, env=None, capture_output=False, text=False):
            assert env is not None
            assert env.get("XBEE_NO_GUI") == "1"
            raise subprocess.CalledProcessError(2, cmd, output="out", stderr="err")

        monkeypatch.setattr(subprocess, "run", fake_run)

        with pytest.raises(SystemExit) as exc:
            autoboot.launch_xbee_script(exit_on_error=True)

        assert exc.value.code == 2
        assert any(
            "XBee process failed with return code 2" in rec.getMessage()
            for rec in caplog.records
        )

    def test_launch_xbee_subprocess_exception(self, monkeypatch, caplog):
        """Test unexpected exception triggers SystemExit."""
        caplog.set_level("ERROR")

        monkeypatch.setattr(autoboot, "XBEE_SCRIPT_DIR", "~/tmp")
        monkeypatch.setattr(os.path, "expanduser", lambda p: "/tmp")
        monkeypatch.setattr(os, "chdir", lambda p: None)

        def fake_run(cmd, check=True, env=None, capture_output=False, text=False):
            assert env is not None
            assert env.get("XBEE_NO_GUI") == "1"
            raise RuntimeError("boom")

        monkeypatch.setattr(subprocess, "run", fake_run)

        with pytest.raises(SystemExit) as exc:
            autoboot.launch_xbee_script(exit_on_error=True)

        assert exc.value.code == 1
        assert any(
            "Unexpected error while launching XBee process" in rec.getMessage()
            for rec in caplog.records
        )

    def test_launch_xbee_success(self, monkeypatch):
        """Test successful launch with exit_on_error does not raise."""
        monkeypatch.setattr(autoboot, "XBEE_SCRIPT_DIR", "~/tmp")
        monkeypatch.setattr(os.path, "expanduser", lambda p: "/tmp")
        monkeypatch.setattr(os, "chdir", lambda p: None)

        def fake_run(cmd, check=True, env=None, capture_output=False, text=False):
            assert env is not None
            assert env.get("XBEE_NO_GUI") == "1"
            return SimpleNamespace(returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)

        # No exception expected
        autoboot.launch_xbee_script(exit_on_error=True)
