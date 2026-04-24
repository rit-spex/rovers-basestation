"""Tests for the KeyboardInput reader."""

import threading
import time
from unittest.mock import Mock, patch

from xbee.controller.keyboard import (
    _ALL_SIGNALS,
    HELD,
    JUST_PRESSED,
    JUST_RELEASED,
    NOT_PRESSED,
    KeyboardInput,
)

# ------------------------------------------------------------------
# Basic API
# ------------------------------------------------------------------


def test_get_state_returns_all_signals():
    kb = KeyboardInput()
    state = kb.get_state()
    assert set(state.keys()) == set(_ALL_SIGNALS)


def test_initial_state_values_are_zero():
    kb = KeyboardInput()
    state = kb.get_state()
    for sig, val in state.items():
        assert val == NOT_PRESSED, f"Expected {sig} to be 0, got {val}"


def test_is_connected_returns_false_initially():
    kb = KeyboardInput()
    assert kb.is_connected() is False


def test_get_key_bindings_returns_mapping():
    bindings = KeyboardInput.get_key_bindings()
    assert isinstance(bindings, dict)
    assert "enable_science" in bindings
    assert bindings["enable_science"] == "q"


# ------------------------------------------------------------------
# State-machine transitions
# ------------------------------------------------------------------


def test_state_transitions_just_pressed_to_held():
    kb = KeyboardInput()
    with kb._lock:
        kb._state["enable_science"] = JUST_PRESSED
    state1 = kb.get_state()
    assert state1["enable_science"] == JUST_PRESSED
    # After get_state, JUST_PRESSED advances to HELD
    state2 = kb.get_state()
    assert state2["enable_science"] == HELD


def test_state_transitions_just_released_to_not_pressed():
    kb = KeyboardInput()
    with kb._lock:
        kb._state["enable_science"] = JUST_RELEASED
    state1 = kb.get_state()
    assert state1["enable_science"] == JUST_RELEASED
    # After get_state, JUST_RELEASED advances to NOT_PRESSED
    state2 = kb.get_state()
    assert state2["enable_science"] == NOT_PRESSED


# ------------------------------------------------------------------
# Device-monitor based connection tracking and disconnect callback
# ------------------------------------------------------------------


def _run_monitor_once(kb: KeyboardInput) -> None:
    """Trigger one iteration of the monitor loop then signal it to stop."""

    def stop_after_first_call(*_a, **_kw):
        kb._stop_event.set()

    with patch.object(kb, "_stop_event") as mock_stop:
        # First is_set call returns False (enter loop), wait then sets stop.
        mock_stop.is_set.side_effect = [False, True]
        mock_stop.wait.side_effect = stop_after_first_call
        kb._device_monitor_loop()


def test_monitor_marks_connected_when_keyboard_present():
    """Monitor should set _connected=True when inputs reports keyboards."""
    kb = KeyboardInput()
    fake_inputs = Mock()
    fake_inputs.DeviceManager.return_value = Mock(keyboards=[Mock()])
    fake_inputs.devices = fake_inputs.DeviceManager.return_value

    with patch("xbee.controller.keyboard.inputs_lib", fake_inputs):
        _run_monitor_once(kb)

    assert kb.is_connected() is True


def test_monitor_marks_disconnected_when_no_keyboard():
    """Monitor should set _connected=False when inputs reports no keyboards."""
    kb = KeyboardInput()
    with kb._lock:
        kb._connected = True
    fake_inputs = Mock()
    fake_inputs.DeviceManager.return_value = Mock(keyboards=[])
    fake_inputs.devices = fake_inputs.DeviceManager.return_value

    with patch("xbee.controller.keyboard.inputs_lib", fake_inputs):
        _run_monitor_once(kb)

    assert kb.is_connected() is False


def test_monitor_fires_disconnect_callback_on_unplug():
    """When keyboard goes from present -> absent, on_disconnect must fire."""
    callback = Mock()
    kb = KeyboardInput(on_disconnect=callback)
    with kb._lock:
        kb._connected = True
    fake_inputs = Mock()
    fake_inputs.DeviceManager.return_value = Mock(keyboards=[])
    fake_inputs.devices = fake_inputs.DeviceManager.return_value

    with patch("xbee.controller.keyboard.inputs_lib", fake_inputs):
        _run_monitor_once(kb)

    callback.assert_called_once()


def test_monitor_does_not_fire_disconnect_when_already_absent():
    """If keyboard was never present, disconnect callback should not fire."""
    callback = Mock()
    kb = KeyboardInput(on_disconnect=callback)
    fake_inputs = Mock()
    fake_inputs.DeviceManager.return_value = Mock(keyboards=[])
    fake_inputs.devices = fake_inputs.DeviceManager.return_value

    with patch("xbee.controller.keyboard.inputs_lib", fake_inputs):
        _run_monitor_once(kb)

    callback.assert_not_called()


# ------------------------------------------------------------------
# Tkinter integration
# ------------------------------------------------------------------


