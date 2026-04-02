"""Tests for the SpaceMouse HID input reader."""

import struct
import threading

from xbee.controller.spacemouse import SpaceMouse
from xbee.controller.detection import detect_controller_type
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


def test_process_report_translation_only():
    """Report ID 0x01 with 3 axes should update x/y/z only."""
    sm = SpaceMouse()

    raw_x, raw_y, raw_z = 123, -234, 345
    data = [0x01] + list(struct.pack("<hhh", raw_x, raw_y, raw_z))

    sm._process_report(data)
    state = sm.get_state()

    assert state["x"] == raw_x
    assert state["y"] == -raw_y
    assert state["z"] == -raw_z
    # Rotational axes remain unchanged
    assert state["rx"] == 0
    assert state["ry"] == 0
    assert state["rz"] == 0


def test_process_report_rotation_only():
    """Report ID 0x02 with 3 axes should update rx/ry/rz only."""
    sm = SpaceMouse()

    raw_rx, raw_ry, raw_rz = -111, 222, -333
    data = [0x02] + list(struct.pack("<hhh", raw_rx, raw_ry, raw_rz))

    sm._process_report(data)
    state = sm.get_state()

    assert state["rx"] == raw_rx
    assert state["ry"] == raw_ry
    assert state["rz"] == -raw_rz
    # Translation axes remain unchanged
    assert state["x"] == 0
    assert state["y"] == 0
    assert state["z"] == 0


def test_split_mode_padded_translation_does_not_reset_rotation():
    """After a split rotation packet, padded 0x01 packets must not clobber rx/ry/rz."""
    sm = SpaceMouse()

    # Enter split-report mode by observing a rotation packet.
    raw_rx, raw_ry, raw_rz = 10, -20, 30
    rot = [0x02] + list(struct.pack("<hhh", raw_rx, raw_ry, raw_rz))
    sm._process_report(rot)

    # Translation-only packet padded to >=13 bytes (common HID read behavior).
    raw_x, raw_y, raw_z = 111, 222, -333
    padded_translation = [0x01] + list(struct.pack("<hhh", raw_x, raw_y, raw_z)) + [0, 0, 0, 0, 0, 0]
    sm._process_report(padded_translation)

    state = sm.get_state()
    assert state["x"] == raw_x
    assert state["y"] == -raw_y
    assert state["z"] == -raw_z
    # Rotation remains what report 0x02 set.
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


def test_process_report_ignores_short_translation():
    """Report 0x01 with fewer than 7 bytes should not update state."""
    sm = SpaceMouse()

    # Only 6 bytes instead of required 7 for translation report
    data = [0x01, 0x00, 0x01, 0x00, 0x02, 0x00]
    sm._process_report(data)
    state = sm.get_state()

    # State should remain at initial zeros
    for key in ("x", "y", "z", "rx", "ry", "rz"):
        assert state[key] == 0


def test_process_report_ignores_short_rotation():
    """Report 0x02 with fewer than 7 bytes should not update state."""
    sm = SpaceMouse()

    data = [0x02, 0x00, 0x01, 0x00, 0x02, 0x00]
    sm._process_report(data)
    state = sm.get_state()

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


# ------------------------------------------------------------------
# _zero_state helper
# ------------------------------------------------------------------


def test_zero_state_returns_all_zero():
    """The _zero_state helper should return a dict with all zeros."""
    state = SpaceMouse._zero_state()
    assert set(state.keys()) == {"x", "y", "z", "rx", "ry", "rz", "buttons"}
    for key, val in state.items():
        assert val == 0, f"Expected {key} to be 0, got {val}"


def test_zero_state_returns_new_dict_each_call():
    """Each call should return an independent dict."""
    s1 = SpaceMouse._zero_state()
    s2 = SpaceMouse._zero_state()
    assert s1 is not s2
    s1["x"] = 999
    assert s2["x"] == 0


# ------------------------------------------------------------------
# Disconnect callback
# ------------------------------------------------------------------


def test_disconnect_callback_called_on_close():
    """_close_device should invoke on_disconnect when transitioning from connected."""
    callback_invoked = threading.Event()

    sm = SpaceMouse(on_disconnect=lambda: callback_invoked.set())
    # Simulate the SpaceMouse being connected
    with sm._lock:
        sm._connected = True
    sm._close_device()

    assert callback_invoked.is_set(), "on_disconnect callback was not called"


def test_disconnect_callback_not_called_when_already_disconnected():
    """_close_device should NOT invoke on_disconnect when already disconnected."""
    callback_invoked = threading.Event()

    sm = SpaceMouse(on_disconnect=lambda: callback_invoked.set())
    # _connected is False by default — closing again shouldn't trigger callback
    sm._close_device()

    assert not callback_invoked.is_set()


def test_close_device_resets_state_to_zero():
    """State should be reset to all zeros when the device is closed."""
    sm = SpaceMouse()
    # Simulate having received some data
    with sm._lock:
        sm._connected = True
        sm._state["x"] = 500
        sm._state["ry"] = -200
        sm._state["buttons"] = 3

    sm._close_device()
    state = sm.get_state()

    for key, val in state.items():
        assert val == 0, f"Expected {key} to be 0 after close, got {val}"


# ------------------------------------------------------------------
# Controller detection
# ------------------------------------------------------------------


def test_detect_controller_type_spacemouse_by_name():
    """SpaceMouse should be recognized by name markers."""
    sm_name = CONSTANTS.SPACEMOUSE.NAME
    assert detect_controller_type("3Dconnexion SpaceMouse Wireless") == sm_name
    assert detect_controller_type("SpaceMouse Pro") == sm_name
    assert detect_controller_type("3DConnexion Space Mouse") == sm_name


def test_detect_controller_type_spacemouse_not_xbox():
    """SpaceMouse should never fall through to Xbox detection."""
    result = detect_controller_type("3Dconnexion SpaceMouse Wireless")
    assert result != CONSTANTS.XBOX.NAME
    assert result == CONSTANTS.SPACEMOUSE.NAME
