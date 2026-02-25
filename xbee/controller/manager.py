"""
Controller manager and input processor.

ControllerManager:
    Tracks connected controllers, handles hotplug events,
    and manages mode flags (creep mode, reverse mode).

InputProcessor:
    Translates raw InputEvents into controller state updates.
    Handles joystick axis scaling, trigger booleans, button encoding,
    and D-pad direction mapping.

HOW EVENTS FLOW:
    InputEvent -> ControllerManager.handle_axis_motion() (or button/joypad)
                    -> InputProcessor.process_joystick_axis() (etc.)
                        -> ControllerState.update_value()
"""

import logging
import os
import threading
from math import floor
from typing import Optional, Union

from xbee.config.constants import CONSTANTS
from xbee.controller.detection import detect_controller_type
from xbee.controller.events import (
    JOYBUTTONDOWN,
    JOYDEVICEADDED,
    JOYDEVICEREMOVED,
    InputEvent,
)
from xbee.controller.state import ControllerState

logger = logging.getLogger(__name__)

_TRUTHY_ENV_VALUES = frozenset(("1", "true", "yes", "on", "y", "t"))


def _default_creep_mode() -> bool:
    """Get startup creep mode from env, defaulting to enabled."""
    raw = os.environ.get("XBEE_DEFAULT_CREEP", "").strip()
    if not raw:
        return True
    return raw.lower() in _TRUTHY_ENV_VALUES


def _default_trigger_activation_threshold() -> float:
    """Get trigger activation threshold from env, defaulting to 0.05.

    Values are clamped to [0.0, 1.0]. Invalid values fall back to default.
    """
    default = 0.05
    raw = os.environ.get("XBEE_TRIGGER_THRESHOLD", "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning(
            "Invalid XBEE_TRIGGER_THRESHOLD=%r; using default %.2f", raw, default
        )
        return default
    return max(0.0, min(1.0, value))


# Joystick axis indices for quick lookup
_XBOX_JOYSTICK_AXES = [
    CONSTANTS.XBOX.JOYSTICK.AXIS_LX,
    CONSTANTS.XBOX.JOYSTICK.AXIS_LY,
    CONSTANTS.XBOX.JOYSTICK.AXIS_RX,
    CONSTANTS.XBOX.JOYSTICK.AXIS_RY,
]
_N64_JOYSTICK_AXES = [
    CONSTANTS.N64.JOYSTICK.AXIS_X,
    CONSTANTS.N64.JOYSTICK.AXIS_Y,
]
_ALL_JOYSTICK_AXES = _XBOX_JOYSTICK_AXES + _N64_JOYSTICK_AXES

_XBOX_TRIGGER_AXES = [
    CONSTANTS.XBOX.TRIGGER.AXIS_LT,
    CONSTANTS.XBOX.TRIGGER.AXIS_RT,
]

# Lookup tables for controller-specific axis validation and key mapping
_CONTROLLER_JOYSTICK_AXES = {
    CONSTANTS.XBOX.NAME: frozenset(_XBOX_JOYSTICK_AXES),
    CONSTANTS.N64.NAME: frozenset(_N64_JOYSTICK_AXES),
}

_N64_AXIS_KEY_MAP = {
    CONSTANTS.N64.JOYSTICK.AXIS_X: CONSTANTS.N64.JOYSTICK.AXIS_X_STR,
    CONSTANTS.N64.JOYSTICK.AXIS_Y: CONSTANTS.N64.JOYSTICK.AXIS_Y_STR,
}

_CONTROLLER_CONSTANTS = {
    CONSTANTS.XBOX.NAME: CONSTANTS.XBOX,
    CONSTANTS.N64.NAME: CONSTANTS.N64,
}


