"""
Input event definitions for controller handling.

These replace pygame event constants with a lightweight internal API.
Each event has a type (one of the constants below) and optional fields
depending on the event type.

Event types:
    JOYDEVICEADDED   (1) - A controller was plugged in
    JOYDEVICEREMOVED (2) - A controller was unplugged
    JOYAXISMOTION    (3) - A joystick axis moved
    JOYBUTTONDOWN    (4) - A button was pressed
    JOYBUTTONUP      (5) - A button was released
    JOYHATMOTION     (6) - The D-pad/hat changed
    QUIT             (7) - Application quit requested
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# Event type constants
JOYDEVICEADDED = 1
JOYDEVICEREMOVED = 2
JOYAXISMOTION = 3
JOYBUTTONDOWN = 4
JOYBUTTONUP = 5
JOYHATMOTION = 6
QUIT = 7


@dataclass
class InputEvent:
    """A normalized controller input event.

    Attributes:
        raw_code:     Raw event code from the OS driver.
        raw_state:    Raw event state from the OS driver.
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
