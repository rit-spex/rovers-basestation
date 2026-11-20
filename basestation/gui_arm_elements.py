# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : gui_arm_elements.py
# purpose       : render the Arm module panel (joint table, pose, mode
#                 chips, error banner) and its shared text helpers
# ------------------------------------------------------------------
"""Arm-specific rendering for the basestation display.

``gui.Display`` hands the Arm telemetry to :class:`ArmPanel`, which owns
the text widget tags, the joint/pose tables, the option chips and the
command-rejection banner. Keeping it out of gui.py leaves that file with
the module routing and the non-arm panels.
"""

import logging
import time

from basestation.keyboard import Keyboard
from basestation.protocol import error_text

log = logging.getLogger(__name__)

# Arm telemetry bits (keep in sync with arm_route_planner_node.py).
ARM_FLAG_NAMES = (
    (0, "Home"),
    (1, "Flip"),
    (2, "Flipped"),
    (3, "Planar"),
    (4, "Joint"),
    (5, "PosLock"),
    (6, "OriLock"),
    (7, "Zenith"),
)
ARM_MODE_SHORT = {
    0: "PNP",
    1: "PNPF",
    2: "PLAN",
    3: "HOME",
    4: "ZEN",
}
ARM_MODE_TAGS = {
    0: "mode_pnp",
    1: "mode_pnpf",
    2: "mode_planar",
    3: "mode_home",
    4: "mode_zenith",
}
ARM_OPTION_KEYS = {
    "MODE": "V/P/H",
    "POSITION": "I",
    "PNP": "V",
    "HOME": "H",
    "FLIP": "F",
    "FLIPPED": "F",
    "PLANAR": "P",
    "ZENITH": "Z",
    "JOINT": "J",
    "POSLOCK": "Q",
    "ORILOCK": "O",
    "GUIDE": "G",
    "REST": "R",
    "GRIP": "-",
    "SOL": "-",
    "HOMING": "S+1-5",
    "ERROR": "",
}
ARM_JOINT_SHORT = ("B", "S", "E", "WB", "WT")
ARM_JOINTS = (
    ("Base", "arm_base_position"),
    ("Shldr", "shoulder_position"),
    ("Elbow", "elbow_position"),
    ("WstBnd", "wrist_bend_position"),
    ("WstTst", "wrist_twist_position"),
    ("Gripper", "gripper_position"),
)

# Human labels for the arm key legend in the devices panel.
ARM_ACTION_LABELS = {
    "flip": "Flip",
    "home": "Home",
    "position_drive": "Position",
    "joint_drive": "Joint",
    "pnp_normal": "PNP",
    "toggle_planar": "Planar",
    "zenith": "Zenith",
    "guide_orientation": "Guide",
    "toggle_position_lock": "Pos Lock",
    "toggle_orientation_lock": "Ori Lock",
    "lock_all_joints": "Lock All",
    "rest": "Rest",
    "solenoid_strike": "Solenoid",
    "gripper_up": "Grip Up",
    "gripper_down": "Grip Down",
}
for _index, _joint in enumerate(
        ("Base", "Shoulder", "Elbow", "Wrist Bend", "Wrist Twist")):
    ARM_ACTION_LABELS[f"toggle_joint_lock:{_index}"] = f"Lock {_joint}"
    ARM_ACTION_LABELS[f"home_joint:{_index}"] = f"Home {_joint}"

# The rover clears the code after the next successful command, so this is
# only a backstop for a dropped clear packet. One window for every code.
ARM_ERROR_HOLD_SECONDS = 5.0

# Arm encoder telemetry travels as centi-degrees in an INT_16.
ARM_ANGLE_KEYS = {
    "arm_base_position",
    "shoulder_position",
    "elbow_position",
    "wrist_bend_position",
    "wrist_twist_position",
    "gripper_position",
}


