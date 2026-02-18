"""
Telemetry interpretation helpers for the display system.

These functions interpret raw telemetry dictionary values into
display-friendly formats (booleans, status strings, colors, etc.).

Used by both TkinterDisplay and potentially other display backends.
"""

import re
from typing import Any, Dict, Optional

_TRUE_STRINGS = frozenset(("1", "true", "yes", "on", "enabled", "active"))
_FALSE_STRINGS = frozenset(
    ("0", "false", "no", "off", "disabled", "inactive")
)

_ESTOP_KEYS = ("estop", "e_stop", "rover_status", "rover_estop")
_ESTOP_MARKERS = ("estop", "e-stop", "emergency stop")
_NOT_PATTERN = re.compile(r"\bnot\b")
_ESTOP_FALSE_EXACT = frozenset(
    (
        "ok",
        "nominal",
        "running",
        "clear",
        "inactive",
        "disabled",
        "false",
        "0",
        "off",
        "no",
    )
)
_ESTOP_TRUE_EXACT = frozenset(
    (
        "estop",
        "e-stop",
        "estopped",
        "e_stopped",
        "emergency stop",
        "emergency_stop",
        "active",
        "enabled",
        "true",
        "1",
        "on",
        "yes",
    )
)


def resolve_boolean_flag(telemetry: Dict[str, Any], keys: list[str]) -> Optional[bool]:
    """Look up the first matching key and coerce its value to True/False.

    Returns None if no key is found in telemetry.
    """
    for key in keys:
        if key not in telemetry:
            continue
        value = telemetry.get(key)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in _TRUE_STRINGS:
                return True
            if lowered in _FALSE_STRINGS:
                return False
        return bool(value)
    return None


def _contains_estop_marker(value: str) -> bool:
    return any(marker in value for marker in _ESTOP_MARKERS)


def _resolve_estop_string_status(value: str) -> Optional[bool]:
    if value in _ESTOP_FALSE_EXACT:
        return False
    if value in _ESTOP_TRUE_EXACT:
        return True
    if _NOT_PATTERN.search(value) and _contains_estop_marker(value):
        return False
    if _contains_estop_marker(value):
        return True
    return None


def resolve_estop_status(telemetry: Dict[str, Any]) -> Optional[bool]:
    """Return True if the rover is e-stopped, False if OK, None if unknown."""
    estop_value = None
    for key in _ESTOP_KEYS:
        if key in telemetry:
            estop_value = telemetry.get(key)
            break

    if estop_value is None:
        return None
    if isinstance(estop_value, str):
        lowered = estop_value.strip().lower()
        resolved = _resolve_estop_string_status(lowered)
        if resolved is not None:
            return resolved
        return None
    if isinstance(estop_value, bool):
        return estop_value
    return bool(estop_value)


def resolve_auto_status(
    telemetry: Dict[str, Any], current_state: str = "teleop"
) -> str:
    """Determine the autonomy status string from telemetry.

    Returns one of: "teleop", "autonomous", "arrived".
    Falls back to *current_state* when no telemetry key is present.
    """
    value = next(
        (
            telemetry[key]
            for key in ("auto_status", "autonomy_status", "autonomous_status")
            if key in telemetry
        ),
        None,
    )
    if value is None:
        return current_state
    if isinstance(value, bool):
        return "autonomous" if value else "teleop"
    if isinstance(value, (int, float)):
        return _resolve_auto_status_numeric(value)
    if isinstance(value, str):
        return _resolve_auto_status_string(value)
    return "teleop"


def _resolve_auto_status_numeric(value: float) -> str:
    iv = int(value)
    if iv >= 2:
        return "arrived"
    if iv == 1:
        return "autonomous"
    return "teleop"


def _resolve_auto_status_string(value: str) -> str:
    lowered = value.lower()
    if any(s in lowered for s in ("arriv", "success", "target")):
        return "arrived"
    if "auto" in lowered:
        return "autonomous"
    if "tele" in lowered or "manual" in lowered:
        return "teleop"
    return "teleop"


def filter_telemetry_for_module(
    telemetry: Dict[str, Any], module_key: str
) -> Dict[str, Any]:
    """Return only the telemetry entries relevant to a given module view.

    Module keys: "life", "auto", "arm".
    """
    prefixes = {
        "life": ("life_", "life ", "victim_", "detection_"),
        "auto": ("auto_", "autonomy_", "lidar_", "nav_", "path_"),
        "arm": ("arm_", "servo_", "joint_", "encoder_", "gripper_"),
    }
    explicit_keys = {
        "life": {
            "color_sensor",
            "limit_switch_1",
            "limit_switch_2",
            "auger_depth",
            "pump_output_level",
            "slide_position",
            "selected_tube",
            "spec_slide_position",
            "spec_color_sensor",
            "life_enabled",
        },
        "auto": {
            "drive_speed_left",
            "drive_speed_right",
            "yaw",
            "pitch",
            "roll",
            "control_mode",
            "auto_state",
            "auto_enabled",
        },
        "arm": {
            "arm_base_position",
            "shoulder_position",
            "elbow_position",
            "wrist_position",
            "claw_encoder",
            "arm_enabled",
        },
    }

    module_prefixes = prefixes.get(module_key, ())
    allowed_explicit_keys = explicit_keys.get(module_key, set())
    if not module_prefixes and not allowed_explicit_keys:
        return {}

    result: Dict[str, Any] = {}
    for key, value in telemetry.items():
        if not isinstance(key, str):
            continue
        lowered = key.lower()
        if lowered in allowed_explicit_keys or lowered.startswith(module_prefixes):
            result[key] = value
    return result


__all__ = [
    "resolve_boolean_flag",
    "resolve_estop_status",
    "resolve_auto_status",
    "filter_telemetry_for_module",
]
