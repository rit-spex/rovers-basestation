"""Arm keyboard mode and press-state tests."""

from basestation.keyboard import (
    ARM_STATE_SIGNALS, HELD, JUST_PRESSED, JUST_RELEASED, NOT_PRESSED, Keyboard)


def _keyboard():
    """Keyboard with release debounce disabled for deterministic tests."""
    kb = Keyboard()
    kb._release_debounce = 0.0
    return kb


def _state(kb, action):
    return kb.get_arm_state()[ARM_STATE_SIGNALS[action]]


def test_arm_mode_emits_action_states():
    kb = _keyboard()
    kb.set_mode("arm")
    assert set(kb.get_arm_state().values()) == {NOT_PRESSED}

    kb.press_arm("flip")
    assert _state(kb, "flip") == JUST_PRESSED
    assert _state(kb, "flip") == HELD

    kb.release_arm("flip")
    assert _state(kb, "flip") == JUST_RELEASED
    assert _state(kb, "flip") == NOT_PRESSED


def test_arm_states_are_independent():
    kb = _keyboard()
    kb.set_mode("arm")
    kb.press_arm("flip")
    kb.press_arm("toggle_joint_lock:0")

    states = kb.get_arm_state()
    assert states[ARM_STATE_SIGNALS["flip"]] == JUST_PRESSED
    assert states[ARM_STATE_SIGNALS["toggle_joint_lock:0"]] == JUST_PRESSED

    kb.release_arm("flip")
    states = kb.get_arm_state()
    assert states[ARM_STATE_SIGNALS["flip"]] == JUST_RELEASED
    assert states[ARM_STATE_SIGNALS["toggle_joint_lock:0"]] == HELD


def test_arm_states_zero_outside_arm_mode():
    kb = _keyboard()
    kb.set_mode("arm")
    kb.press_arm("flip")
    assert _state(kb, "flip") == JUST_PRESSED

    kb.set_mode("life")
    assert set(kb.get_arm_state().values()) == {NOT_PRESSED}


def test_signal_names_are_topic_safe():
    for action, signal in ARM_STATE_SIGNALS.items():
        assert ":" not in signal, action
        assert signal.replace("_", "").isalnum(), action
    assert len(set(ARM_STATE_SIGNALS.values())) == len(ARM_STATE_SIGNALS)


def test_arm_signals_match_protocol():
    from basestation.protocol import CONSTANTS, MessageEncoder

    encoder = MessageEncoder()
    defined = list(
        encoder.get_messages()[CONSTANTS.COMPACT_MESSAGES.ARM_STATE_ID]["values"]
    )
    assert defined == list(ARM_STATE_SIGNALS.values())


def test_quick_tap_reports_press_then_release():
    kb = _keyboard()
    kb.set_mode("arm")
    kb.press_arm("toggle_joint_lock:0")
    kb.release_arm("toggle_joint_lock:0")

    # The press must not be lost even though it ended before the next read.
    assert _state(kb, "toggle_joint_lock:0") == JUST_PRESSED
    assert _state(kb, "toggle_joint_lock:0") == JUST_RELEASED
    assert _state(kb, "toggle_joint_lock:0") == NOT_PRESSED


def test_release_debounce_absorbs_a_bouncy_key():
    kb = _keyboard()
    kb._release_debounce = 0.05
    kb.set_mode("arm")
    kb.press_arm("toggle_position_lock")
    assert _state(kb, "toggle_position_lock") == JUST_PRESSED

    # A bouncy keyboard emits release then press while the key is held.
    kb.release_arm("toggle_position_lock")
    kb.press_arm("toggle_position_lock")

    # The action must never look released, otherwise the rover sees a
    # second "just pressed" and toggles the lock twice.
    assert _state(kb, "toggle_position_lock") == HELD


def test_release_is_held_for_the_debounce_window():
    kb = _keyboard()
    kb._release_debounce = 0.05
    kb.set_mode("arm")
    kb.press_arm("home")
    assert _state(kb, "home") == JUST_PRESSED

    kb.release_arm("home")
    assert _state(kb, "home") == HELD

    kb._release_debounce = 0.0
    assert _state(kb, "home") == JUST_RELEASED
    assert _state(kb, "home") == NOT_PRESSED