def text_table(headers, rows, indent="  ", min_width=4,
               compact_first=False) -> list[str]:
    """Bordered text table in the SpaceMouse readout style.

    ``headers`` is the header row and ``rows`` are (label, *values).
    Labels are left-aligned; headers and values are right-aligned in
    columns at least ``min_width`` characters wide.  ``compact_first``
    removes the padding around the first column so short row labels such
    as the pose table's A/T/R sit tight against the border.
    """
    label_width = max(
        min_width, len(str(headers[0])),
        *(len(str(row[0])) for row in rows))
    data_width = max(
        min_width,
        *(len(str(cell)) for row in rows for cell in row[1:]),
        *(len(str(header)) for header in headers[1:]),
    )

    def line(cells) -> str:
        values = [f"{str(cell):>{data_width}}" for cell in cells[1:]]
        if compact_first:
            return f"{indent}|{cells[0]}|" + " | ".join(values) + "|"
        body = " | ".join(
            [f"{str(cells[0]):<{label_width}}"] + values)
        return f"{indent}| {body} |"

    rendered = [line(headers)]
    rendered.extend(line(row) for row in rows)
    return rendered


# Telemetry signals from the rover's arm_pose packet (centi-units).
_POSE_SIGNALS = ("pose_x", "pose_y", "pose_z",
                 "pose_roll", "pose_pitch", "pose_yaw")


def _pose_table(x, y, z, roll, pitch, yaw):
    """Formatted pose table; position [in] and rotation [deg]."""
    return text_table(("A", "X", "Y", "Z"), [
        ("T", f"{float(x):.1f}", f"{float(y):.1f}", f"{float(z):.1f}"),
        ("R", f"{float(roll):.1f}", f"{float(pitch):.1f}",
         f"{float(yaw):.1f}"),
    ], indent="", min_width=1, compact_first=True)


def arm_pose_lines(telemetry: dict) -> list[str]:
    """End-effector pose table from the rover's arm_pose telemetry.

    The rover owns the pose calculation, so the basestation never derives
    it from joint angles.  Until the first pose packet arrives the table
    shows placeholders.
    """
    try:
        values = [float(telemetry[key]) / 100.0 for key in _POSE_SIGNALS]
    except (KeyError, TypeError, ValueError):
        return text_table(("A", "X", "Y", "Z"), [
            ("T", "---", "---", "---"),
            ("R", "---", "---", "---"),
        ], indent="", min_width=1, compact_first=True)
    return _pose_table(*values)


def teleop_active(snap) -> bool:
    """True when a SpaceMouse or jog axis exceeds the teleop deadzone."""
    spacemouse = (snap or {}).get("spacemouse") or {}
    try:
        return any(
            abs(float(spacemouse.get(axis, 0))) > 8
            for axis in ("x", "y", "z", "rx", "ry", "rz"))
    except (TypeError, ValueError):
        return False


def arm_keyboard_lines(arm_keys: dict) -> list[str]:
    """Device-panel legend for the Arm keyboard bindings."""
    lines = ["Keyboard (Arm):"]
    for action, pressed in arm_keys.items():
        key = Keyboard.key_for_arm(action)
        if key == "?":
            continue  # action has no key binding
        check = "x" if pressed else " "
        label = ARM_ACTION_LABELS.get(action, action)
        lines.append(f"    [{key.upper()}] [{check}] {label}")
    return lines


