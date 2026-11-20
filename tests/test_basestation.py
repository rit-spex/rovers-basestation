# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : test_basestation.py
# purpose       : wire-format and behavior checks for the basestation
# created on    : 7/12/2026 - Ryan
# last modified : 10/1/2026 - Zach
# ------------------------------------------------------------------
"""The tests that matter: bytes on the wire, input math, and quit paths.

Golden byte strings were derived from protocol.yaml by hand; if these
fail after a protocol change, update the goldens on purpose.
"""

import pytest

import threading
import time
from types import SimpleNamespace

from basestation.app import (AXIS_LY, AXIS_RY, HEARTBEAT_PERIOD,
                             RELEASE_BURST_FRAMES, BaseStation, StreamGate,
                             arm_wire_state, xbox_wire_values)
from basestation.comms import Link
from basestation.gamepads import N64, XBOX, Gamepads, detect_type
from basestation.keyboard import (ARM_STATE_SIGNALS, HELD, JUST_PRESSED,
                                  JUST_RELEASED, NOT_PRESSED, Keyboard)
from basestation.protocol import CONSTANTS, MSG, MessageEncoder

ENCODER = MessageEncoder()


def make_gamepads(**kwargs):
    return Gamepads(scan=False, **kwargs)


# ----------------------------------------------------------------------
# Wire format
# ----------------------------------------------------------------------

def test_neutral_states_encode_to_known_bytes():
    states, _ = make_gamepads().snapshot()
    assert ENCODER.encode_data(states[XBOX], MSG.XBOX_ID).hex() == "0264645555"
    assert ENCODER.encode_data(states[N64], MSG.N64_ID).hex() == "0355555540"
    assert ENCODER.encode_data({"timestamp": 0}, MSG.HEARTBEAT_ID).hex() == "010000"
    assert ENCODER.encode_data({}, MSG.QUIT_ID).hex() == "0480"
    assert ENCODER.encode_data({"auto_state": 3}, MSG.AUTO_STATE_ID).hex() == "0503"


def test_button_and_trigger_reach_the_wire():
    pads = make_gamepads()
    pads.handle_event(XBOX, "BTN_SOUTH", 1)   # A pressed
    pads.handle_event(XBOX, "ABS_Z", 200)     # left trigger pulled
    states, _ = pads.snapshot()
    payload = ENCODER.encode_data(states[XBOX], MSG.XBOX_ID)
    # A -> 2 in the first 2-bit slot, AXIS_LT -> 2 in the seventh slot
    assert payload.hex() == "0264649559"


def test_arm_pose_encodes_to_known_bytes():
    pose = {"pose_x": 1234, "pose_y": -500, "pose_z": 650,
            "pose_roll": 100, "pose_pitch": -200, "pose_yaw": 9000}
    payload = ENCODER.encode_data(pose, MSG.ARM_POSE_ID)
    assert payload.hex(" ") == "f7 04 d2 fe 0c 02 8a 00 64 ff 38 23 28"

    decoded, message_id = ENCODER.decode_data(payload)
    assert message_id == MSG.ARM_POSE_ID
    assert decoded == pose


def test_spacemouse_and_keyboard_encode():
    sm = {"x": -100, "y": 50, "z": 0, "rx": 1, "ry": -1, "rz": 32767, "buttons": 3}
    assert ENCODER.encode_data(sm, MSG.SPACEMOUSE_ID).hex(" ") == \
        "06 ff 9c 00 32 00 00 00 01 ff ff 7f ff 00 03"
    kb = Keyboard.life_zero_state() | {"enable_science": 1, "pump_1": 2}
    assert ENCODER.encode_data(kb, MSG.KEYBOARD_ID).hex(" ") == \
        "07 01 00 00 00 00 00 02 00 00 00 00 00 00 00 00"

    # Arm actions are per-action press states, not a key bitmask.
    arm = Keyboard().get_arm_state()
    arm["flip"] = 1
    assert ENCODER.encode_data(arm, MSG.ARM_STATE_ID).hex(" ") == (
        "08 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
        "00 00 00 00")


def test_lock_all_is_removed_before_encoding():
    state = Keyboard().get_arm_state(include_local=True)
    state["lock_all_joints"] = JUST_PRESSED
    wire = arm_wire_state(state, 0b11111)
    assert "lock_all_joints" not in wire
    assert set(wire) == set(ARM_STATE_SIGNALS.values())


