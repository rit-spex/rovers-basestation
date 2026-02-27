"""
Comprehensive tests for GPS.py module.

Tests cover NMEA parsing, I2C communication, checksum validation,
and shutdown handling.
"""

from unittest.mock import Mock, patch

import pytest

from utils.gps import _reset_i2c_signature_cache, run_gps_reader, stop_gps_reader


@pytest.fixture(autouse=True)
def reset_gps_cache():
    """Reset GPS module state before each test."""
    _reset_i2c_signature_cache()
    yield
    _reset_i2c_signature_cache()


class TestNMEAParsing:
    """Test NMEA sentence parsing logic."""

    @patch("utils.gps.busio")
    @patch("utils.gps.board")
    @patch("utils.gps.logger")
    def test_nmea_checksum_validation_valid(self, mock_logger, mock_board, mock_busio):
        """Test valid NMEA checksum is accepted."""
        # GPGGA sample with valid checksum
        nmea_sentence = (
            b"$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47\r\n"
        )

        mock_i2c = Mock()
        mock_i2c.scan.return_value = [0x42]
        mock_i2c.readfrom_into = Mock()

        def fake_read(device, buffer, *args, **kwargs):
            buffer[: len(nmea_sentence)] = nmea_sentence
            return len(nmea_sentence)

        mock_i2c.readfrom_into.side_effect = fake_read
        mock_busio.I2C.return_value = mock_i2c

        with patch("utils.gps.shutdown_event") as mock_shutdown:
            mock_shutdown.is_set.side_effect = [False, True, True]  # Run once then stop

            run_gps_reader(gps_address=0x42)

            # Should log valid NMEA
            assert any(
                "valid" in str(call).lower()
                for call in mock_logger.debug.call_args_list
            )

    @patch("utils.gps.busio")
    @patch("utils.gps.board")
    @patch("utils.gps.logger")
    def test_nmea_checksum_validation_invalid(
        self, mock_logger, mock_board, mock_busio
    ):
        """Test invalid NMEA checksum is detected."""
        # NMEA with incorrect checksum
        nmea_sentence = (
            b"$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*FF\r\n"
        )

        mock_i2c = Mock()
        mock_i2c.scan.return_value = [0x42]

        def fake_read(device, buffer, *args, **kwargs):
            buffer[: len(nmea_sentence)] = nmea_sentence
            return len(nmea_sentence)

        mock_i2c.readfrom_into.side_effect = fake_read
        mock_busio.I2C.return_value = mock_i2c

        with patch("utils.gps.shutdown_event") as mock_shutdown:
            mock_shutdown.is_set.side_effect = [False, True, True]

            run_gps_reader(gps_address=0x42)

            # Should log checksum mismatch
            assert any(
                "mismatch" in str(call).lower()
                for call in mock_logger.debug.call_args_list
            )