def test_bind_tkinter_marks_tkinter_bound():
    """bind_tkinter should record the binding without forcing _connected.

    The display state must reflect actual hardware presence (issue #25),
    so bind_tkinter no longer flips _connected on by itself.
    """
    kb = KeyboardInput()
    mock_root = Mock()
    kb.bind_tkinter(mock_root)
    assert kb._tkinter_bound is True
    mock_root.bind.assert_any_call("<KeyPress>", kb._on_tk_key_press)
    mock_root.bind.assert_any_call("<KeyRelease>", kb._on_tk_key_release)


def test_tkinter_key_press_updates_state():
    kb = KeyboardInput()
    mock_root = Mock()
    kb.bind_tkinter(mock_root)

    # Simulate tkinter key press for 'q' (enable_science)
    event = Mock()
    event.keysym = "q"
    kb._on_tk_key_press(event)

    state = kb.get_state()
    assert state["enable_science"] == JUST_PRESSED


def test_tkinter_key_release_updates_state():
    kb = KeyboardInput()
    mock_root = Mock()
    kb.bind_tkinter(mock_root)

    # Press then release 'q'
    press_event = Mock()
    press_event.keysym = "q"
    kb._on_tk_key_press(press_event)
    kb.get_state()  # Advance to HELD

    release_event = Mock()
    release_event.keysym = "q"
    kb._on_tk_key_release(release_event)

    state = kb.get_state()
    assert state["enable_science"] == JUST_RELEASED


def test_tkinter_unmapped_key_ignored():
    kb = KeyboardInput()
    mock_root = Mock()
    kb.bind_tkinter(mock_root)

    event = Mock()
    event.keysym = "F12"  # Not mapped
    kb._on_tk_key_press(event)

    state = kb.get_state()
    for val in state.values():
        assert val == NOT_PRESSED


# ------------------------------------------------------------------
# Read loop sustained error detection
# ------------------------------------------------------------------


def test_read_loop_breaks_on_sustained_errors_after_connection():
    """When inputs was active and errors pile up, the loop should break."""
    kb = KeyboardInput()
    kb._inputs_ever_connected = True

    # inputs.get_key always raises OSError
    with patch("xbee.controller.keyboard.inputs_lib") as mock_inputs:
        mock_inputs.get_key.side_effect = OSError("device gone")
        with patch("xbee.controller.keyboard.time") as mock_time:
            mock_time.sleep = Mock()  # Don't actually sleep
            # _read_loop should eventually break
            kb._read_loop()

    # Should have retried exactly max_consecutive_errors times
    assert mock_inputs.get_key.call_count == 10  # max_consecutive_errors


def test_read_loop_doesnt_break_when_never_connected():
    """When inputs never worked, errors should NOT break the loop (retry forever).
    Instead, they keep retrying until _stop_event is set."""
    kb = KeyboardInput()
    kb._inputs_ever_connected = False
    call_count = 0

    def fake_get_key():
        nonlocal call_count
        call_count += 1
        if call_count >= 15:
            kb._stop_event.set()  # Stop after 15 retries
        raise OSError("no device")

    with patch("xbee.controller.keyboard.inputs_lib") as mock_inputs:
        mock_inputs.get_key.side_effect = fake_get_key
        with patch("xbee.controller.keyboard.time") as mock_time:
            mock_time.sleep = Mock()
            kb._read_loop()

    # Should have kept retrying past 10 (max_consecutive_errors)
    assert call_count >= 15


# ------------------------------------------------------------------
# Release debounce (issue #24)
# ------------------------------------------------------------------


def _key_event(code: str, state: int):
    """Build a fake ``inputs`` library key event."""
    ev = Mock()
    ev.ev_type = "Key"
    ev.code = code
    ev.state = state
    return ev


def test_release_followed_by_press_keeps_held():
    """A spurious release immediately followed by a press must not show RELEASE.

    Some non-native keyboards emit release/press cycles while a key is held;
    the debounce window should swallow them and keep the key in HELD state.
    """
    kb = KeyboardInput()
    kb._process_event(_key_event("KEY_Q", 1))  # press
    kb.get_state()  # advance JUST_PRESSED -> HELD
    assert kb._state["enable_science"] == HELD

    # Spurious release followed immediately by a press from the noisy driver
    kb._process_event(_key_event("KEY_Q", 0))
    kb._process_event(_key_event("KEY_Q", 1))

    # No release should have been committed; key stays HELD
    state = kb.get_state()
    assert state["enable_science"] == HELD
    assert kb._keys_down["enable_science"] is True


def test_release_committed_after_debounce_window():
    """A real release with no follow-up press must eventually be reported."""
    kb = KeyboardInput()
    kb._release_debounce_seconds = 0.01  # short window for the test
    kb._process_event(_key_event("KEY_Q", 1))
    kb.get_state()  # HELD

    kb._process_event(_key_event("KEY_Q", 0))
    time.sleep(0.02)  # let debounce expire
    state = kb.get_state()
    assert state["enable_science"] == JUST_RELEASED


def test_repeat_event_cancels_pending_release():
    """A key-repeat (state=2) inside the window must keep the key HELD."""
    kb = KeyboardInput()
    kb._process_event(_key_event("KEY_Q", 1))
    kb.get_state()
    kb._process_event(_key_event("KEY_Q", 0))  # spurious release
    kb._process_event(_key_event("KEY_Q", 2))  # repeat (still held)

    state = kb.get_state()
    assert state["enable_science"] == HELD
    assert "enable_science" not in kb._pending_release
