"""Tests for the KeyboardInput reader."""

import threading
import time
from unittest.mock import Mock, patch

from xbee.controller.keyboard import (
    KeyboardInput,
    _ALL_SIGNALS,
    NOT_PRESSED,
    JUST_PRESSED,
    HELD,
    JUST_RELEASED,
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
# Disconnect callback – only when inputs was working
# ------------------------------------------------------------------


def test_disconnect_callback_called_when_inputs_was_active():
    """If inputs library was working and thread exits, callback fires."""
    callback = Mock()
    kb = KeyboardInput(on_disconnect=callback)
    kb._inputs_ever_connected = True
    # Simulate _run finishing without stop_event (device lost)
    kb._stop_event.clear()
    with kb._lock:
        kb._connected = True

    # Call the finally block logic manually via _run
    # We mock _read_loop to raise so _run's finally block runs
    with patch.object(kb, "_read_loop", side_effect=OSError("device gone")):
        kb._run()

    callback.assert_called_once()
    assert kb.is_connected() is False


def test_disconnect_callback_not_called_when_inputs_never_worked():
    """If inputs library never got an event (Windows laptop), no callback."""
    callback = Mock()
    kb = KeyboardInput(on_disconnect=callback)
    kb._inputs_ever_connected = False
    kb._stop_event.clear()

    # _read_loop raises immediately (inputs library fails)
    with patch.object(kb, "_read_loop", side_effect=OSError("no device")):
        kb._run()

    callback.assert_not_called()


def test_disconnect_callback_not_called_on_normal_shutdown():
    """Normal shutdown (stop_event set) should not fire disconnect callback."""
    callback = Mock()
    kb = KeyboardInput(on_disconnect=callback)
    kb._inputs_ever_connected = True
    kb._stop_event.set()  # Normal shutdown

    with patch.object(kb, "_read_loop"):
        kb._run()

    callback.assert_not_called()


# ------------------------------------------------------------------
# Tkinter integration
# ------------------------------------------------------------------


def test_bind_tkinter_sets_connected():
    kb = KeyboardInput()
    mock_root = Mock()
    kb.bind_tkinter(mock_root)
    assert kb.is_connected() is True
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
