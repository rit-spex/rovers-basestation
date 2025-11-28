"""
Tests for gps.py advanced functionality.
"""

import signal
from unittest.mock import Mock, patch


class TestGpsShutdownEvent:
    """Test GPS shutdown event functionality."""

    def test_stop_gps_reader_sets_event(self):
        """Test stop_gps_reader sets the shutdown event."""
        from utils.gps import shutdown_event, stop_gps_reader

        shutdown_event.clear()
        stop_gps_reader()

        assert shutdown_event.is_set()

        # Clean up
        shutdown_event.clear()


class TestI2CSignatureDetection:
    """Test I2C API signature detection."""

    def test_detect_i2c_signature_device_buffer(self):
        """Test detecting device_buffer signature."""
        from utils.gps import _detect_i2c_signature

        mock_i2c = Mock()
        mock_i2c.readfrom_into = Mock()

        # Mock inspect.signature to return 2 params
        with patch("inspect.signature") as mock_sig:
            mock_params = Mock()
            mock_params.parameters = {"device": Mock(), "buffer": Mock()}
            mock_sig.return_value = mock_params

            result = _detect_i2c_signature(mock_i2c)

        assert result == "device_buffer"

    def test_detect_i2c_signature_buffer_only(self):
        """Test detecting buffer_only signature."""
        from utils.gps import _detect_i2c_signature

        mock_i2c = Mock()
        mock_i2c.readfrom_into = Mock()

        # Mock inspect.signature to return 1 param
        with patch("inspect.signature") as mock_sig:
            mock_params = Mock()
            mock_params.parameters = {"buffer": Mock()}
            mock_sig.return_value = mock_params

            result = _detect_i2c_signature(mock_i2c)

        assert result == "buffer_only"

    def test_detect_i2c_signature_exception(self):
        """Test detecting signature falls back on exception."""
        from utils.gps import _detect_i2c_signature

        mock_i2c = Mock()
        mock_i2c.readfrom_into = Mock()

        with patch("inspect.signature", side_effect=Exception("Test error")):
            result = _detect_i2c_signature(mock_i2c)

        assert result == "device_buffer"

    def test_reset_i2c_signature_cache(self):
        """Test resetting I2C signature cache."""
        from utils.gps import _reset_i2c_signature_cache

        _reset_i2c_signature_cache()

        # Cache should be None after reset
        import utils.gps

        assert utils.gps._i2c_api_signature is None


class TestNmeaValidation:
    """Test NMEA validation functions."""

    def test_decode_line_ascii(self):
        """Test decoding ASCII line."""
        from utils.gps import _decode_line

        result = _decode_line(b"$GPGGA,123456,...")

        assert result == "$GPGGA,123456,..."

    def test_decode_line_utf8_fallback(self):
        """Test decoding with UTF-8 fallback."""
        from utils.gps import _decode_line

        # Valid UTF-8 but invalid ASCII (é = \xc3\xa9)
        result = _decode_line(b"$GPGGA,\xc3\xa9,test")

        # Should successfully decode with UTF-8
        assert result == "$GPGGA,é,test"

    def test_validate_nmea_checksum_valid(self):
        """Test valid NMEA checksum."""
        from utils.gps import _validate_nmea_checksum

        # Known valid NMEA sentence
        result = _validate_nmea_checksum(
            "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"
        )

        # The result depends on actual checksum calculation
        assert result is True

    def test_validate_nmea_checksum_no_checksum(self):
        """Test NMEA with no checksum returns True."""
        from utils.gps import _validate_nmea_checksum

        result = _validate_nmea_checksum("$GPGGA,123456")

        assert result is True

    def test_validate_nmea_checksum_short_checksum(self):
        """Test NMEA with short checksum returns True."""
        from utils.gps import _validate_nmea_checksum

        result = _validate_nmea_checksum("$GPGGA,123456*0")

        assert result is True

    def test_process_nmea_line_non_nmea(self):
        """Test processing non-NMEA line."""
        from utils.gps import _process_nmea_line

        with patch("utils.gps.logger") as mock_logger:
            _process_nmea_line(b"Not an NMEA sentence")

            mock_logger.debug.assert_called()


