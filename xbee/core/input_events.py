"""
Input event definitions and compatibility constants for controller handling.
Replaces pygame event constants with a lightweight internal API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# Event type constants (mirroring pygame naming for minimal refactors)
JOYDEVICEADDED = 1
JOYDEVICEREMOVED = 2
JOYAXISMOTION = 3
JOYBUTTONDOWN = 4
JOYBUTTONUP = 5
JOYHATMOTION = 6
QUIT = 7


@dataclass
class InputEvent:
    """Normalized input event.

    Attributes mirror pygame's event fields to ease migration.
    """

    type: int
    instance_id: Optional[int] = None
    device_index: Optional[int] = None
    axis: Optional[int] = None
    button: Optional[int] = None
    value: Any = None
    name: Optional[str] = None
    guid: Optional[str] = None
    raw_code: Optional[str] = None
    raw_state: Optional[Any] = None

    def is_button_event(self) -> bool:
        return self.type in (JOYBUTTONDOWN, JOYBUTTONUP)

    def is_axis_event(self) -> bool:
        return self.type == JOYAXISMOTION

    def is_hat_event(self) -> bool:
        return self.type == JOYHATMOTION
