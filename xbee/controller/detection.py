"""
Controller type detection utility.

Identifies whether a gamepad is an Xbox or N64 controller based on
its reported name string. Used by controller/manager.py,
controller/input_source.py, and display/gui.py.

To add support for a new controller type:
    1. Add its name pattern to detect_controller_type() below
    2. Add its button/axis definitions to config/constants.py
    3. Add its message format to protocol/encoding.py
"""

from typing import Optional

_XBOX_MARKERS = ("xbox", "x-box")
_N64_MARKERS = ("n64", "dinput", "directinput", "direct input")
_SPACEMOUSE_MARKERS = ("spacemouse", "space mouse", "3dconnexion")

# Import lazily to avoid circular imports at module level
_XBOX_NAME: Optional[str] = None
_N64_NAME: Optional[str] = None
_SPACEMOUSE_NAME: Optional[str] = None


def _get_controller_names():
    """Lazy-load controller name constants to avoid circular imports."""
    global _XBOX_NAME, _N64_NAME, _SPACEMOUSE_NAME
    if _XBOX_NAME is None:
        from xbee.config.constants import CONSTANTS

        _XBOX_NAME = CONSTANTS.XBOX.NAME
        _N64_NAME = CONSTANTS.N64.NAME
        _SPACEMOUSE_NAME = CONSTANTS.SPACEMOUSE.NAME
    return _XBOX_NAME, _N64_NAME, _SPACEMOUSE_NAME


def detect_controller_type(name: str) -> Optional[str]:
    """Detect controller type from its name string.

    Args:
        name: The controller's reported name (e.g., "Xbox Wireless Controller").

    Returns:
        The canonical controller name ("xbox", "n64", "3Dconnexion SpaceMouse"),
        or ``None`` if unrecognized.

    Examples:
        >>> detect_controller_type("Xbox Wireless Controller")
        'xbox'
        >>> detect_controller_type("Retrolink N64")
        'n64'
        >>> detect_controller_type("3Dconnexion SpaceMouse Wireless")
        '3Dconnexion SpaceMouse'
        >>> detect_controller_type("Unknown Gamepad")  # Returns None
    """
    if not isinstance(name, str):
        return None

    xbox_name, n64_name, spacemouse_name = _get_controller_names()
    lower = name.lower()

    # Check SpaceMouse first – 3Dconnexion devices should never be
    # treated as gamepads even though the OS may enumerate them as such.
    if any(marker in lower for marker in _SPACEMOUSE_MARKERS):
        return spacemouse_name
    if any(marker in lower for marker in _XBOX_MARKERS):
        return xbox_name
    if any(marker in lower for marker in _N64_MARKERS):
        return n64_name

    return None