class ControllerManager:
    """Tracks connected controllers and manages mode flags.

    Attributes:
        joysticks:              Dict of connected controllers {instance_id: info}
        instance_id_values_map: Maps instance_id -> controller type ("xbox"/"n64")
        controller_state:       ControllerState storing current input values
        creep_mode:             True = slow speed (20%)
        reverse_mode:           True = inverted controls
        input_processor:        InputProcessor for translating events
    """

    def __init__(self):
        self.joysticks = {}
        self.instance_id_values_map = {}
        self._joystick_lock = threading.RLock()
        self.controller_state = ControllerState()

        # Mode flags
        self.creep_mode = _default_creep_mode()
        self.reverse_mode = False
        self.auto_state = CONSTANTS.AUTO_STATE.MIN

        self.input_processor = InputProcessor(self)

    def adjust_auto_state(self, delta: int) -> int:
        """Adjust autonomous state and clamp to protocol limits."""
        next_state = self.auto_state + int(delta)
        next_state = max(
            CONSTANTS.AUTO_STATE.MIN, min(CONSTANTS.AUTO_STATE.MAX, next_state)
        )
        self.auto_state = next_state
        return self.auto_state

    # --- Hotplug ---

    def handle_hotplug_event(self, event: InputEvent) -> bool:
        """Handle controller add/remove events.

        Returns True if should quit (controller disconnected).
        """
        if event.type == JOYDEVICEADDED:
            instance_id = getattr(event, "instance_id", None)
            if instance_id is None:
                instance_id = getattr(event, "device_index", None)
            name = getattr(event, "name", None) or "Unknown"
            guid = getattr(event, "guid", None)
            if instance_id is not None:
                self._add_device(instance_id, name, guid)
                logger.info("Joystick %d connected", instance_id)
            return False

        if event.type == JOYDEVICEREMOVED:
            instance_id = getattr(event, "instance_id", None)
            if instance_id is not None:
                self._remove_device(instance_id)
                logger.info("Joystick %d disconnected", instance_id)
            return True

        return False

    def handle_controller_added(self, event: InputEvent) -> bool:
        return self.handle_hotplug_event(event)

    def handle_controller_removed(self, event: InputEvent) -> bool:
        return self.handle_hotplug_event(event)

    def _add_device(self, instance_id: int, name: str, guid: Optional[str] = None):
        """Register a new controller.

        SpaceMouse devices detected by the OS as gamepads are ignored here
        because they have a dedicated HID reader (see spacemouse.py).  Routing
        their events through the gamepad pipeline would produce incorrect
        axis/button values.
        """
        controller_type = detect_controller_type(name)

        # SpaceMouse is handled by the dedicated HID reader – skip gamepad
        # registration entirely so its events don't pollute Xbox/N64 state.
        if controller_type == CONSTANTS.SPACEMOUSE.NAME:
            logger.info(
                "Ignoring '%s' in gamepad pipeline (handled by SpaceMouse HID reader)",
                name,
            )
            return

        with self._joystick_lock:
            self.joysticks[instance_id] = {"name": name, "guid": guid}
            if not controller_type:
                controller_type = CONSTANTS.XBOX.NAME
                logger.warning("Unknown controller '%s'; defaulting to xbox", name)
            self.instance_id_values_map[instance_id] = controller_type

    def _remove_device(self, instance_id: int):
        """Unregister a disconnected controller."""
        with self._joystick_lock:
            self.joysticks.pop(instance_id, None)
            self.instance_id_values_map.pop(instance_id, None)

    # --- Input handling ---

    def handle_axis_motion(self, event: InputEvent) -> None:
        """Route axis events to either joystick or trigger processor."""
        if event.axis in _ALL_JOYSTICK_AXES:
            self.input_processor.process_joystick_axis(event)
        else:
            self.input_processor.process_trigger_axis(event)

    def handle_button_down(self, event: InputEvent) -> None:
        self.input_processor.process_button(event)

    def handle_button_up(self, event: InputEvent) -> None:
        self.input_processor.process_button(event)

    def handle_joypad(self, event: InputEvent) -> None:
        self.input_processor.process_joypad(event)

    # --- Queries ---

    def should_quit_on_button(self, event: InputEvent) -> bool:
        """Check if home/start button was pressed (quit signal)."""
        with self._joystick_lock:
            if event.instance_id not in self.instance_id_values_map:
                return False
            ct = self.instance_id_values_map[event.instance_id]

        if ct == CONSTANTS.XBOX.NAME and event.button == CONSTANTS.XBOX.BUTTON.HOME:
            return True
        if ct == CONSTANTS.N64.NAME and event.button == CONSTANTS.N64.BUTTON.START:
            return True
        return False

    def get_controller_type(self, instance_id: int) -> Optional[str]:
        """Get controller type for an instance ID."""
        with self._joystick_lock:
            return self.instance_id_values_map.get(instance_id)

    def get_joystick(self, instance_id: int):
        """Get device info dict for an instance ID."""
        with self._joystick_lock:
            return self.joysticks.get(instance_id)

    def has_joysticks(self) -> bool:
        """Are any controllers connected?"""
        with self._joystick_lock:
            return bool(self.joysticks)

    # --- Mode flags ---

    def update_mode_flags(self, joypad_direction, controller_type: str) -> None:
        """Update creep/reverse modes based on D-pad + SELECT/START combo.

        How it works:
            - Hold SELECT + D-pad UP/DOWN -> toggle reverse mode
            - Hold START  + D-pad UP/DOWN -> toggle creep mode
        """
        name = self.controller_state.canonical_controller_name(controller_type)
        if name != CONSTANTS.XBOX.NAME:
            return

        values = self.controller_state.get_controller_values(CONSTANTS.XBOX.NAME)
        offset = CONSTANTS.XBOX.BUTTON_INDEX_OFFSET
        select_on = (
            values.get(CONSTANTS.XBOX.BUTTON.SELECT + offset)
            == CONSTANTS.XBOX.BUTTON.ON
        )
        start_on = (
            values.get(CONSTANTS.XBOX.BUTTON.START + offset) == CONSTANTS.XBOX.BUTTON.ON
        )

        direction_map = {
            CONSTANTS.XBOX.JOYPAD.UP: True,
            CONSTANTS.XBOX.JOYPAD.DOWN: False,
        }

        if isinstance(joypad_direction, tuple) and joypad_direction in direction_map:
            if select_on:
                self.reverse_mode = direction_map[joypad_direction]
                logger.info("Reverse mode %s", "on" if self.reverse_mode else "off")
            if start_on:
                self.creep_mode = direction_map[joypad_direction]
                logger.info("Creep mode %s", "on" if self.creep_mode else "off")