class TestPartialBufferProcessing:
    """Test partial buffer processing."""

    def test_process_partial_buffer_normal(self):
        """Test processing normal partial buffer."""
        from utils.gps import _process_partial_buffer

        partial = b"$GPGGA,123\n$GPRMC,456"

        result = _process_partial_buffer(partial, 1024)

        # Should have extracted the first line
        assert result == b"$GPRMC,456"

    def test_process_partial_buffer_overflow(self):
        """Test processing overflowed partial buffer."""
        from utils.gps import _process_partial_buffer

        # Create a large partial buffer
        partial = b"x" * 100 + b"\n" + b"y" * 50

        with patch("utils.gps.logger"):
            result = _process_partial_buffer(partial, 100)

        # Buffer should be truncated
        assert len(result) <= 100


class TestGpsReader:
    """Test GPS reader functions."""

    def test_run_gps_reader_no_blinka(self):
        """Test run_gps_reader when blinka unavailable."""
        from utils.gps import run_gps_reader

        with (
            patch("utils.gps.board", None),
            patch("utils.gps.logger") as mock_logger,
        ):
            run_gps_reader()

            mock_logger.warning.assert_called()

    def test_cleanup_i2c_bus_none(self):
        """Test cleanup_i2c_bus with None."""
        from utils.gps import cleanup_i2c_bus

        # Should not raise
        cleanup_i2c_bus(None)

    def test_cleanup_i2c_bus_with_deinit(self):
        """Test cleanup_i2c_bus with deinit method."""
        from utils.gps import cleanup_i2c_bus

        mock_i2c = Mock()
        mock_i2c.deinit = Mock()

        cleanup_i2c_bus(mock_i2c)

        mock_i2c.deinit.assert_called_once()

    def test_cleanup_i2c_bus_with_close(self):
        """Test cleanup_i2c_bus with close method."""
        from utils.gps import cleanup_i2c_bus

        mock_i2c = Mock(spec=["close"])
        mock_i2c.close = Mock()

        cleanup_i2c_bus(mock_i2c)

        mock_i2c.close.assert_called_once()


class TestSignalHandlers:
    """Test signal handler registration."""

    def test_register_signal_handlers(self):
        """Test registering signal handlers."""
        from utils.gps import _register_signal_handlers

        with (
            patch("signal.signal") as mock_signal,
            patch("utils.gps.logger"),
        ):
            _register_signal_handlers()

            # Should register both SIGINT and SIGTERM
            assert mock_signal.call_count == 2
            calls = [call[0][0] for call in mock_signal.call_args_list]
            assert signal.SIGINT in calls
            assert signal.SIGTERM in calls


class TestScanForGps:
    """Test I2C scanning for GPS."""

    def test_scan_for_gps_found(self):
        """Test scanning finds GPS device."""
        from utils.gps import _scan_for_gps

        mock_i2c = Mock()
        mock_i2c.scan.return_value = [0x42, 0x50]

        result = _scan_for_gps(mock_i2c, 0x42)

        assert result == 0x42

    def test_scan_for_gps_not_found(self):
        """Test scanning when GPS not at expected address."""
        from utils.gps import _scan_for_gps

        mock_i2c = Mock()
        mock_i2c.scan.return_value = [0x50, 0x60]

        with patch("utils.gps.logger"):
            result = _scan_for_gps(mock_i2c, 0x42)

        assert result is None

    def test_scan_for_gps_empty(self):
        """Test scanning with no devices."""
        from utils.gps import _scan_for_gps

        mock_i2c = Mock()
        mock_i2c.scan.return_value = []

        with patch("utils.gps.logger"):
            result = _scan_for_gps(mock_i2c, 0x42)

        assert result is None


class TestReadI2CData:
    """Test I2C data reading."""

    def test_read_i2c_data_device_buffer(self):
        """Test reading with device_buffer signature."""
        from utils.gps import _read_i2c_data, _reset_i2c_signature_cache

        _reset_i2c_signature_cache()

        mock_i2c = Mock()
        buffer = bytearray(64)

        with patch("utils.gps._detect_i2c_signature", return_value="device_buffer"):
            _read_i2c_data(mock_i2c, 0x42, buffer)

            mock_i2c.readfrom_into.assert_called_with(0x42, buffer)

        _reset_i2c_signature_cache()

    def test_read_i2c_data_buffer_only(self):
        """Test reading with buffer_only signature."""
        from utils.gps import _read_i2c_data, _reset_i2c_signature_cache

        _reset_i2c_signature_cache()

        mock_i2c = Mock()
        buffer = bytearray(64)

        with patch("utils.gps._detect_i2c_signature", return_value="buffer_only"):
            _read_i2c_data(mock_i2c, 0x42, buffer)

            mock_i2c.readfrom_into.assert_called_with(buffer)

        _reset_i2c_signature_cache()