def configure_tags(widget):
    """Configure the Text tags used by the Arm module panel."""
    widget.tag_configure("header", foreground="#1c71d8")
    widget.tag_configure("label", foreground="#444444")
    widget.tag_configure("key", foreground="#555555", background="#eeeeee")
    widget.tag_configure("mode", foreground="#6a1b9a", background="#f3e8ff")
    widget.tag_configure(
        "mode_pnp", foreground="#1c71d8", background="#e8f2ff")
    widget.tag_configure(
        "mode_pnpf", foreground="#6a1b9a", background="#f3e8ff")
    widget.tag_configure(
        "mode_planar", foreground="#0b6b3a", background="#e6ffe9")
    widget.tag_configure(
        "mode_home", foreground="#a16207", background="#fff4d6")
    widget.tag_configure(
        "mode_zenith", foreground="#0f766e", background="#ccfbf1")
    widget.tag_configure("on", foreground="#0b6b3a", background="#e6ffe9")
    widget.tag_configure("off", foreground="#888888")
    widget.tag_configure(
        "option_on", foreground="#0b6b3a", background="#e6ffe9")
    widget.tag_configure(
        "option_off", foreground="#b91c1c", background="#fde8e8")
    widget.tag_configure("lock", foreground="#c2410c")
    widget.tag_configure("home", foreground="#a16207")
    widget.tag_configure("error", foreground="#ffffff", background="#b91c1c")
    widget.tag_configure("table_header", foreground="#1c71d8")
    widget.tag_configure("angle", foreground="#333333")
    widget.tag_configure(
        "row_free", foreground="#0b6b3a", background="#e6ffe9")
    widget.tag_configure(
        "row_locked", foreground="#b91c1c", background="#fde8e8")
    widget.tag_configure(
        "row_homing", foreground="#a16207", background="#fff4d6")
    widget.tag_configure("group", foreground="#1c71d8", underline=True)
    widget.tag_configure(
        "telemetry_live", foreground="#ffffff", background="#1a7f37",
        font=("TkDefaultFont", 11, "bold"))
    widget.tag_configure(
        "telemetry_missing", foreground="#ffffff", background="#b91c1c",
        font=("TkDefaultFont", 11, "bold"))


