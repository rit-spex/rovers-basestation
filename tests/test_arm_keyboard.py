"""Arm keyboard mode and press-state tests."""

from basestation.keyboard import (
    ARM_JOG_KEYS, ARM_KEY_MAP, ARM_STATE_SIGNALS, HELD, JUST_PRESSED,
    JUST_RELEASED, NOT_PRESSED, TK_ARM_JOG_KEYS, TK_ARM_KEY_MAP, Keyboard)


def _keyboard():
    """Keyboard with release debounce disabled for deterministic tests."""
    kb = Keyboard()
    kb._release_debounce = 0.0
    return kb


def _state(kb, action, include_local=False):
    state = kb.get_arm_state(include_local=include_local)
    return state[ARM_STATE_SIGNALS.get(action, action)]


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


def test_up_down_arrows_drive_the_gripper():
    assert ARM_KEY_MAP["KEY_UP"] == "gripper_up"
    assert ARM_KEY_MAP["KEY_DOWN"] == "gripper_down"
    assert TK_ARM_KEY_MAP["up"] == "gripper_up"
    assert TK_ARM_KEY_MAP["down"] == "gripper_down"
    assert Keyboard.key_for_arm("gripper_up") == "up"
    assert Keyboard.key_for_arm("gripper_down") == "down"


def test_arrows_no_longer_jog_the_shoulder():
    assert "KEY_UP" not in ARM_JOG_KEYS
    assert "KEY_DOWN" not in ARM_JOG_KEYS
    assert "up" not in TK_ARM_JOG_KEYS
    assert "down" not in TK_ARM_JOG_KEYS
    assert ARM_JOG_KEYS["KEY_LEFT"] == ("rz", 1)
    assert TK_ARM_JOG_KEYS["right"] == ("rz", -1)


def test_l_locks_all_joints_and_r_starts_rest_pipeline():
    assert ARM_KEY_MAP["KEY_L"] == "lock_all_joints"
    assert TK_ARM_KEY_MAP["l"] == "lock_all_joints"
    assert ARM_KEY_MAP["KEY_R"] == "rest"
    assert TK_ARM_KEY_MAP["r"] == "rest"
    assert Keyboard.key_for_arm("lock_all_joints") == "l"
    assert Keyboard.key_for_arm("rest") == "r"


def test_planar_and_target_lock_bindings():
    assert ARM_KEY_MAP["KEY_P"] == "toggle_planar"
    assert TK_ARM_KEY_MAP["p"] == "toggle_planar"
    assert ARM_KEY_MAP["KEY_Q"] == "toggle_position_lock"
    assert TK_ARM_KEY_MAP["q"] == "toggle_position_lock"
    assert ARM_KEY_MAP["KEY_O"] == "toggle_orientation_lock"
    assert TK_ARM_KEY_MAP["o"] == "toggle_orientation_lock"
    assert ARM_KEY_MAP["KEY_Z"] == "zenith"
    assert TK_ARM_KEY_MAP["z"] == "zenith"
    assert "KEY_X" not in ARM_KEY_MAP
    assert Keyboard.key_for_arm("toggle_planar") == "p"
    assert Keyboard.key_for_arm("toggle_position_lock") == "q"
    assert Keyboard.key_for_arm("toggle_orientation_lock") == "o"
    assert Keyboard.key_for_arm("zenith") == "z"


def test_holding_lock_all_sends_only_one_press():
    kb = _keyboard()
    kb.set_mode("arm")
    kb.press_arm("lock_all_joints")
    assert _state(kb, "lock_all_joints", include_local=True) == JUST_PRESSED

    # OS key repeat / a held key must not look like another lock command.
    kb.press_arm("lock_all_joints")
    assert _state(kb, "lock_all_joints", include_local=True) == HELD

    kb.release_arm("lock_all_joints")
    assert _state(kb, "lock_all_joints", include_local=True) == JUST_RELEASED
    assert _state(
        kb, "lock_all_joints", include_local=True) == NOT_PRESSED


def test_lock_all_is_basestation_only():
    assert "lock_all_joints" not in ARM_STATE_SIGNALS

    kb = _keyboard()
    kb.set_mode("arm")
    kb.press_arm("lock_all_joints")
    assert "lock_all_joints" not in kb.get_arm_state()

    local = _keyboard()
    local.set_mode("arm")
    local.press_arm("lock_all_joints")
    assert (local.get_arm_state(include_local=True)["lock_all_joints"]
            == JUST_PRESSED)


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