class TestI2CCommunication:
    """Test I2C device communication."""

    @patch("utils.gps.busio")
    @patch("utils.gps.board")
    @patch("utils.gps.logger")
    def test_i2c_initialization_success(self, mock_logger, mock_board, mock_busio):
        """Test I2C bus initializes successfully."""
        mock_i2c = Mock()
        mock_i2c.scan.return_value = [0x42]
        mock_busio.I2C.return_value = mock_i2c

        with patch("utils.gps.shutdown_event") as mock_shutdown:
            mock_shutdown.is_set.return_value = True  # Exit immediately

            run_gps_reader(gps_address=0x42)

            mock_busio.I2C.assert_called_once()

    @patch("utils.gps.busio")
    @patch("utils.gps.board")
    @patch("utils.gps.logger")
    def test_i2c_initialization_failure_logged(
        self, mock_logger, mock_board, mock_busio
    ):
        """Test I2C initialization failure is logged."""
        mock_busio.I2C.side_effect = Exception("I2C error")

        with pytest.raises(RuntimeError):
            run_gps_reader()

        mock_logger.exception.assert_called_once()

    @patch("utils.gps.busio")
    @patch("utils.gps.board")
    @patch("utils.gps.logger")
    def test_gps_device_not_found_warning(self, mock_logger, mock_board, mock_busio):
        """Test warning when GPS device not found at expected address."""
        mock_i2c = Mock()
        mock_i2c.scan.return_value = [0x10, 0x20]  # Other devices, not GPS
        mock_busio.I2C.return_value = mock_i2c

        with patch("utils.gps.shutdown_event") as mock_shutdown:
            mock_shutdown.is_set.return_value = True

            run_gps_reader(gps_address=0x42)

            # Should log warning about missing device
            assert any(
                "No GPS device found" in str(call)
                for call in mock_logger.warning.call_args_list
            )

    @patch("utils.gps.busio")
    @patch("utils.gps.board")
    @patch("utils.gps.logger")
    def test_no_i2c_devices_found_warning(self, mock_logger, mock_board, mock_busio):
        """Test warning when no I2C devices found."""
        mock_i2c = Mock()
        mock_i2c.scan.return_value = []
        mock_busio.I2C.return_value = mock_i2c

        with patch("utils.gps.shutdown_event") as mock_shutdown:
            mock_shutdown.is_set.return_value = True

            run_gps_reader()

            mock_logger.warning.assert_called()
            assert any(
                "No I2C devices found" in str(call)
                for call in mock_logger.warning.call_args_list
            )


class TestShutdownHandling:
    """Test GPS reader shutdown mechanism."""

    def test_stop_gps_reader_sets_shutdown_event(self):
        """Test stop_gps_reader sets the shutdown event."""
        with patch("utils.gps.shutdown_event") as mock_event:
            stop_gps_reader()

            mock_event.set.assert_called_once()

    @patch("utils.gps.busio")
    @patch("utils.gps.board")
    def test_gps_reader_respects_shutdown_event(self, mock_board, mock_busio):
        """Test GPS reader exits when shutdown event is set."""
        mock_i2c = Mock()
        mock_i2c.scan.return_value = [0x42]
        mock_busio.I2C.return_value = mock_i2c

        with patch("utils.gps.shutdown_event") as mock_shutdown:
            # Shutdown immediately
            mock_shutdown.is_set.return_value = True

            run_gps_reader(gps_address=0x42)

            # Should have checked shutdown event
            mock_shutdown.is_set.assert_called()


class TestPartialBufferGuard:
    """Test protection against unbounded partial buffer growth."""

    @patch("utils.gps.busio")
    @patch("utils.gps.board")
    def test_partial_buffer_overflow_protection(self, mock_board, mock_busio):
        """Test partial buffer doesn't grow indefinitely."""
        # Send data without newlines to test partial buffer
        mock_i2c = Mock()
        mock_i2c.scan.return_value = [0x42]
        mock_i2c.readfrom_into = Mock()

        def fake_read_no_newline(device, buffer, *args, **kwargs):
            # Return data without newlines
            data = b"AAAAA"
            buffer[: len(data)] = data
            return len(data)

        mock_i2c.readfrom_into.side_effect = fake_read_no_newline
        mock_busio.I2C.return_value = mock_i2c

        with patch("utils.gps.shutdown_event") as mock_shutdown:
            # Run a few iterations then stop
            call_count = [0]

            def check_shutdown():
                call_count[0] += 1
                return call_count[0] > 3

            mock_shutdown.is_set.side_effect = check_shutdown

            # Function should complete without error (no overflow crash)
            run_gps_reader(gps_address=0x42)


class TestBlinkaMissing:
    """Test behavior when Adafruit Blinka is not available."""

    @patch("utils.gps.board", None)
    @patch("utils.gps.busio", None)
    @patch("utils.gps.logger")
    def test_gps_reader_warns_when_blinka_missing(self, mock_logger):
        """Test GPS reader logs warning when board/busio unavailable."""
        run_gps_reader()

        mock_logger.warning.assert_called_once()
        assert (
            "board/busio modules not available" in mock_logger.warning.call_args[0][0]
        )