class InputProcessor:
    """Translates raw InputEvents into ControllerState updates.

    This is where gamepad values get converted:
        - Joystick float (-1.0 to 1.0) -> int (0-200, 100=center)
        - Trigger float -> bool (pressed or not)
        - Button press/release -> int (1=OFF, 2=ON)
        - D-pad tuple -> mapped to button states
    """

    def __init__(self, controller_manager: ControllerManager):
        self.controller_manager = controller_manager
        self.deadband = CONSTANTS.TIMING.DEADBAND_THRESHOLD
        self.trigger_activation_threshold = _default_trigger_activation_threshold()

    def process_joystick_axis(self, event: InputEvent) -> None:
        """Process a joystick axis movement event."""
        instance_id = getattr(event, "instance_id", None)
        if instance_id is None or event.axis is None or event.value is None:
            return

        ct = self.controller_manager.get_controller_type(instance_id)
        if not ct:
            return

        # Validate this axis belongs to this controller type
        valid_axes = _CONTROLLER_JOYSTICK_AXES.get(ct)
        if valid_axes is None or event.axis not in valid_axes:
            return

        # Apply deadband + mode multiplier
        multiplier = self._calculate_multiplier(ct)
        value = event.value if abs(event.value) >= self.deadband else 0

        # Convert to 0-200 integer range
        int_val = self._convert_axis_value(value, multiplier, _CONTROLLER_CONSTANTS[ct])

        # Resolve storage key (N64 uses string keys to avoid collision)
        axis_key = self._resolve_axis_key(ct, event.axis)
        if axis_key is None:
            return

        self.controller_manager.controller_state.update_value(ct, axis_key, int_val)

    def _resolve_axis_key(self, ct: str, axis: int) -> Optional[Union[int, str]]:
        """Resolve the storage key for a joystick axis.

        N64 axes are stored under string keys to avoid collision with button indices.
        Xbox axes use their numeric axis index directly.
        """
        if ct == CONSTANTS.N64.NAME:
            return _N64_AXIS_KEY_MAP.get(axis)
        return axis

    def process_trigger_axis(self, event: InputEvent) -> None:
        """Process a trigger axis event (Xbox only, treated as boolean)."""
        instance_id = getattr(event, "instance_id", None)
        if instance_id is None or event.axis is None or event.value is None:
            return

        ct = self.controller_manager.get_controller_type(instance_id)
        if not ct or ct == CONSTANTS.N64.NAME:  # N64 has no triggers
            return
        if event.axis not in _XBOX_TRIGGER_AXES:
            return

        try:
            trigger_value = float(event.value)
        except (TypeError, ValueError):
            trigger_value = 0.0

        self.controller_manager.controller_state.update_value(
            ct,
            event.axis,
            trigger_value >= self.trigger_activation_threshold,
        )

    def process_button(self, event: InputEvent) -> None:
        """Process a button press/release event."""
        instance_id = getattr(event, "instance_id", None)
        if instance_id is None or event.button is None:
            return

        ct = self.controller_manager.get_controller_type(instance_id)
        if not ct:
            return

        # Determine if pressed
        pressed = (
            bool(getattr(event, "value", None))
            if getattr(event, "value", None) is not None
            else event.type == JOYBUTTONDOWN
        )
        encoded = CONSTANTS.XBOX.BUTTON.ON if pressed else CONSTANTS.XBOX.BUTTON.OFF

        if ct == CONSTANTS.XBOX.NAME and pressed and event.type == JOYBUTTONDOWN:
            if event.button == CONSTANTS.XBOX.BUTTON.LEFT_BUMPER:
                self.controller_manager.adjust_auto_state(-1)
            elif event.button == CONSTANTS.XBOX.BUTTON.RIGHT_BUMPER:
                self.controller_manager.adjust_auto_state(1)

        # Xbox buttons need index offset to avoid collision with axis indices
        offset = CONSTANTS.XBOX.BUTTON_INDEX_OFFSET if ct == CONSTANTS.XBOX.NAME else 0
        self.controller_manager.controller_state.update_value(
            ct, event.button + offset, encoded
        )

    def process_joypad(self, event: InputEvent) -> None:
        """Process a D-pad / hat event."""
        instance_id = getattr(event, "instance_id", None)
        if instance_id is None or event.value is None:
            return

        ct = self.controller_manager.get_controller_type(instance_id)
        if not ct:
            return

        if ct == CONSTANTS.N64.NAME:
            self._process_n64_dpad(event)
        elif ct == CONSTANTS.XBOX.NAME:
            self.controller_manager.update_mode_flags(event.value, CONSTANTS.XBOX.NAME)

    # --- Internal helpers ---

    def _calculate_multiplier(self, controller_type: str) -> float:
        """Calculate axis multiplier based on creep/reverse mode."""
        if controller_type == CONSTANTS.N64.NAME:
            return CONSTANTS.CONTROLLER_MODES.NORMAL_MULTIPLIER

        mult = CONSTANTS.CONTROLLER_MODES.NORMAL_MULTIPLIER
        if self.controller_manager.creep_mode:
            mult = CONSTANTS.CONTROLLER_MODES.CREEP_MULTIPLIER
        if self.controller_manager.reverse_mode:
            mult = -mult
        return mult

    def _convert_axis_value(self, value: float, multiplier: float, constants) -> int:
        """Convert a -1.0..1.0 float to 0..200 int with multiplier applied."""
        result = floor(multiplier * value * 100 + constants.JOYSTICK.NEUTRAL_INT)
        return max(
            constants.JOYSTICK.MIN_VALUE, min(constants.JOYSTICK.MAX_VALUE, result)
        )

    def _process_n64_dpad(self, event: InputEvent) -> None:
        """Map N64 D-pad (x, y) tuple to button ON/OFF states.

        D-pad maps to DP_UP/DOWN/LEFT/RIGHT buttons for the N64.
        """
        x, y = event.value
        n64 = CONSTANTS.N64
        on, off = n64.BUTTON.ON, n64.BUTTON.OFF
        state = self.controller_manager.controller_state

        # Horizontal
        state.update_value(n64.NAME, n64.BUTTON.DP_LEFT, on if x == -1 else off)
        state.update_value(n64.NAME, n64.BUTTON.DP_RIGHT, on if x == 1 else off)

        # Vertical
        state.update_value(n64.NAME, n64.BUTTON.DP_DOWN, on if y == -1 else off)
        state.update_value(n64.NAME, n64.BUTTON.DP_UP, on if y == 1 else off)
