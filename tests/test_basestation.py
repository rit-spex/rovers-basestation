# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : test_basestation.py
# purpose       : wire-format and behavior checks for the basestation
# created on    : 7/12/2026 - Ryan
# last modified : 7/16/2026 - Ryan
# ------------------------------------------------------------------
"""The tests that matter: bytes on the wire, input math, and quit paths.

Golden byte strings were derived from protocol.yaml by hand; if these
fail after a protocol change, update the goldens on purpose.
"""

from basestation.app import xbox_wire_values
from basestation.comms import Link
from basestation.gamepads import N64, XBOX, Gamepads, detect_type
from basestation.keyboard import (HELD, JUST_PRESSED, JUST_RELEASED,
                                  NOT_PRESSED, Keyboard)
from basestation.protocol import MSG, MessageEncoder

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


def test_spacemouse_and_keyboard_encode():
    sm = {"x": -100, "y": 50, "z": 0, "rx": 1, "ry": -1, "rz": 32767, "buttons": 3}
    assert ENCODER.encode_data(sm, MSG.SPACEMOUSE_ID).hex(" ") == \
        "06 ff 9c 00 32 00 00 00 01 ff ff 7f ff 00 03"
    kb = Keyboard.zero_state() | {"enable_science": 1, "pump_1": 2}
    assert ENCODER.encode_data(kb, MSG.KEYBOARD_ID).hex(" ") == \
        "07 01 00 00 00 00 00 02 00 00 00 00 00 00 00 00"


# ----------------------------------------------------------------------
# Stick math
# ----------------------------------------------------------------------

def test_stick_deadband_creep_and_clamp():
    pads = make_gamepads()
    pads.creep_mode = False

    pads.handle_event(XBOX, "ABS_Y", 32767)   # full deflection
    assert pads.states[XBOX]["AXIS_LY"] == 200

    pads.handle_event(XBOX, "ABS_Y", -32768)
    assert pads.states[XBOX]["AXIS_LY"] == 0

    pads.handle_event(XBOX, "ABS_Y", 2000)    # inside 10% deadband
    assert pads.states[XBOX]["AXIS_LY"] == 100

    pads.creep_mode = True                    # creep scales to 20%
    pads.handle_event(XBOX, "ABS_Y", 32767)
    assert pads.states[XBOX]["AXIS_LY"] == 120

    pads.creep_mode = False
    pads.reverse_mode = True                  # reverse negates
    pads.handle_event(XBOX, "ABS_Y", 32767)
    assert pads.states[XBOX]["AXIS_LY"] == 0

    # floor boundary raws where raw/32767 scaling would be off by one
    # against the old basestation, just for b4b wire compat
    pads.reverse_mode = False
    pads.handle_event(XBOX, "ABS_Y", -32440)
    assert pads.states[XBOX]["AXIS_LY"] == 1
    pads.creep_mode = True
    pads.handle_event(XBOX, "ABS_Y", -31129)
    assert pads.states[XBOX]["AXIS_LY"] == 81


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
    pads.handle_event(XBOX, "BTN_SELECT", 1)
    pads.handle_event(XBOX, "ABS_HAT0Y", -1)  # up
    assert pads.reverse_mode is True
    pads.handle_event(XBOX, "ABS_HAT0Y", 1)   # down
    assert pads.reverse_mode is False
    pads.handle_event(XBOX, "BTN_SELECT", 0)

    pads.handle_event(XBOX, "BTN_START", 1)
    pads.handle_event(XBOX, "ABS_HAT0Y", 1)
    assert pads.creep_mode is False
    pads.handle_event(XBOX, "ABS_HAT0Y", -1)
    assert pads.creep_mode is True


def test_auto_state_bumpers_clamp():
    pads = make_gamepads()
    for _ in range(10):
        pads.handle_event(XBOX, "BTN_TR", 1)
        pads.handle_event(XBOX, "BTN_TR", 0)
    assert pads.auto_state == 5
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
    kb._press("pump_1")
    assert kb.get_state()["pump_1"] == JUST_PRESSED
    assert kb.get_state()["pump_1"] == HELD
    kb._release("pump_1")
    assert kb.get_state()["pump_1"] == JUST_RELEASED
    assert kb.get_state()["pump_1"] == NOT_PRESSED


def test_keyboard_release_debounce_cancels_bounce():
    kb = Keyboard()
    kb._press("pump_1")
    kb.get_state()
    kb._release("pump_1")
    kb._press("pump_1")  # bounce within the debounce window
    assert kb.get_state()["pump_1"] == HELD  # release was cancelled


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