def test_lock_all_expands_to_the_unlocked_joint_toggles():
    state = dict.fromkeys(ARM_STATE_SIGNALS.values(), NOT_PRESSED)
    state["lock_all_joints"] = JUST_PRESSED

    # Joints 0 and 2 are already locked, so L must not toggle those.
    wire = arm_wire_state(state, 0b00101)
    assert "lock_all_joints" not in wire
    for index, pressed in enumerate((False, True, False, True, True)):
        signal = ARM_STATE_SIGNALS[f"toggle_joint_lock:{index}"]
        assert wire[signal] == (JUST_PRESSED if pressed else NOT_PRESSED)


def test_lock_all_with_all_joints_locked_sends_no_pulses():
    state = dict.fromkeys(ARM_STATE_SIGNALS.values(), NOT_PRESSED)
    state["lock_all_joints"] = JUST_PRESSED

    wire = arm_wire_state(state, 0b11111)
    assert set(wire.values()) == {NOT_PRESSED}


def test_lock_all_without_telemetry_is_ignored():
    state = dict.fromkeys(ARM_STATE_SIGNALS.values(), NOT_PRESSED)
    state["lock_all_joints"] = JUST_PRESSED

    wire = arm_wire_state(state, None)
    assert set(wire.values()) == {NOT_PRESSED}


# ----------------------------------------------------------------------
# Stick math
# ----------------------------------------------------------------------

def test_stick_deadband_speed_and_clamp():
    pads = make_gamepads()
    pads.drive_speed = 100

    pads.handle_event(XBOX, "ABS_Y", 32767)   # full deflection
    assert pads.states[XBOX]["AXIS_LY"] == 200

    pads.handle_event(XBOX, "ABS_Y", -32768)
    assert pads.states[XBOX]["AXIS_LY"] == 0

    pads.handle_event(XBOX, "ABS_Y", 2000)    # inside 10% deadband
    assert pads.states[XBOX]["AXIS_LY"] == 100

    pads.drive_speed = 25                     # scales to 25%
    pads.handle_event(XBOX, "ABS_Y", 32767)
    assert pads.states[XBOX]["AXIS_LY"] == 125

    pads.drive_speed = 100
    pads.reverse_mode = True                  # reverse negates
    pads.handle_event(XBOX, "ABS_Y", 32767)
    assert pads.states[XBOX]["AXIS_LY"] == 0

    # floor boundary raws where raw/32767 scaling would be off by one
    # against the old basestation, just for b4b wire compat
    pads.reverse_mode = False
    pads.handle_event(XBOX, "ABS_Y", -32440)
    assert pads.states[XBOX]["AXIS_LY"] == 1
    pads.drive_speed = 25
    pads.handle_event(XBOX, "ABS_Y", -31129)
    assert pads.states[XBOX]["AXIS_LY"] == 76


def test_reverse_mode_swaps_sticks_on_the_wire():
    state = {"AXIS_LY": 150, "AXIS_RY": 50}
    swapped = xbox_wire_values(state, reverse=True)
    assert swapped["AXIS_LY"] == 50 and swapped["AXIS_RY"] == 150
    assert xbox_wire_values(state, reverse=False) is state


# ----------------------------------------------------------------------
# Modes, auto state, quit
# ----------------------------------------------------------------------

def test_mode_combos():
    pads = make_gamepads()
    assert pads.drive_speed == 25
    pads.handle_event(XBOX, "BTN_SELECT", 1)
    pads.handle_event(XBOX, "ABS_HAT0Y", -1)  # up
    assert pads.reverse_mode is True
    pads.handle_event(XBOX, "ABS_HAT0Y", 1)   # down
    assert pads.reverse_mode is False
    pads.handle_event(XBOX, "BTN_SELECT", 0)

    pads.handle_event(XBOX, "BTN_START", 1)
    pads.handle_event(XBOX, "ABS_HAT0Y", 1)
    assert pads.drive_speed == 25
    pads.handle_event(XBOX, "ABS_HAT0Y", -1)
    assert pads.drive_speed == 25

    pads.handle_event(XBOX, "ABS_HAT0X", -1)
    pads.handle_event(XBOX, "ABS_HAT0X", 0)
    pads.handle_event(XBOX, "ABS_HAT0X", -1)
    assert pads.drive_speed == 0

    speeds = []
    for _ in range(6):
        pads.handle_event(XBOX, "ABS_HAT0X", 0)
        pads.handle_event(XBOX, "ABS_HAT0X", 1)
        speeds.append(pads.drive_speed)
    assert speeds == [25, 50, 75, 100, 100, 100]


