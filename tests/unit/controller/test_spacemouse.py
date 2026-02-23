"""Tests for the SpaceMouse HID input reader."""

import struct

from xbee.controller.spacemouse import SpaceMouse
from xbee.config.constants import CONSTANTS


def test_get_state_returns_all_expected_keys():
    sm = SpaceMouse()
    state = sm.get_state()
    expected_keys = {"x", "y", "z", "rx", "ry", "rz", "buttons"}
    assert set(state.keys()) == expected_keys


def test_initial_state_values_are_zero():
    sm = SpaceMouse()
    state = sm.get_state()
    for key in ("x", "y", "z", "rx", "ry", "rz", "buttons"):
        assert state[key] == 0, f"Expected {key} to be 0, got {state[key]}"


def test_is_connected_returns_false_initially():
    sm = SpaceMouse()
    assert sm.is_connected() is False


def test_process_report_6dof():
    """A 6DOF report (report ID 0x01) should update translation/rotation state."""
    sm = SpaceMouse()

    # Raw HID values before sign inversion
    raw_x, raw_y, raw_z = 100, 200, 300
    raw_rx, raw_ry, raw_rz = 400, 500, 600

    # Build a mock HID report: report_id (0x01) + 6 little-endian int16 values
    data = [0x01] + list(struct.pack("<hhhhhh", raw_x, raw_y, raw_z, raw_rx, raw_ry, raw_rz))

    sm._process_report(data)
    state = sm.get_state()

    # The SpaceMouse class inverts y, z, and rz
    assert state["x"] == raw_x
    assert state["y"] == -raw_y
    assert state["z"] == -raw_z
    assert state["rx"] == raw_rx
    assert state["ry"] == raw_ry
    assert state["rz"] == -raw_rz


def test_process_report_buttons():
    """A button report (report ID 0x03) should update button state."""
    sm = SpaceMouse()

    button_mask = 0x001F  # first 5 buttons pressed
    data = [0x03] + list(struct.pack("<H", button_mask))

    sm._process_report(data)
    state = sm.get_state()

    assert state["buttons"] == button_mask


def test_parse_6dof_sign_conventions():
    """Verify y, z translations and rz rotation are inverted."""
    sm = SpaceMouse()

    raw_x, raw_y, raw_z = 1, 1, 1
    raw_rx, raw_ry, raw_rz = 1, 1, 1

    data = [0x01] + list(struct.pack("<hhhhhh", raw_x, raw_y, raw_z, raw_rx, raw_ry, raw_rz))
    sm._process_report(data)
    state = sm.get_state()

    # x is NOT inverted
    assert state["x"] == 1
    # y IS inverted
    assert state["y"] == -1
    # z IS inverted
    assert state["z"] == -1
    # rx is NOT inverted
    assert state["rx"] == 1
    # ry is NOT inverted
    assert state["ry"] == 1
    # rz IS inverted
    assert state["rz"] == -1


def test_parse_6dof_negative_raw_values():
    """Negative raw values should also have the inversions applied."""
    sm = SpaceMouse()

    raw_x, raw_y, raw_z = -500, -300, -100
    raw_rx, raw_ry, raw_rz = -10, -20, -30

    data = [0x01] + list(struct.pack("<hhhhhh", raw_x, raw_y, raw_z, raw_rx, raw_ry, raw_rz))
    sm._process_report(data)
    state = sm.get_state()

    assert state["x"] == -500
    assert state["y"] == 300   # negated: -(-300) = 300
    assert state["z"] == 100   # negated: -(-100) = 100
    assert state["rx"] == -10
    assert state["ry"] == -20
    assert state["rz"] == 30   # negated: -(-30) = 30


def test_process_report_ignores_short_6dof():
    """Report 0x01 with fewer than 13 bytes should not update state."""
    sm = SpaceMouse()

    # Only 7 bytes instead of required 13
    data = [0x01, 0x00, 0x01, 0x00, 0x02, 0x00, 0x03]
    sm._process_report(data)
    state = sm.get_state()

    # State should remain at initial zeros
    for key in ("x", "y", "z", "rx", "ry", "rz"):
        assert state[key] == 0


def test_process_report_ignores_short_button():
    """Report 0x03 with fewer than 3 bytes should not update state."""
    sm = SpaceMouse()

    data = [0x03, 0xFF]  # Only 2 bytes, need at least 3
    sm._process_report(data)
    state = sm.get_state()

    assert state["buttons"] == 0


def test_process_report_ignores_empty_data():
    """Empty data should not crash or change state."""
    sm = SpaceMouse()
    sm._process_report([])
    state = sm.get_state()

    for key in ("x", "y", "z", "rx", "ry", "rz", "buttons"):
        assert state[key] == 0


def test_process_report_ignores_unknown_report_id():
    """Unknown report IDs should be silently ignored."""
    sm = SpaceMouse()

    data = [0x99, 0x01, 0x02, 0x03]
    sm._process_report(data)
    state = sm.get_state()

    for key in ("x", "y", "z", "rx", "ry", "rz", "buttons"):
        assert state[key] == 0
