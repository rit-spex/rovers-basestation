"""Arm panel rendering helpers (no Tk widget required)."""

import time

from basestation.gui_arm_elements import (ArmPanel, arm_keyboard_lines,
                                          arm_pose_lines, teleop_active,
                                          text_table)


class FakeText:
    """The parts of a tkinter Text widget that ArmPanel touches."""

    def __init__(self):
        self.parts = []
        self.tags = {}

    def configure(self, **_kwargs):
        pass

    def tag_configure(self, name, **kwargs):
        self.tags[name] = kwargs

    def config(self, **_kwargs):
        pass

    def yview(self):
        return (0.0, 1.0)

    def yview_moveto(self, _value):
        pass

    def yview_scroll(self, _units, _what):
        pass

    def index(self, _index):
        return "1.0"

    def see(self, _index):
        pass

    def update_idletasks(self):
        pass

    def delete(self, *_args):
        self.parts.clear()

    def insert(self, _index, text, _tags=()):
        self.parts.append(text)

    def text(self):
        return "".join(self.parts)


def live_telemetry(**extra):
    telemetry = {
        "arm_base_position": 0,
        "shoulder_position": 0,
        "elbow_position": 0,
        "wrist_bend_position": 0,
        "wrist_twist_position": 0,
        "_received_at": time.time(),
    }
    telemetry.update(extra)
    return telemetry


def test_text_table_columns_line_up():
    lines = text_table(("Axis", "X", "Y"),
                       [("Trans", 1, 22), ("Rot", -3, 0)])
    assert len(set(map(len, lines))) == 1  # every row is padded alike
    assert "Axis" in lines[0] and "Trans" in lines[1] and "22" in lines[1]


def test_pose_table_waits_for_rover_telemetry():
    lines = arm_pose_lines({})
    assert len(lines) == 3
    assert "--" in lines[1] and "--" in lines[2]


def test_pose_table_uses_rover_telemetry():
    telemetry = {
        "pose_x": 1234, "pose_y": -500, "pose_z": 650,
        "pose_roll": 100, "pose_pitch": -200, "pose_yaw": 9000,
    }
    lines = arm_pose_lines(telemetry)
    assert "12.3" in lines[1] and "-5.0" in lines[1] and "6.5" in lines[1]
    assert "1.0" in lines[2] and "-2.0" in lines[2] and "90.0" in lines[2]


def test_teleop_deadzone():
    assert teleop_active({"spacemouse": {"x": 9}})
    assert not teleop_active({"spacemouse": {"x": 8}})
    assert not teleop_active({})


def test_pose_angle_tables_are_compact():
    lines = arm_pose_lines({
        "pose_x": 1234, "pose_y": -500, "pose_z": 650,
        "pose_roll": 100, "pose_pitch": -200, "pose_yaw": 9000,
    })
    assert lines[0].startswith("|A|")
    assert lines[1].startswith("|T|")
    assert lines[2].startswith("|R|")
    assert "| A |" not in lines[0]
    assert len(set(map(len, lines))) == 1


def test_arm_keyboard_legend_marks_pressed_keys():
    lines = arm_keyboard_lines({"flip": True, "home": False})
    assert lines[0] == "Keyboard (Arm):"
    assert "    [F] [x] Flip" in lines
    assert "    [H] [ ] Home" in lines


def test_arm_keyboard_legend_uses_the_new_bindings():
    lines = arm_keyboard_lines({
        "joint_drive": False, "toggle_planar": False,
        "toggle_position_lock": True, "toggle_orientation_lock": False,
        "guide_orientation": True, "lock_all_joints": False,
    })
    assert "    [J] [ ] Joint" in lines
    assert "    [P] [ ] Planar" in lines
    assert "    [Q] [x] Pos Lock" in lines
    assert "    [O] [ ] Ori Lock" in lines
    assert "    [G] [x] Guide" in lines
    assert "    [L] [ ] Lock All" in lines


def test_arm_panel_reads_out_rest_action():
    widget = FakeText()
    panel = ArmPanel(widget)
    panel.draw(
        live_telemetry(locked_joints=0b11111),
        {"arm_keyboard": {"rest": True}})
    text = widget.text()
    assert "L     Lock All" not in text
    assert "R     Rest       [ON ]" in text
    assert "Lock All: L" in text and "Home: Shift+1-5" in text
    assert "Rest: R" not in text


def test_arm_panel_groups_follow_requested_order():
    widget = FakeText()
    panel = ArmPanel(widget)
    panel.draw(live_telemetry(), {})
    text = widget.text()
    assert "KEY   OPTION" not in text
    assert "ERROR: -----" in text
    positions = [text.index(title) for title in
                 ("Limit Types", "Drive Modes", "Actions", "Target Locks")]
    assert positions == sorted(positions)


def test_arm_panel_reads_out_zenith():
    widget = FakeText()
    panel = ArmPanel(widget)
    panel.draw(live_telemetry(arm_flags=1 << 7), {})
    text = widget.text()
    assert "Z     Zenith     [ON ]" in text


def test_arm_panel_drops_status_line_and_puts_pose_last():
    widget = FakeText()
    panel = ArmPanel(widget)
    panel.draw(live_telemetry(arm_flags=1 << 7), {})
    text = widget.text()
    assert "STATUS" not in text
    # The end-effector pose block is the last thing in the panel.
    assert text.rindex("END EFFECTOR POSE") > text.rindex("ARM TELEMETRY")
    assert text.rstrip().splitlines()[-1].startswith("|R|")


def test_error_banner_shows_text_then_expires():
    widget = FakeText()
    panel = ArmPanel(widget)
    panel.draw(live_telemetry(arm_error_code=1, arm_error_arg=5,
                              arm_error_seq=1), {})
    assert "Octant 5 requires Planar" in widget.text()

    # Same sequence number: the banner is not re-stamped, so it ages out.
    panel._error_at -= 10
    panel.draw(live_telemetry(arm_error_code=1, arm_error_arg=5,
                              arm_error_seq=1, arm_flags=1), {})
    assert "Octant 5 requires Planar" not in widget.text()
    assert "--" in widget.text()  # the ERROR row is still there
