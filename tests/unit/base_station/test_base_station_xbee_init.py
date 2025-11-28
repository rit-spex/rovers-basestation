"""
Tests for BaseStation XBee initialization and error handling.
"""

from unittest.mock import Mock, patch


class TestXBeeInitialization:
    """Test XBee device initialization and fallback to simulation mode."""

    @patch("xbee.core.base_station.XBEE_AVAILABLE", True)
    @patch("xbee.core.base_station.XBeeDevice")
    @patch("xbee.core.base_station.RemoteXBeeDevice")
    @patch("xbee.core.base_station.XBee64BitAddress")
    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    @patch("xbee.core.base_station.CONSTANTS")
    def test_xbee_device_creation_success(
        self,
        mock_constants,
        mock_controller,
        mock_heartbeat,
        mock_comm,
        mock_addr,
        mock_remote,
        mock_device,
    ):
        """Test successful XBee device creation."""
        mock_constants.SIMULATION_MODE = False
        mock_constants.COMMUNICATION.DEFAULT_PORT = "/dev/ttyUSB0"
        mock_constants.COMMUNICATION.DEFAULT_BAUD_RATE = 9600
        mock_constants.COMMUNICATION.REMOTE_XBEE_ADDRESS = "0013A200XXXXXXXX"
        mock_constants.TIMING.UPDATE_FREQUENCY = 40000000

        mock_xbee_instance = Mock()
        mock_device.return_value = mock_xbee_instance

        from xbee.core.base_station import BaseStation

        base = BaseStation()

        assert base.xbee_enabled is True
        mock_xbee_instance.open.assert_called_once()

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_xbee_initialization_falls_back_on_oserror(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test that OSError during XBee initialization falls back to simulation."""
        from xbee.core.base_station import BaseStation

        with (
            patch("xbee.core.base_station.XBEE_AVAILABLE", True),
            patch("xbee.core.base_station.XBeeDevice") as mock_device,
            patch("xbee.core.base_station.CONSTANTS") as mock_constants,
            patch("xbee.core.base_station.logger") as mock_logger,
        ):
            mock_constants.SIMULATION_MODE = False
            mock_constants.COMMUNICATION.DEFAULT_PORT = "/dev/ttyUSB0"
            mock_constants.COMMUNICATION.DEFAULT_BAUD_RATE = 9600
            mock_constants.TIMING.UPDATE_FREQUENCY = 40000000
            mock_device.side_effect = OSError("Port not found")

            base = BaseStation()

            assert base.xbee_enabled is False
            mock_logger.warning.assert_called()


class TestXBeeErrorLogging:
    """Test XBee initialization error logging."""

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_log_xbee_init_error_oserror(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test error logging for OSError."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()

        with patch("xbee.core.base_station.logger") as mock_logger:
            base._log_xbee_init_error(OSError("Timeout"))

            mock_logger.warning.assert_called_once()
            assert "OS-level error" in mock_logger.warning.call_args[0][0]

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_log_xbee_init_error_generic(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test error logging for generic exceptions."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()

        with patch("xbee.core.base_station.logger") as mock_logger:
            base._log_xbee_init_error(RuntimeError("Unknown error"))

            mock_logger.exception.assert_called_once()


class TestXBeeCleanup:
    """Test XBee device cleanup."""

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_cleanup_xbee_device_success(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test cleanup closes XBee device successfully."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()
        base.xbee_enabled = True
        base.xbee_device = Mock()

        with patch("xbee.core.base_station.logger") as mock_logger:
            base._cleanup_xbee_device()

            base.xbee_device.close.assert_called_once()
            mock_logger.info.assert_called()

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_cleanup_xbee_device_error(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test cleanup handles XBee device close error."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()
        base.xbee_enabled = True
        base.xbee_device = Mock()
        base.xbee_device.close.side_effect = Exception("Close failed")

        with patch("xbee.core.base_station.logger") as mock_logger:
            base._cleanup_xbee_device()

            mock_logger.exception.assert_called_once()

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_cleanup_display_success(self, mock_controller, mock_heartbeat, mock_comm):
        """Test cleanup calls display quit."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()
        mock_display = Mock()

        base._cleanup_display(mock_display)

        mock_display.quit.assert_called_once()

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_cleanup_display_error(self, mock_controller, mock_heartbeat, mock_comm):
        """Test cleanup handles display quit error."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()
        mock_display = Mock()
        mock_display.quit.side_effect = Exception("Quit failed")

        with patch("xbee.core.base_station.logger") as mock_logger:
            base._cleanup_display(mock_display)

            mock_logger.exception.assert_called_once()

    @patch("xbee.core.base_station.CommunicationManager")
    @patch("xbee.core.base_station.HeartbeatManager")
    @patch("xbee.core.base_station.ControllerManager")
    def test_cleanup_communication_manager_error(
        self, mock_controller, mock_heartbeat, mock_comm
    ):
        """Test cleanup handles communication manager cleanup error."""
        from xbee.core.base_station import BaseStation

        base = BaseStation()
        base.communication_manager = Mock()
        base.communication_manager.cleanup.side_effect = Exception("Cleanup failed")

        with patch("xbee.core.base_station.logger") as mock_logger:
            base._cleanup_communication_manager()

            mock_logger.exception.assert_called_once()