def test_drive_speed_recalc_held_stick():
    pads = make_gamepads()
    pads.handle_event(XBOX, "ABS_Y", 32767)
    assert pads.states[XBOX]["AXIS_LY"] == 125

    pads.handle_event(XBOX, "BTN_START", 1)
    pads.handle_event(XBOX, "ABS_HAT0X", 1)
    assert pads.drive_speed == 50
    assert pads.states[XBOX]["AXIS_LY"] == 150


def test_auto_state_bumpers_clamp():
    pads = make_gamepads()
    pads.handle_event(XBOX, "BTN_START", 1)
    for _ in range(10):
        pads.handle_event(XBOX, "BTN_TR", 1)
        pads.handle_event(XBOX, "BTN_TR", 0)
    assert pads.auto_state == CONSTANTS.AUTO_STATE.MAX
    for _ in range(10):
        pads.handle_event(XBOX, "BTN_TL", 1)
        pads.handle_event(XBOX, "BTN_TL", 0)
    assert pads.auto_state == 0


def test_quit_buttons():
    quits = []
    pads = make_gamepads(on_quit=lambda: quits.append(1))
    pads.handle_event(XBOX, "BTN_MODE", 1)   # Xbox home
    pads.handle_event(N64, "BTN_START", 1)   # N64 start
    assert len(quits) == 2


def test_n64_dpad_maps_to_buttons():
    pads = make_gamepads()
    pads.handle_event(N64, "ABS_HAT0Y", -1)
    assert pads.states[N64]["DP_UP"] is True
    assert pads.states[N64]["DP_DOWN"] is False
    pads.handle_event(N64, "ABS_HAT0X", 1)
    assert pads.states[N64]["DP_RIGHT"] is True


def test_detect_type():
    assert detect_type("Xbox Wireless Controller") == XBOX
    assert detect_type("Retrolink N64 DInput") == N64
    assert detect_type("3Dconnexion SpaceMouse Wireless") == "spacemouse"
    assert detect_type("Mystery Pad") is None


# ----------------------------------------------------------------------
# Keyboard state machine
# ----------------------------------------------------------------------

def test_keyboard_press_hold_release_cycle():
    kb = Keyboard()
    kb._release_debounce = 0.0  # no debounce wait in tests
    kb._press_life("pump_1")
    assert kb.get_life_state()["pump_1"] == JUST_PRESSED
    assert kb.get_life_state()["pump_1"] == HELD
    kb._release_life("pump_1")
    assert kb.get_life_state()["pump_1"] == JUST_RELEASED
    assert kb.get_life_state()["pump_1"] == NOT_PRESSED


def test_keyboard_release_debounce_cancels_bounce():
    kb = Keyboard()
    kb._press_life("pump_1")
    kb.get_life_state()
    kb._release_life("pump_1")
    kb._press_life("pump_1")  # bounce within the debounce window
    assert kb.get_life_state()["pump_1"] == HELD  # release was cancelled


def test_keyboard_scan_failure_is_unknown_not_disconnect(monkeypatch):
    import basestation.keyboard as kbmod

    class Boom:
        def DeviceManager(self):
            raise RuntimeError("transient enumeration failure")

    monkeypatch.setattr(kbmod, "inputs", Boom())
    assert Keyboard._scan_keyboards() is None  # not False: must not fake unplug


# ----------------------------------------------------------------------
# Link duplicate suppression
# ----------------------------------------------------------------------

def test_headless_refuses_silent_simulation_fallback(monkeypatch):
    import pytest

    monkeypatch.setenv("XBEE_NO_GUI", "1")
    monkeypatch.delenv("BASESTATION_SIMULATION", raising=False)
    monkeypatch.setattr(Link, "_open_xbee", lambda self: False)
    with pytest.raises(SystemExit):
        Link()  # dead radio on the field Pi must be loud, not simulated

    monkeypatch.setenv("BASESTATION_SIMULATION", "1")
    link = Link()  # explicitly requested simulation is still allowed obv
    assert link.simulation
    link.close()


def test_early_rx_during_connect_does_not_crash(monkeypatch):
    # xbee telemetry can arrive the moment _open_xbee sees the data
    # callback before __init__ finishes, this must not blow up rx
    packet = ENCODER.encode_data({"rover_estop": True}, MSG.ROVER_ESTOP_ID)
    received = []

    def fake_open_xbee(self):
        self._handle_telemetry(packet)  # callback fires mid-connect
        return True

    monkeypatch.setattr(Link, "_open_xbee", fake_open_xbee)
    link = Link(on_telemetry=received.append)
    assert received and received[0]["rover_estop"] is True
    link.close()


