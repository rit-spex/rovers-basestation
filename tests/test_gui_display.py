# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : test_gui_display.py
# purpose       : display freshness rules (no Tk widget required)
# created on    : 11/16/2026
# ------------------------------------------------------------------
"""Basestation tab freshness: local input state must not blank out while
the rover has not sent telemetry yet."""

from types import SimpleNamespace

from basestation.gui import (GRAY, RED, TELEMETRY_TIMEOUT, Display,
                             telemetry_stale)

NOW = 1000.0


def test_no_telemetry_ever_is_not_stale():
    # The pad/keyboard/devices and link status must stay visible while the
    # rover is connected but silent; only stale rover data is cleared.
    assert not telemetry_stale({}, NOW)


def test_fresh_telemetry_is_not_stale():
    assert not telemetry_stale({"_received_at": NOW - 0.1}, NOW)


def test_telemetry_that_went_quiet_is_stale():
    old = NOW - TELEMETRY_TIMEOUT - 0.1
    assert telemetry_stale({"_received_at": old}, NOW)


def test_non_numeric_received_at_is_ignored():
    assert not telemetry_stale({"_received_at": None}, NOW)
    assert not telemetry_stale({"_received_at": "not a timestamp"}, NOW)


def _cells(line):
    return [cell.strip() for cell in line.split("|")[1:-1]]


def test_xbox_table_puts_button_pairs_in_left_right_columns():
    lines = Display._xbox_table({
        "AXIS_LY": 100, "AXIS_RY": 150,
        "A": True, "B": False, "X": False, "Y": True,
        "LEFT_BUMPER": False, "RIGHT_BUMPER": True,
        "AXIS_LT": True, "AXIS_RT": False,
    })
    assert len(set(map(len, lines))) == 1  # all rows padded alike
    assert _cells(lines[0]) == ["Axis", "Left", "Right"]
    assert _cells(lines[1]) == ["Sticks", "100", "150"]
    assert _cells(lines[2]) == ["A/B", "X", "-"]
    assert _cells(lines[3]) == ["X/Y", "-", "X"]
    assert _cells(lines[4]) == ["Bumpers", "-", "X"]
    assert _cells(lines[5]) == ["Triggers", "X", "-"]


class FakeWidget:
    def __init__(self, text=""):
        self.options = {"text": text}
        self.background = None

    def config(self, **kwargs):
        self.options.update({k: v for k, v in kwargs.items() if k == "text"})
        if "background" in kwargs:
            self.background = kwargs["background"]

    def cget(self, key):
        return self.options.get(key)


def test_reset_display_clears_sidebar_and_module_panel():
    """Stale telemetry must clear rover state but keep local input devices."""
    text_writes = []
    resets = []
    display = SimpleNamespace(
        _indicators={"Rover": FakeWidget()},
        _indicator_labels={"Rover": FakeWidget("OK")},
        speed_boxes={25: FakeWidget()},
        mode_boxes={0: FakeWidget()},
        comm_label=FakeWidget("Connected"),
        updates_label=FakeWidget("Updates: 9"),
        devices_text=FakeWidget("Xbox Wireless Controller:"),
        module_text=FakeWidget("Arm Module data"),
        module_frame=FakeWidget("Arm Module"),
        _module_view="arm",
        _view_override="arm",
        simulation=True,
        _view_var=FakeWidget("Arm"),
        _set_text=lambda widget, content: text_writes.append((widget, content)),
        arm_panel=SimpleNamespace(reset=lambda: resets.append(True)),
    )

    Display._reset_display(display)

    # Far-left status reset.
    assert display._indicators["Rover"].background == RED
    assert display._indicator_labels["Rover"].cget("text") == ""
    assert display.speed_boxes[25].background == GRAY
    assert display.mode_boxes[0].background == GRAY
    assert display.comm_label.cget("text") == "-"
    assert display.updates_label.cget("text") == "Updates: 0"

    # The rover-derived module panel resets and drops its cached state.
    assert text_writes == [
        (display.module_text, "Waiting for rover telemetry...")]
    assert display.module_frame.cget("text") == "Module Info"
    assert resets == [True]

    # Local input device content is preserved.
    assert display.devices_text.cget("text") == "Xbox Wireless Controller:"