class ArmPanel:
    """Renders Arm telemetry into a Text widget and tracks rejections."""

    def __init__(self, widget):
        self.widget = widget
        configure_tags(widget)
        # Last arm rejection shown.  The rover only increments
        # arm_error_seq on a new error, so a repeat of the same code is
        # not mistaken for a fresh one.
        self._error_seq = 0
        self._error_text = ""
        self._error_at = 0.0
        self._last_state = None

    def reset(self):
        """Forget cached telemetry so the next packet redraws from scratch."""
        self._last_state = None
        self._error_seq = 0
        self._error_text = ""
        self._error_at = 0.0

    def draw(self, telemetry, snap=None):
        """Colored arm state + joint table in the Arm module panel."""
        snap = snap or {}
        mode = int(telemetry.get("arm_operation_mode", 0))
        flags = int(telemetry.get("arm_flags", 0))
        locked = int(telemetry.get("locked_joints", 0))
        homing = int(telemetry.get("homing_joints", 0))
        angles = tuple(telemetry.get(key) for _, key in ARM_JOINTS)
        motor_keys = [key for _, key in ARM_JOINTS[:5]]
        angles_live = all(telemetry.get(key) is not None
                          for key in motor_keys)
        arm_keys = snap.get("arm_keyboard") or {}
        guide_active = bool(arm_keys.get("guide_orientation"))
        rest_active = bool(arm_keys.get("rest"))
        solenoid_active = bool(arm_keys.get("solenoid_strike"))
        teleop = teleop_active(snap)

        flag_bit = {name.upper(): bit for bit, name in ARM_FLAG_NAMES}

        def flag_on(name):
            return bool(flags & (1 << flag_bit[name]))

        error_code = int(telemetry.get("arm_error_code", 0) or 0)
        error_arg = int(telemetry.get("arm_error_arg", 0) or 0)
        error_seq = int(telemetry.get("arm_error_seq", 0) or 0)
        if error_seq != self._error_seq:
            self._error_seq = error_seq
            # error_text() already returns "" for code 0.
            self._error_text = error_text(error_code, error_arg)
            self._error_at = time.time()
            log.debug("Arm error banner: code=%s arg=%s seq=%s text=%r",
                      error_code, error_arg, error_seq, self._error_text)
        error_age = (time.time() - self._error_at
                     if self._error_at else None)
        show_error = (bool(self._error_text) and error_age is not None
                      and error_age < ARM_ERROR_HOLD_SECONDS)

        received = telemetry.get("_received_at")
        age_bucket = (int(max(0.0, time.time() - received))
                      if isinstance(received, (int, float)) else None)
        pose = tuple(telemetry.get(key) for key in _POSE_SIGNALS)
        state_key = (mode, flags, locked, homing, angles, pose, age_bucket,
                     teleop, guide_active, rest_active, solenoid_active,
                     self._error_seq,
                     int(error_age) if error_age is not None else None)
        if self._last_state == state_key:
            return
        self._last_state = state_key

        widget = self.widget
        top = widget.index("@0,0")
        stick = widget.yview()[1] >= 0.999
        widget.config(state="normal")
        widget.delete("1.0", "end")
        if not angles_live:
            # No motor angles: show the angle + RPY readouts and the error,
            # with every setting/option hidden.
            self._insert_joint_table(
                widget, telemetry, locked, homing, show_state=False)
            self._insert_pose(widget, telemetry)
            self._insert_status(
                widget, teleop, guide_active, solenoid_active, flag_on)
            self._insert_error(widget, show_error, error_age, compact=True)
            self._insert_footer(widget, telemetry, angles_live)
            self._restore_view(widget, top, stick)
            return

        self._insert_joint_table(widget, telemetry, locked, homing)
        self._insert_pose(widget, telemetry)
        self._insert_status(
            widget, teleop, guide_active, solenoid_active, flag_on)
        widget.insert(
            "end", f"{'KEY':<5} {'OPTION':<10} {'VALUE'}\n",
            ("table_header",))
        widget.insert(
            "end", f"{'-' * 5} {'-' * 10} {'-' * 5}\n", ("off",))

        self._insert_error(widget, show_error, error_age)
        widget.insert("end", "\n")

        groups = (
            ("Drive Modes", (
                (ARM_OPTION_KEYS["POSITION"], "Position",
                 not flag_on("JOINT")),
                (ARM_OPTION_KEYS["JOINT"], "Joint", flag_on("JOINT")),
            )),
            ("Limit Types", (
                (ARM_OPTION_KEYS["PLANAR"], "Planar", flag_on("PLANAR")),
                (ARM_OPTION_KEYS["FLIPPED"], "Flipped", flag_on("FLIPPED")),
                (ARM_OPTION_KEYS["ZENITH"], "Zenith", flag_on("ZENITH")),
            )),
            ("Target Locks", (
                (ARM_OPTION_KEYS["POSLOCK"], "Pos Lock", flag_on("POSLOCK")),
                (ARM_OPTION_KEYS["ORILOCK"], "Ori Lock", flag_on("ORILOCK")),
            )),
            ("Actions", (
                (ARM_OPTION_KEYS["FLIP"], "Flipping", flag_on("FLIP")),
                (ARM_OPTION_KEYS["HOME"], "Homing All", flag_on("HOME")),
                (ARM_OPTION_KEYS["GUIDE"], "Guide", guide_active),
                (ARM_OPTION_KEYS["REST"], "Rest", rest_active),
                (ARM_OPTION_KEYS["SOL"], "Solenoid", solenoid_active),
            )),
        )
        for title, rows in groups:
            widget.insert("end", f"{title}\n", ("group",))
            for key, option, on in rows:
                widget.insert("end", f"{key:<5} ", ("key",))
                widget.insert("end", f"{option:<10} ", ("label",))
                widget.insert(
                    "end", "[ON ]" if on else "[OFF]",
                    ("option_on" if on else "option_off",))
                widget.insert("end", "\n", ("off",))
            widget.insert("end", "\n")

        widget.insert(
            "end",
            "\nLock: 1-5   Lock All: L   Rest: R   Home: Shift+1-5\n",
            ("off",))
        self._insert_footer(widget, telemetry, angles_live)
        self._restore_view(widget, top, stick)

    @staticmethod
    def _restore_view(widget, top, stick):
        """Keep the previous scroll position after a content rewrite."""
        widget.config(state="disabled")
        if stick:
            widget.yview_moveto(1.0)
        else:
            widget.yview(top)

    @staticmethod
    def _insert_footer(widget, telemetry, angles_live):
        """Put link status and packet age below the controls."""
        widget.insert("end", "\n", ("off",))
        widget.insert(
            "end",
            "ARM TELEMETRY: LIVE" if angles_live
            else "ARM TELEMETRY: MISSING",
            ("telemetry_live" if angles_live else "telemetry_missing",))
        widget.insert("end", "\n", ("off",))
        widget.insert(
            "end", last_packet_line(telemetry) + "\n", ("header",))

    @staticmethod
    def _insert_pose(widget, telemetry):
        """Insert the end-effector XYZ + RPY table below the joint angles."""
        widget.insert("end", "\nEND EFFECTOR POSE\n", ("table_header",))
        for line in arm_pose_lines(telemetry):
            widget.insert("end", line + "\n", ("off",))

    @staticmethod
    def _insert_status(widget, teleop, guide_active, solenoid_active,
                       flag_on):
        """One line summarizing the active inputs, modes, and actions."""
        active = []
        if teleop:
            active.append("TELEOP")
        if guide_active:
            active.append("GUIDE")
        if solenoid_active:
            active.append("SOLENOID")
        if flag_on("POSLOCK"):
            active.append("POS LOCK")
        if flag_on("ORILOCK"):
            active.append("ORI LOCK")
        if flag_on("HOME"):
            active.append("HOMING")
        if flag_on("FLIP"):
            active.append("FLIPPING")
        if flag_on("PLANAR"):
            active.append("PLANAR")
        if flag_on("ZENITH"):
            active.append("ZENITH")
        text = " | ".join(active) if active else "idle"
        widget.insert("end", "\nSTATUS ", ("table_header",))
        widget.insert("end", text, ("on" if active else "off",))
        widget.insert("end", "\n", ("off",))

    def _insert_error(self, widget, show_error, error_age,
                      compact=False):
        """Insert the last command rejection row."""
        if compact:
            widget.insert("end", "\nERROR ", ("table_header",))
        else:
            widget.insert(
                "end", f"{ARM_OPTION_KEYS['ERROR']:<5} ", ("key",))
            widget.insert("end", f"{'ERROR':<10} ", ("label",))
        if show_error:
            widget.insert(
                "end", f"{self._error_text}  ({error_age:.0f}s)",
                ("error",))
        else:
            widget.insert("end", "--", ("off",))
        widget.insert("end", "\n", ("off",))

    @staticmethod
    def _insert_joint_table(widget, telemetry, locked, homing,
                            show_state=True):
        """Insert the joint angle table, optionally with lock/home state."""
        if show_state:
            widget.insert(
                "end",
                f"{'JOINT':<7} {'ANGLE':>6} {'LOCK':<4} {'HOME':<4}\n",
                ("table_header",))
            widget.insert("end", "-" * 24 + "\n", ("off",))
        else:
            widget.insert(
                "end", f"{'JOINT':<7} {'ANGLE':>6}\n", ("table_header",))
            widget.insert("end", "-" * 14 + "\n", ("off",))
        for index, (name, key) in enumerate(ARM_JOINTS):
            value = telemetry.get(key)
            try:
                angle = f"{float(value) / 100.0:6.1f}"
            except (TypeError, ValueError):
                angle = f"{'--':>6}"
            if not show_state:
                widget.insert("end", f"{name:<7} {angle}", ("off",))
                widget.insert("end", "\n", ("off",))
                continue
            is_locked = index < 5 and bool(locked & (1 << index))
            is_homing = index < 5 and bool(homing & (1 << index))
            if is_homing:
                tag = "row_homing"
            elif is_locked:
                tag = "row_locked"
            else:
                tag = "row_free"
            lock_text = "[x]" if is_locked else "[ ]"
            home_text = "[x]" if is_homing else "[ ]"
            widget.insert(
                "end",
                f"{name:<7} {angle} {lock_text:<4} {home_text:<4}",
                (tag,))
            widget.insert("end", "\n", ("off",))


def last_packet_line(telemetry):
    """Arm panel footer: timestamp plus integer age."""
    received_at = telemetry.get("_received_at")
    if not isinstance(received_at, (int, float)):
        return "Last Packet: --:--:--   |  --s ago"
    age = max(0.0, time.time() - received_at)
    stamp = time.strftime("%H:%M:%S", time.localtime(received_at))
    return f"Last Packet: {stamp}   |  {int(age):02d}s ago"
