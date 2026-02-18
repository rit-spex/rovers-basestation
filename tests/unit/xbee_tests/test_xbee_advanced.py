"""
Tests for XbeeCommunicationManager advanced functionality.
"""

import threading
import time
from unittest.mock import Mock, patch

import pytest

from xbee.communication.xbee_backend import XbeeCommunicationManager


class TestXbeeCommunicationManagerAdvanced:
    """Test XbeeCommunicationManager advanced functionality."""

    def test_initialization_default_timeout(self):
        """Test default timeout initialization."""
        manager = XbeeCommunicationManager()

        assert abs(manager.inflight_wait_timeout - 30.0) < 0.001

    @patch.dict("os.environ", {"XBEE_INFLIGHT_WAIT_TIMEOUT": "10.0"})
    def test_initialization_custom_timeout(self):
        """Test custom timeout from environment."""
        manager = XbeeCommunicationManager()

        assert abs(manager.inflight_wait_timeout - 10.0) < 0.001

    @patch.dict("os.environ", {"XBEE_INFLIGHT_WAIT_TIMEOUT": "invalid"})
    def test_initialization_invalid_timeout(self):
        """Test invalid timeout raises ValueError."""
        with pytest.raises(ValueError, match="Invalid XBEE_INFLIGHT_WAIT_TIMEOUT"):
            XbeeCommunicationManager()

    @patch.dict("os.environ", {"XBEE_INFLIGHT_WAIT_TIMEOUT": "0"})
    def test_initialization_zero_timeout(self):
        """Test zero timeout raises ValueError."""
        with pytest.raises(ValueError, match="must be a positive number"):
            XbeeCommunicationManager()

    @patch.dict("os.environ", {"XBEE_INFLIGHT_WAIT_TIMEOUT": "-1"})
    def test_initialization_negative_timeout(self):
        """Test negative timeout raises ValueError."""
        with pytest.raises(ValueError, match="must be a positive number"):
            XbeeCommunicationManager()

    @patch.dict("os.environ", {"XBEE_INFLIGHT_ENTRY_MAX_AGE": "invalid"})
    def test_initialization_invalid_max_age(self):
        """Test invalid max age logs warning and uses default."""
        with patch("xbee.communication.xbee_backend.logger") as mock_logger:
            manager = XbeeCommunicationManager()

            mock_logger.warning.assert_called()
            assert manager.inflight_entry_max_age > 0

    def test_convert_to_bytes_from_bytes(self):
        """Test converting bytes to bytes."""
        manager = XbeeCommunicationManager()

        result = manager._convert_to_bytes(b"\x01\x02\x03")

        assert result == b"\x01\x02\x03"

    def test_convert_to_bytes_from_bytearray(self):
        """Test converting bytearray to bytes."""
        manager = XbeeCommunicationManager()

        result = manager._convert_to_bytes(bytearray([1, 2, 3]))

        assert result == b"\x01\x02\x03"

    def test_convert_to_bytes_from_list(self):
        """Test converting list to bytes."""
        manager = XbeeCommunicationManager()

        result = manager._convert_to_bytes([1, 2, 3])

        assert result == b"\x01\x02\x03"

    def test_convert_to_bytes_from_mixed_list(self):
        """Test converting mixed list to bytes."""
        manager = XbeeCommunicationManager()

        result = manager._convert_to_bytes([b"\x01", 2, b"\x03"])

        assert result == b"\x01\x02\x03"

    def test_convert_to_bytes_invalid_int(self):
        """Test converting list with invalid int raises error."""
        manager = XbeeCommunicationManager()

        with pytest.raises(ValueError, match="out of range"):
            manager._convert_to_bytes([256])

    def test_convert_to_bytes_negative_int(self):
        """Test converting list with negative int raises error."""
        manager = XbeeCommunicationManager()

        with pytest.raises(ValueError, match="out of range"):
            manager._convert_to_bytes([-1])

    def test_convert_to_bytes_invalid_type(self):
        """Test converting list with invalid type raises error."""
        manager = XbeeCommunicationManager()

        with pytest.raises(ValueError, match="Unsupported data type"):
            manager._convert_to_bytes(["string"])  # type: ignore[arg-type]

    def test_send_package_disabled(self):
        """Test send_package returns False when disabled."""
        manager = XbeeCommunicationManager()
        manager.enabled = False

        result = manager.send_package(b"\x01\x02")

        assert result is False

    def test_send_package_no_device(self):
        """Test send_package returns False when no device."""
        manager = XbeeCommunicationManager()
        manager.enabled = True
        manager.xbee_device = None

        result = manager.send_package(b"\x01\x02")

        assert result is False

    def test_send_package_no_remote(self):
        """Test send_package returns False when no remote."""
        manager = XbeeCommunicationManager()
        manager.enabled = True
        manager.xbee_device = Mock()
        manager.remote_xbee = None

        result = manager.send_package(b"\x01\x02")

        assert result is False

    def test_send_package_success(self):
        """Test send_package succeeds with device and remote."""
        manager = XbeeCommunicationManager()
        manager.enabled = True
        manager.xbee_device = Mock()
        manager.remote_xbee = Mock()

        result = manager.send_package(b"\x01\x02")

        assert result is True
        manager.xbee_device.send_data.assert_called_once()

    def test_send_package_duplicate_suppression(self):
        """Test duplicate messages are suppressed."""
        manager = XbeeCommunicationManager()
        manager.enabled = True
        manager.xbee_device = Mock()
        manager.remote_xbee = Mock()

        # First send
        result1 = manager.send_package(b"\x01\x02")
        # Second send with same data
        result2 = manager.send_package(b"\x01\x02")

        assert result1 is True
        assert result2 is True
        # Only one actual send
        assert manager.xbee_device.send_data.call_count == 1

    def test_send_package_skip_duplicate_check(self):
        """Test skip_duplicate_check sends even if duplicate."""
        manager = XbeeCommunicationManager()
        manager.enabled = True
        manager.xbee_device = Mock()
        manager.remote_xbee = Mock()

        # First send
        result1 = manager.send_package(b"\x01\x02")
        # Second send with skip_duplicate_check
        result2 = manager.send_package(b"\x01\x02", skip_duplicate_check=True)

        assert result1 is True
        assert result2 is True
        # Both sends should happen
        assert manager.xbee_device.send_data.call_count == 2

    def test_enable_disable(self):
        """Test enable and disable methods."""
        manager = XbeeCommunicationManager()

        manager.disable()
        assert manager.enabled is False

        manager.enable()
        assert manager.enabled is True

    def test_is_inflight_entry_stale_false(self):
        """Test stale check returns False for fresh entry."""
        manager = XbeeCommunicationManager()
        manager.inflight_entry_max_age = 100.0

        entry = (threading.Event(), {}, time.time())

        assert manager._is_stale(entry) is False

    def test_is_inflight_entry_stale_true(self):
        """Test stale check returns True for old entry."""
        manager = XbeeCommunicationManager()
        manager.inflight_entry_max_age = 0.001

        entry = (threading.Event(), {}, time.time() - 1.0)

        assert manager._is_stale(entry) is True

    def test_create_inflight_entry(self):
        """Test creating inflight entry."""
        manager = XbeeCommunicationManager()

        entry = manager._create_inflight(b"\x01\x02")

        assert isinstance(entry[0], threading.Event)
        assert isinstance(entry[1], dict)
        assert entry[2] > 0
        assert b"\x01\x02" in manager._inflight_messages

    def test_cleanup_stale_inflight_entry(self):
        """Test cleaning up stale inflight entry."""
        manager = XbeeCommunicationManager()

        event = threading.Event()
        result_container = {}
        entry = (event, result_container, time.time() - 1000)
        message_key = b"\x01\x02"
        manager._inflight_messages[message_key] = entry

        manager._cleanup_stale(message_key, entry)

        assert result_container.get("sent") is False
        assert event.is_set()
        assert message_key not in manager._inflight_messages

    def test_wait_for_inflight_result_success(self):
        """Test waiting for inflight result success."""
        manager = XbeeCommunicationManager()
        manager.inflight_wait_timeout = 1.0

        event = threading.Event()
        result_container = {"sent": True}

        # Set the event in a thread
        def set_event():
            time.sleep(0.01)
            event.set()

        thread = threading.Thread(target=set_event)
        thread.start()

        result = manager._wait_for_result(event, result_container)
        thread.join()

        assert result is True

    def test_wait_for_inflight_result_timeout(self):
        """Test waiting for inflight result timeout."""
        manager = XbeeCommunicationManager()
        manager.inflight_wait_timeout = 0.01

        event = threading.Event()
        result_container = {}

        with patch("xbee.communication.xbee_backend.logger"):
            result = manager._wait_for_result(event, result_container)

        assert result is False
