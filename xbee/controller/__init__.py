"""
Controller input handling package.

DATA FLOW:
    1. input_source.py reads raw gamepad events from the OS
    2. events.py defines the InputEvent format those raw events are converted to
    3. manager.py processes InputEvents and updates state
    4. state.py stores current button/axis values for each controller
    5. detection.py identifies what type of controller is connected

Modules:
    events       - InputEvent dataclass and event type constants
    detection    - Controller type detection (Xbox vs N64)
    state        - ControllerState: stores current values for all inputs
    manager      - ControllerManager + InputProcessor: event handling
    input_source - InputEventSource: reads gamepad events from the OS
"""

from .detection import detect_controller_type
from .events import (
    JOYAXISMOTION,
    JOYBUTTONDOWN,
    JOYBUTTONUP,
    JOYDEVICEADDED,
    JOYDEVICEREMOVED,
    JOYHATMOTION,
    QUIT,
    InputEvent,
)
from .input_source import InputEventSource, InputSourceError
from .manager import ControllerManager, InputProcessor
from .state import ControllerState

__all__ = [
    "JOYAXISMOTION",
    "JOYBUTTONDOWN",
    "JOYBUTTONUP",
    "JOYDEVICEADDED",
    "JOYDEVICEREMOVED",
    "JOYHATMOTION",
    "QUIT",
    "InputEvent",
    "detect_controller_type",
    "ControllerState",
    "ControllerManager",
    "InputProcessor",
    "InputEventSource",
    "InputSourceError",
]