def test_truncated_telemetry_is_dropped_not_misdecoded():
    link = Link(connect=False)
    received = []
    link._on_telemetry = received.append

    full = ENCODER.encode_data({}, MSG.ARM_ENCODERS_ID)
    link._handle_telemetry(full)
    assert len(received) == 1

    # stale protocol rover sends 11 byte arm_encoders packets. The codec
    # zero pads short reads, so without a length guard this would silently
    # decode into wrong joint angles instead of being rejected like it should
    link._handle_telemetry(full[:11])
    assert len(received) == 1  # dropped, not delivered as garbage


def test_arm_status_updates_mode_locks_and_flags():
    link = Link(connect=False)
    received = []
    link._on_telemetry = received.append

    status = {
        "arm_error_code": 0,
        "arm_error_arg": 0,
        "arm_error_seq": 7,
        "arm_operation_mode": 4,       # zenith
        "locked_joints": 0b11000,
        "homing_joints": 0b00001,
        "arm_flags": 1 << 7,           # zenith flag
    }
    payload = ENCODER.encode_data(status, MSG.ARM_STATUS_ID)
    assert len(payload) == 9
    link._handle_telemetry(payload)
    link.close()

    assert len(received) == 1
    assert received[0] == status | {"_message_name": "arm_status"}


def test_arm_status_fields_are_merged_into_telemetry():
    station = object.__new__(BaseStation)
    station.telemetry = {}
    station._telemetry_lock = threading.Lock()

    station._store_telemetry({
        "arm_operation_mode": 4,
        "locked_joints": 0b11000,
        "homing_joints": 0,
        "arm_flags": 1 << 7,
    })
    station._store_telemetry({"rover_estop": False})

    snap = station.telemetry_snapshot()
    assert snap["arm_operation_mode"] == 4
    assert snap["locked_joints"] == 0b11000
    assert snap["arm_flags"] == 1 << 7
    assert snap["rover_estop"] is False


def test_link_suppresses_duplicate_payloads():
    link = Link(connect=False)
    sent = []
    link._transmit = lambda payload: sent.append(payload) or True

    link.send(MSG.AUTO_STATE_ID, {"auto_state": 1})
    link.send(MSG.AUTO_STATE_ID, {"auto_state": 1})  # duplicate, suppressed
    link.send(MSG.AUTO_STATE_ID, {"auto_state": 2})
    assert len(sent) == 2

    link.send(MSG.HEARTBEAT_ID, {"timestamp": 5}, force=True)
    link.send(MSG.HEARTBEAT_ID, {"timestamp": 5}, force=True)
    assert len(sent) == 4  # force bypasses suppression


def test_heartbeat_runs_independently_of_control_loop():
    """The heartbeat must keep flowing even if cycle() never runs."""
    class FakeLink:
        def __init__(self):
            self.sent = []

        def send(self, message_id, values, force=False):
            self.sent.append((message_id, values, force))
            return True

    station = SimpleNamespace(
        link=FakeLink(),
        _quit=threading.Event(),
        _heartbeat_stop=threading.Event(),
    )
    thread = threading.Thread(
        target=BaseStation._heartbeat_loop, args=(station,), daemon=True)
    thread.start()
    time.sleep(HEARTBEAT_PERIOD * 2.5)
    station._heartbeat_stop.set()
    thread.join(timeout=1.0)
    heartbeats = [sent for sent in station.link.sent
                  if sent[0] == MSG.HEARTBEAT_ID]
    assert len(heartbeats) >= 2
    assert all(sent[2] for sent in heartbeats)  # force=True


class _IdleSpaceMouse:
    def get_state(self):
        return dict.fromkeys(CONSTANTS.SPACEMOUSE.ALL_AXES, 0)


def make_station(pads, link, keyboard=None):
    station = object.__new__(BaseStation)
    station.gamepads = pads
    station.spacemouse = _IdleSpaceMouse()
    station.keyboard = keyboard or Keyboard()
    station.link = link
    station.telemetry_snapshot = lambda: {}
    station._gates = {name: StreamGate() for name in (
        "xbox", "spacemouse", "keyboard", "arm_state", "auto_state")}
    station._last_auto_state = None
    return station


def capture_link():
    link = Link(connect=False)
    sent = []
    link._transmit = lambda payload: sent.append(payload) or True
    return link, sent


def frames_for(sent, message_id):
    return [p for p in sent if p and p[0] == message_id]


def test_idle_link_sends_no_repeated_state():
    """Idle inputs must not occupy the shared radio channel.

    Only the first cycle sends (the initial state, plus the initial auto-state
    edge and its burst).  After that every idle stream is silent.
    """
    link, sent = capture_link()
    station = make_station(make_gamepads(), link)
    for _ in range(RELEASE_BURST_FRAMES + 3):
        station.cycle()
    before = len(sent)
    for _ in range(50):
        station.cycle()
    assert len(sent) == before
    link.close()


