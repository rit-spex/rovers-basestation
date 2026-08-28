# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : __init__.py
# purpose       : basestation package marker; repairs the one-shot
#                 EVENT_MAP generator in the inputs library
# created on    : 7/12/2026 - Ryan
# last modified : 8/24/2026 - Ryan
# ------------------------------------------------------------------
"""RIT SPEX rover basestation: controller input -> rover, telemetry -> GUI."""

try:
    import inputs as _inputs
except Exception:  # inputs is optional; gamepads.py already handles this
    _inputs = None


def _repair_inputs_event_map():
    """Fix inputs 0.5: `EVENT_MAP['type_codes']` is a one-shot generator.

    The first `DeviceManager()` drains it, so later Linux scans lose
    `LED` type codes and hotplug rescan fails. Make it once so that
    future thingies work too
    """
    if _inputs is None:
        return
    _inputs.EVENT_MAP = tuple(
        (key, tuple((name, code) for code, name in _inputs.EVENT_TYPES))
        if key == "type_codes" else (key, value)
        for key, value in _inputs.EVENT_MAP)


_repair_inputs_event_map()