def test_release_sends_zero_burst_then_goes_quiet():
    """A released stick publishes explicit zero drive, then stops sending.

    The chassis latches the last drive command, so the release itself must
    reach it.  The basestation sends the neutral state for a short burst, then
    goes quiet so an autonomous drive source is not fought by neutral frames.
    """
    pads = make_gamepads()
    link, sent = capture_link()
    station = make_station(pads, link)

    station.cycle()
    assert len(frames_for(sent, MSG.XBOX_ID)) == 1

    pads.handle_event(XBOX, "ABS_Y", 32767)
    station.cycle()
    station.cycle()
    assert len(frames_for(sent, MSG.XBOX_ID)) == 3
    held = ENCODER.decode_data(frames_for(sent, MSG.XBOX_ID)[-1])[0]
    assert held[AXIS_LY] > 0.0

    pads.handle_event(XBOX, "ABS_Y", 0)
    for _ in range(RELEASE_BURST_FRAMES + 3):
        station.cycle()
    neutral = [ENCODER.decode_data(p)[0]
               for p in frames_for(sent, MSG.XBOX_ID)[3:]]
    assert len(neutral) == RELEASE_BURST_FRAMES
    assert all(f[AXIS_LY] == 0.0 and f[AXIS_RY] == 0.0 for f in neutral)
    link.close()


def test_arm_edge_once_held_streams_release_bursts():
    """Press edges go out once, held jogs stream, and releases are repeated.

    The rover acts on the just-pressed edge, so re-sending it would toggle
    twice.  A held action must keep streaming or the gripper jog times out.
    """
    keyboard = Keyboard()
    keyboard._release_debounce = 0.0
    keyboard.set_mode("arm")
    link, sent = capture_link()
    station = make_station(make_gamepads(), link, keyboard=keyboard)

    keyboard.press_arm("flip")
    station.cycle()
    edges = [ENCODER.decode_data(p)[0] for p in frames_for(sent, MSG.ARM_STATE_ID)]
    assert edges and edges[-1]["flip"] == 1
    keyboard.release_arm("flip")
    for _ in range(RELEASE_BURST_FRAMES + 2):
        station.cycle()

    link_frames = len(frames_for(sent, MSG.ARM_STATE_ID))
    keyboard.press_arm("gripper_up")
    for _ in range(4):
        station.cycle()
    held = [ENCODER.decode_data(p)[0]
            for p in frames_for(sent, MSG.ARM_STATE_ID)[link_frames:]]
    assert len(held) >= 4
    assert all(f["gripper_up"] != 0 for f in held[-4:])

    before = len(frames_for(sent, MSG.ARM_STATE_ID))
    keyboard.release_arm("gripper_up")
    for _ in range(10):
        station.cycle()
    after = len(frames_for(sent, MSG.ARM_STATE_ID)) - before
    assert after == RELEASE_BURST_FRAMES + 1  # JUST_RELEASED + burst of idle
    link.close()


def test_auto_state_change_is_sent_then_repeated_briefly():
    pads = make_gamepads()
    link, sent = capture_link()
    station = make_station(pads, link)
    for _ in range(RELEASE_BURST_FRAMES + 3):
        station.cycle()
    settled = len(frames_for(sent, MSG.AUTO_STATE_ID))
    for _ in range(RELEASE_BURST_FRAMES + 5):
        station.cycle()
    assert len(frames_for(sent, MSG.AUTO_STATE_ID)) == settled

    pads.auto_state = pads.auto_state + 1
    station.cycle()
    for _ in range(RELEASE_BURST_FRAMES + 5):
        station.cycle()
    changed = frames_for(sent, MSG.AUTO_STATE_ID)[settled:]
    assert len(changed) == RELEASE_BURST_FRAMES + 1
    assert all(ENCODER.decode_data(p)[0]["auto_state"] == pads.auto_state
               for p in changed)
    link.close()


def test_repeated_device_manager_keeps_type_codes():
    """inputs 0.5 drains EVENT_MAP's type_codes generator on first use.

    The hotplug monitors rebuild DeviceManager every 0.5 s; without the
    repair in basestation/__init__.py the second one has an empty
    type_codes and get_typecode('LED') raises KeyError on Linux.
    """
    inputs = pytest.importorskip("inputs")
    for _ in range(3):
        assert inputs.DeviceManager().get_typecode("LED") == 0x11
