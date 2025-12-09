"""
Controller management module for handling diff controller types and their inputs.
Seperates controller logic from main XBee comms class.
"""

import logging
import os
import threading
from math import floor
from typing import Any, Dict, Optional, Union

import pygame
from pygame.event import Event

from .command_codes import CONSTANTS
from .encoding import MessageEncoder

logger = logging.getLogger(__name__)


class ControllerState:
    """
    Manages the state of controller inputs.
    """

    def __init__(self):
        """
        Init controller state with default vals.
        """
        # Build a mapping converting numeric indices to string aliases; use get_alias_for_index for safe access.
        self.index_conversion = self._build_index_conversion()
        # Build reverse mapping for fast alias -> numeric key lookups
        # Pattern: self.reverse_index_conversion[controller_name][string_alias] == numeric_index
        self.reverse_index_conversion = {
            name: {str_key: num_key for num_key, str_key in mapping.items()}
            for name, mapping in self.index_conversion.items()
        }

        # Values keyed by controller name -> numeric or string keys depending on mapping
        self.values: Dict[str, Dict[Any, Any]] = {}

        # Lock protecting self.values to avoid races when InputProcessor and other threads access it; RLock allows nested calls.
        self._values_lock = threading.RLock()

        # Initialize values from encoder message definitions
        self._initialize_values_from_messages()

    def _build_index_conversion(self) -> dict:
        """
        Return the index conversion mapping between numeric keys and string keys.
        """
        return {
            CONSTANTS.XBOX.NAME: {
                # Axis
                CONSTANTS.XBOX.JOYSTICK.AXIS_LX: CONSTANTS.XBOX.JOYSTICK.AXIS_LX_STR,
                CONSTANTS.XBOX.JOYSTICK.AXIS_LY: CONSTANTS.XBOX.JOYSTICK.AXIS_LY_STR,
                CONSTANTS.XBOX.JOYSTICK.AXIS_RX: CONSTANTS.XBOX.JOYSTICK.AXIS_RX_STR,
                CONSTANTS.XBOX.JOYSTICK.AXIS_RY: CONSTANTS.XBOX.JOYSTICK.AXIS_RY_STR,
                # Buttons
                CONSTANTS.XBOX.TRIGGER.AXIS_LT: CONSTANTS.XBOX.TRIGGER.AXIS_LT_STR,
                CONSTANTS.XBOX.TRIGGER.AXIS_RT: CONSTANTS.XBOX.TRIGGER.AXIS_RT_STR,
                CONSTANTS.XBOX.BUTTON.A
                + CONSTANTS.XBOX.BUTTON_INDEX_OFFSET: CONSTANTS.XBOX.BUTTON.A_STR,
                CONSTANTS.XBOX.BUTTON.B
                + CONSTANTS.XBOX.BUTTON_INDEX_OFFSET: CONSTANTS.XBOX.BUTTON.B_STR,
                CONSTANTS.XBOX.BUTTON.X
                + CONSTANTS.XBOX.BUTTON_INDEX_OFFSET: CONSTANTS.XBOX.BUTTON.X_STR,
                CONSTANTS.XBOX.BUTTON.Y
                + CONSTANTS.XBOX.BUTTON_INDEX_OFFSET: CONSTANTS.XBOX.BUTTON.Y_STR,
                CONSTANTS.XBOX.BUTTON.LEFT_BUMPER
                + CONSTANTS.XBOX.BUTTON_INDEX_OFFSET: CONSTANTS.XBOX.BUTTON.LEFT_BUMPER_STR,
                CONSTANTS.XBOX.BUTTON.RIGHT_BUMPER
                + CONSTANTS.XBOX.BUTTON_INDEX_OFFSET: CONSTANTS.XBOX.BUTTON.RIGHT_BUMPER_STR,
                CONSTANTS.XBOX.BUTTON.START
                + CONSTANTS.XBOX.BUTTON_INDEX_OFFSET: CONSTANTS.XBOX.BUTTON.START_STR,
                CONSTANTS.XBOX.BUTTON.SELECT
                + CONSTANTS.XBOX.BUTTON_INDEX_OFFSET: CONSTANTS.XBOX.BUTTON.SELECT_STR,
            },
            CONSTANTS.N64.NAME: {
                # Buttons
                CONSTANTS.N64.BUTTON.A: CONSTANTS.N64.BUTTON.A_STR,
                CONSTANTS.N64.BUTTON.B: CONSTANTS.N64.BUTTON.B_STR,
                CONSTANTS.N64.BUTTON.C_UP: CONSTANTS.N64.BUTTON.C_UP_STR,
                CONSTANTS.N64.BUTTON.C_DOWN: CONSTANTS.N64.BUTTON.C_DOWN_STR,
                CONSTANTS.N64.BUTTON.C_LEFT: CONSTANTS.N64.BUTTON.C_LEFT_STR,
                CONSTANTS.N64.BUTTON.C_RIGHT: CONSTANTS.N64.BUTTON.C_RIGHT_STR,
                CONSTANTS.N64.BUTTON.L: CONSTANTS.N64.BUTTON.L_STR,
                CONSTANTS.N64.BUTTON.R: CONSTANTS.N64.BUTTON.R_STR,
                CONSTANTS.N64.BUTTON.Z: CONSTANTS.N64.BUTTON.Z_STR,
                CONSTANTS.N64.BUTTON.DP_UP: CONSTANTS.N64.BUTTON.DP_UP_STR,
                CONSTANTS.N64.BUTTON.DP_DOWN: CONSTANTS.N64.BUTTON.DP_DOWN_STR,
                CONSTANTS.N64.BUTTON.DP_LEFT: CONSTANTS.N64.BUTTON.DP_LEFT_STR,
                CONSTANTS.N64.BUTTON.DP_RIGHT: CONSTANTS.N64.BUTTON.DP_RIGHT_STR,
            },
        }

    def get_alias_for_index(self, controller_type: str, index: int) -> Optional[str]:
        """
        Get the string alias for a numeric index for a given controller.

        This method is a safe accessor for clients (including tests) that need
        to resolve the string key alias for a numeric index. It returns None
        when no mapping is available.

        Args:
            controller_type: Name of the controller (e.g., CONSTANTS.N64.NAME or
                the string 'n64', case insensitive).
            index: The numeric index (e.g., CONSTANTS.N64.BUTTON.A).

        Returns:
            Optional[str]: The string alias associated with the numeric index,
            or None if not present.
        """
        controller_name = self.canonical_controller_name(controller_type)
        mapping = self.index_conversion.get(controller_name, {})
        return mapping.get(index)

    def get_numeric_key_for_alias(
        self, controller_type: str, alias: str
    ) -> Optional[int]:
        """
        Get the numeric index for a string alias for a given controller.

        This is the inverse of get_alias_for_index and is a safe accessor
        for clients that need to find numeric indices based on the human-
        readable alias key.

        Returns None if the alias isn't found.
        """
        controller_name = self.canonical_controller_name(controller_type)
        mapping = self.reverse_index_conversion.get(controller_name, {})
        return mapping.get(alias)

    def _initialize_values_from_messages(self) -> None:
        """
        Populate self.values using the encoder's message definitions.
        """
        encoder = MessageEncoder()
        known_types = set(self.index_conversion.keys())
        for _message_id, message in encoder.get_messages().items():
            name = message.get("name")
            # ensure name is a string and is a known controller type
            if not isinstance(name, str) or name not in known_types:
                continue
            # ensure dictionary exists for this controller type
            self.values[name] = {}
            self._populate_values_for_message(name, message)

    def _populate_values_for_message(self, name: str, message: dict) -> None:
        """
        Populate values for a single message definition.
        """
        for signal_name, signal in message.get("values", {}).items():
            if not hasattr(signal, "default_value"):
                logger.warning(
                    "Signal %s in message %s missing default_value attribute",
                    signal_name,
                    name,
                )
                continue
            numeric_key = self._find_numeric_key_for_signal(name, signal_name)
            key = numeric_key if numeric_key is not None else signal_name
            # Use update_value to make sur that default values are normalized consstently
            self.update_value(name, key, signal.default_value)

    def _find_numeric_key_for_signal(self, name: str, signal_name: str):
        """
        Return numeric key for a signal_name if present in index_conversion, else None.

        This uses the precomputed reverse index mapping for O(1) lookups.
        """
        mapping = self.reverse_index_conversion.get(name, {})
        return mapping.get(signal_name)

    def canonical_controller_name(self, controller_type: str) -> str:
        """
        Normalize controller type string to the canonical name used in CONSTANTS
        (handles case-insensitive input like 'xbox' or 'XBOX').
        """
        # Ensure controller_type is a string, otherwise raise TypeError.
        if not isinstance(controller_type, str):
            raise TypeError("controller_type must be a str")

        if controller_type.lower() == CONSTANTS.XBOX.NAME.lower():
            return CONSTANTS.XBOX.NAME
        if controller_type.lower() == CONSTANTS.N64.NAME.lower():
            return CONSTANTS.N64.NAME
        return controller_type

    def get_controller_values(self, controller_type: str) -> Dict:
        """
        Get the current values for a controller type.

        Args:
            controller_type: Either "xbox" or "n64"

        Returns:
            Dict: Current controller values
        """
        name = self.canonical_controller_name(controller_type)
        # Return a shallow copy of internal controller values to avoid concurrent mutation while iterating/encoding.
        # preserving the live storage in self.values for updates.
        with self._values_lock:
            vals = self.values.get(name)
            if vals is None:
                return {}
            return vals.copy()

    def update_value(self, controller_type: str, key: Union[int, str], value) -> None:
        """
        Updates specific controller val.

        Args:
            controller_type: "xbox" or "n64"
            key: The input key/axis ID (int) or string alias
            value: New value to set. Expected types depend on the key category:

                - Axis keys (e.g., constants like
                    CONSTANTS.XBOX.JOYSTICK.AXIS_LY or alias "AXIS_LY")
                        - Preferred stored representation: single-byte bytes object
                            (e.g., b"\x64").
                        - Accepted input types: bytes (length 1), bytearray
                            (length 1), memoryview (length 1), or int (0..255).
                        - If an int is provided, it will be converted automatically
                            to a one-byte bytes via int.to_bytes(1, 'big').
                    - Example:
                        update_value('xbox', CONSTANTS.XBOX.JOYSTICK.AXIS_LY, 100)
                        # Stored as: b"\x64"

                                - Trigger keys (e.g., CONSTANTS.XBOX.TRIGGER.AXIS_LT or alias
                                    "AXIS_LT")
                                        - Preferred stored representation: bool (True/False).
                                        - Accepted input types: bool, or int where 0 => False and
                                            >0 => True.
                    - Example:
                        update_value('xbox', CONSTANTS.XBOX.TRIGGER.AXIS_LT, True)

                                - Button keys (e.g., indices + offset for XBOX buttons or
                                    N64 button indexes or alias strings like "A")
                                        - Preferred stored representation: int (0..255) - most code
                                            uses 0/1 or 1/2 depending on controller expectations.
                                        - Accepted input types: int (0..255) or bool (False -> 0,
                                            True -> 1). When a boolean is supplied it will be
                                            converted to an int 0/1.
                                        - Note: Some controller APIs or message formats may use a
                                            different convention (e.g.,
                                            CONSTANTS.XBOX.BUTTON.ON is 2 and OFF is 1); update_value
                                            will not automatically translate between these convention
                                            values. Use the controller constants when explicit
                                            values are required.
                    - Example:
                        update_value('xbox', CONSTANTS.XBOX.BUTTON.A + CONSTANTS.XBOX.BUTTON_INDEX_OFFSET, 1)

        If the provided type does not match the expected types for the key category, a ValueError is raised.
        """

        name = self.canonical_controller_name(controller_type)
        # Acquire lock to serialize updates and avoid races with readers/writers.
        with self._values_lock:
            if name not in self.values:
                # Initialize container if missing
                self.values[name] = {}

            # Normalize and validate the input value based on key category (axis/trigger/button)
            converted_value = self._convert_and_validate_value(name, key, value)

            # Store provided key with converted value and update any matching alias keys
            self._store_converted_value(name, key, converted_value)

    def _convert_and_validate_value(self, name: str, key: Union[int, str], value):
        """Normalize and validate a controller value according to key category.

        Extracted to reduce cognitive complexity from update_value and centralize
        conversion logic for all callers.
        """
        alias = self._get_alias_for_key(name, key)
        category = self._determine_category_for_alias(alias)

        if category == "axis":
            return self._normalize_axis_value(key, value)
        if category == "trigger":
            return self._normalize_trigger_value(key, value)
        if category == "button":
            return self._normalize_button_value(key, value)
        # Unknown category: accept the provided value as-is
        return value

    def _store_converted_value(
        self, name: str, key: Union[int, str], converted_value
    ) -> None:
        """Store the converted value into the internal values mapping and
        update both numeric and string alias representations when present.

        The helper centralizes alias synchronization logic to reduce duplicate
        behavior across the class.
        """
        self.values[name][key] = converted_value

        mapping = self.index_conversion.get(name, {})
        # If the provided key is numeric and there's a string alias for it, update both.
        if isinstance(key, int) and key in mapping:
            str_key = mapping[key]
            self.values[name][str_key] = converted_value
            return

        # If provided key is a string, attempt to update any numeric alias
        if isinstance(key, str):
            num_key = self.reverse_index_conversion.get(name, {}).get(key)
            if num_key is not None:
                self.values[name][num_key] = converted_value

    def _get_alias_for_key(self, name: str, key: Union[int, str]) -> Optional[str]:
        """
        Return a string alias for a numeric key, or the key itself if already a
        string.
        """
        mapping = self.index_conversion.get(name, {})
        if isinstance(key, int) and key in mapping:
            return mapping[key]
        if isinstance(key, str):
            return key
        return None

    def _determine_category_for_alias(self, alias: Optional[str]) -> str:
        """
        Return category of alias: 'axis', 'trigger', 'button', or 'unknown'.
        """
        if alias is None:
            return "unknown"

        xbox = CONSTANTS.XBOX
        n64 = CONSTANTS.N64

        xbox_axes = {
            xbox.JOYSTICK.AXIS_LX_STR,
            xbox.JOYSTICK.AXIS_LY_STR,
            xbox.JOYSTICK.AXIS_RX_STR,
            xbox.JOYSTICK.AXIS_RY_STR,
        }
        xbox_triggers = {xbox.TRIGGER.AXIS_LT_STR, xbox.TRIGGER.AXIS_RT_STR}
        xbox_buttons = {
            xbox.BUTTON.A_STR,
            xbox.BUTTON.B_STR,
            xbox.BUTTON.X_STR,
            xbox.BUTTON.Y_STR,
            xbox.BUTTON.LEFT_BUMPER_STR,
            xbox.BUTTON.RIGHT_BUMPER_STR,
            xbox.BUTTON.START_STR,
            xbox.BUTTON.SELECT_STR,
        }

        n64_axes = {n64.JOYSTICK.AXIS_X_STR, n64.JOYSTICK.AXIS_Y_STR}
        n64_buttons = {
            n64.BUTTON.A_STR,
            n64.BUTTON.B_STR,
            n64.BUTTON.C_UP_STR,
            n64.BUTTON.C_DOWN_STR,
            n64.BUTTON.C_LEFT_STR,
            n64.BUTTON.C_RIGHT_STR,
            n64.BUTTON.L_STR,
            n64.BUTTON.R_STR,
            n64.BUTTON.Z_STR,
            n64.BUTTON.DP_UP_STR,
            n64.BUTTON.DP_DOWN_STR,
            n64.BUTTON.DP_LEFT_STR,
            n64.BUTTON.DP_RIGHT_STR,
        }

        if alias in xbox_axes or alias in n64_axes:
            return "axis"
        if alias in xbox_triggers:
            return "trigger"
        if alias in xbox_buttons or alias in n64_buttons:
            return "button"
        return "unknown"

    def _normalize_axis_value(self, key: Union[int, str], value) -> bytes:
        """
        Normalize axis values to a one-byte bytes representation.
        """
        # Axis should be a single byte (bytes-like) or integer 0..255
        if isinstance(value, int):
            if value < 0 or value > 255:
                raise ValueError(
                    f"Axis value out of range for key {key}: {value} (expected 0..255)"
                )
            return int(value).to_bytes(1, byteorder="big")
        if isinstance(value, (bytes, bytearray, memoryview)):
            if len(bytes(value)) != 1:
                raise ValueError(
                    f"Axis value must be single byte for key {key}; got length {len(bytes(value))}"
                )
            return bytes(value)
        raise ValueError(f"Unsupported axis value type for key {key}: {type(value)}")

    def _normalize_trigger_value(self, key: Union[int, str], value) -> bool:
        """
        Normalize trigger values to booleans.
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return bool(value)
        raise ValueError(f"Unsupported trigger value type for key {key}: {type(value)}")

    def _normalize_button_value(self, key: Union[int, str], value) -> int:
        """
        Normalize button values to integers using 2-bit encoding (1=OFF, 2=ON).
        Expects already encoded values or booleans.
        """
        if isinstance(value, bool):
            # Convert bool to 2bit encoding: False -> 1 (OFF), True -> 2 (ON)
            return CONSTANTS.XBOX.BUTTON.ON if value else CONSTANTS.XBOX.BUTTON.OFF
        if isinstance(value, int):
            # Accept already encoded values (1=OFF, 2=ON)
            if value == CONSTANTS.XBOX.BUTTON.OFF or value == CONSTANTS.XBOX.BUTTON.ON:
                return int(value)
            else:
                raise ValueError(
                    f"Button value out of range for key {key}: {value} (expected {CONSTANTS.XBOX.BUTTON.OFF} or {CONSTANTS.XBOX.BUTTON.ON})"
                )
        raise ValueError(f"Unsupported button value type for key {key}: {type(value)}")


class ControllerManager:
    """
    Manages controller connections and input processing.
    """

    def __init__(self):
        """
        Init the controller manager.
        """

        self.joysticks = {}
        self.instance_id_values_map = {}
        # RLock protects joystick maps and instance->type mappings for thread-safety and nested calls.
        self._joystick_lock = threading.RLock()
        self.controller_state = ControllerState()

        # Mode flags - default to creep mode enabled on startup but allow overriding via env var
        default_creep_env = os.environ.get("XBEE_DEFAULT_CREEP", "").strip()
        if not default_creep_env:
            self.creep_mode = True
        else:
            self.creep_mode = default_creep_env.lower() in (
                "1",
                "true",
                "yes",
                "on",
                "y",
                "t",
            )
        self.reverse_mode = False
        # Provide a bound input processor for convenience so callers can use controller_manager.handle_* directly.
        # handlers were exposed on the controller manager.
        self.input_processor = InputProcessor(self)

    def handle_hotplug_event(self, event: Event) -> bool:
        """
        Handle controller connection/disconnection events.

        Args:
            event: Pygame event

        Returns:
            bool: True if should quit (controller dc), False otherwise
        """

        # If new device is added
        if event.type == pygame.JOYDEVICEADDED:
            joy = pygame.joystick.Joystick(event.device_index)
            self._add_joystick(joy)
            logger.info("Joystick %d connected", joy.get_instance_id())
            return False

        # If a device is removed
        if event.type == pygame.JOYDEVICEREMOVED:
            self._remove_joystick_instance(event.instance_id)
            logger.info("Joystick %d disconnected", event.instance_id)
            return True

        return False

    def _add_joystick(self, joy):
        """
        Add joystick to internal mappings and detect controller type.
        """
        with self._joystick_lock:
            self.joysticks[joy.get_instance_id()] = joy
            controller_type = self._detect_controller_type(joy.get_name())
            if controller_type:
                self.instance_id_values_map[joy.get_instance_id()] = controller_type

    def _remove_joystick_instance(self, instance_id: int):
        """
        Remove joystick and mapping entries given an instance id.
        """
        with self._joystick_lock:
            if instance_id in self.joysticks:
                del self.joysticks[instance_id]
            if instance_id in self.instance_id_values_map:
                del self.instance_id_values_map[instance_id]

    def _detect_controller_type(self, name: str) -> Optional[str]:
        """Return a controller type string based on the joystick name (case-insensitive)."""
        if not isinstance(name, str):
            return None
        lname = name.lower()
        if "xbox" in lname or "x-box" in lname:
            return CONSTANTS.XBOX.NAME
        if "dinput" in lname:
            return CONSTANTS.N64.NAME
        return None

    def handle_axis_motion(self, event: Event) -> None:
        """
        Process axis motions via the attached input processor.
        """

        # Determine if this is a joystick axis or trigger axis
        joystick_axes = [
            CONSTANTS.XBOX.JOYSTICK.AXIS_LX,
            CONSTANTS.XBOX.JOYSTICK.AXIS_LY,
            CONSTANTS.XBOX.JOYSTICK.AXIS_RX,
            CONSTANTS.XBOX.JOYSTICK.AXIS_RY,
        ]

        if event.axis in joystick_axes:
            self.input_processor.process_joystick_axis(event)
        else:
            self.input_processor.process_trigger_axis(event)

    def handle_button_down(self, event: Event) -> None:
        """
        Handle button down events via the input processor.
        """
        self.input_processor.process_button(event)

    def handle_button_up(self, event: Event) -> None:
        """
        Handle button release events via the input processor.
        """
        self.input_processor.process_button(event)

    def handle_joypad(self, event: Event) -> None:
        """
        Handle D-Pad/joypad events via the input processor.
        """
        self.input_processor.process_joypad(event)

    def handle_controller_added(self, event: Event) -> None:
        """
        Handle controller hotplug add events.
        """
        self.handle_hotplug_event(event)

    def handle_controller_removed(self, event: Event) -> None:
        """
        Handle controller hotplug remove events.
        """
        self.handle_hotplug_event(event)

    def should_quit_on_button(self, event: Event) -> bool:
        """
        Check if the home/start button was pressed to quit.

        Args:
            event: Button event

        Returns:
            bool: True if should quit, False otherwise
        """

        with self._joystick_lock:
            if event.instance_id not in self.instance_id_values_map:
                return False
            controller_type = self.instance_id_values_map[event.instance_id]

        if (
            controller_type == CONSTANTS.XBOX.NAME
            and event.button == CONSTANTS.XBOX.BUTTON.HOME
        ) or (
            controller_type == CONSTANTS.N64.NAME
            and event.button == CONSTANTS.N64.BUTTON.START
        ):
            return True

        return False

    def get_controller_type(self, instance_id: int) -> Optional[str]:
        """
        Get the controller type for a given instance ID.

        Args:
            instance_id: The controller instance ID

        Returns:
            str: "xbox", "n64", or None if not found
        """

        with self._joystick_lock:
            return self.instance_id_values_map.get(instance_id)

    def get_joystick(self, instance_id: int):
        """Return the joystick object for a given instance id, or None if not found.

        Args:
            instance_id: Instance id of the joystick

        Returns:
            Joystick object or None
        """
        with self._joystick_lock:
            return self.joysticks.get(instance_id)

    def has_joysticks(self) -> bool:
        """Return True if there is at least one joystick connected."""
        with self._joystick_lock:
            return bool(self.joysticks)

    def update_mode_flags(
        self, joypad_direction: Union[int, tuple[int, int]], controller_type: str
    ) -> None:
        """
        Updates creep and reverse mode flags based on joypad input.

        Args:
            joypad_direction: Joypad direction tuple
            controller_type: Type of controller
        """
        # Accept case-insensitive controller type (e.g., 'xbox' or 'XBOX')
        controller_name = self.controller_state.canonical_controller_name(
            controller_type
        )
        if controller_name != CONSTANTS.XBOX.NAME:
            return

        values = self.controller_state.get_controller_values(CONSTANTS.XBOX.NAME)
        select_pressed, start_pressed = self._get_select_start_pressed(values)

        logger.debug(
            "Joypad direction: %s, Select: %s, Start: %s",
            joypad_direction,
            select_pressed,
            start_pressed,
        )

        # Map joypad direction to mode changes
        self._apply_mode_change_from_joypad(
            joypad_direction, select_pressed, start_pressed
        )

    def _get_select_start_pressed(self, values: dict) -> tuple:
        """Return tuple (select_pressed, start_pressed) from controller values."""
        select_pressed = (
            values.get(
                CONSTANTS.XBOX.BUTTON.SELECT + CONSTANTS.XBOX.BUTTON_INDEX_OFFSET
            )
            == CONSTANTS.XBOX.BUTTON.ON
        )
        start_pressed = (
            values.get(CONSTANTS.XBOX.BUTTON.START + CONSTANTS.XBOX.BUTTON_INDEX_OFFSET)
            == CONSTANTS.XBOX.BUTTON.ON
        )
        return (select_pressed, start_pressed)

    def _apply_mode_change_from_joypad(
        self,
        joypad_direction: Union[int, tuple[int, int]],
        select_pressed: bool,
        start_pressed: bool,
    ) -> None:
        """Apply mode changes based on the joypad direction and buttons.

        Separated to reduce cognitive complexity in update_mode_flags.
        """
        direction_to_bool = {
            CONSTANTS.XBOX.JOYPAD.UP: True,
            CONSTANTS.XBOX.JOYPAD.DOWN: False,
        }

        # Only index the mapping if we have an int direction that matches the Xbox JOYPAD mapping.
        if (
            select_pressed
            and isinstance(joypad_direction, tuple)
            and joypad_direction in direction_to_bool
        ):
            self.reverse_mode = direction_to_bool[joypad_direction]
            logger.info("reverse %s", "on" if self.reverse_mode else "off")

        if (
            start_pressed
            and isinstance(joypad_direction, tuple)
            and joypad_direction in direction_to_bool
        ):
            self.creep_mode = direction_to_bool[joypad_direction]
            logger.info("creep mode %s", "on" if self.creep_mode else "off")


class InputProcessor:
    """
    Processes different types of controller inputs.
    """

    def __init__(self, controller_manager: ControllerManager):
        """
        Init the input processor.

        Args:
            controller_manager: The controller manager instance
        """

        self.controller_manager = controller_manager
        self.deadband = CONSTANTS.TIMING.DEADBAND_THRESHOLD

    def process_joystick_axis(self, event: Event) -> None:
        """
        Processes joystick axis movement events.

        Args:
            event: The axis movement event
        """

        controller_type = self.controller_manager.get_controller_type(event.instance_id)
        if not controller_type or controller_type == CONSTANTS.N64.NAME:
            return

        # Calc mult based on modes
        multiplier = self._calculate_axis_multiplier(controller_type)

        # Apply deadband
        value = event.value if abs(event.value) >= self.deadband else 0

        # Convert to integer range (update_value will handle bytes conversion)
        constants = (
            CONSTANTS.XBOX if controller_type == CONSTANTS.XBOX.NAME else CONSTANTS.N64
        )
        int_val = self._convert_axis_value(value, multiplier, constants)
        self.controller_manager.controller_state.update_value(
            controller_type, event.axis, int_val
        )

    def process_trigger_axis(self, event: Event) -> None:
        """
        Process trigger axis events.

        Args:
            event: Trigger event
        """

        controller_type = self.controller_manager.get_controller_type(event.instance_id)
        if not controller_type or controller_type == CONSTANTS.N64.NAME:
            return

        # Treat trigger like button
        value = True if event.value > 0 else False

        self.controller_manager.controller_state.update_value(
            controller_type, event.axis, value
        )

    def process_button(self, event: Event) -> None:
        """
        Process button press/release events.

        Args:
            event: Button event
        """

        controller_type = self.controller_manager.get_controller_type(event.instance_id)
        if not controller_type:
            return

        joystick = self.controller_manager.get_joystick(event.instance_id)
        if joystick is None:
            # If joystick disappeared concurrently, ignore the event.
            return
        button_value = joystick.get_button(event.button)

        # Convert pygame's 0/1 to 2-bit encoding (1=OFF, 2=ON)
        # pygame returns: 0 = not pressed, 1 = presed
        # so therefore we  need: 1 = OFF, 2 = ON
        encoded_value = CONSTANTS.XBOX.BUTTON.ON if button_value else CONSTANTS.XBOX.BUTTON.OFF

        # Calc button key offset; use the constant to avoid magic numbers
        key_offset = (
            CONSTANTS.XBOX.BUTTON_INDEX_OFFSET
            if controller_type == CONSTANTS.XBOX.NAME
            else 0
        )
        button_key = event.button + key_offset

        self.controller_manager.controller_state.update_value(
            controller_type, button_key, encoded_value
        )

    def process_joypad(self, event: Event) -> None:
        """
        Process D-pad/joypad events.

        Args:
            event: Joypad event
        """

        controller_type = self.controller_manager.get_controller_type(event.instance_id)
        if not controller_type:
            return

        if controller_type == CONSTANTS.N64.NAME:
            self._process_n64_joypad(event)
        elif controller_type == CONSTANTS.XBOX.NAME:
            self._process_xbox_joypad(event)

    def _calculate_axis_multiplier(self, controller_type: str) -> float:
        """
        Calc the axis mult based on current modes.

        Args:
            controller_type: The controller type

        Returns:
            float: Calculated mult
        """

        if controller_type == CONSTANTS.N64.NAME:
            return CONSTANTS.CONTROLLER_MODES.NORMAL_MULTIPLIER

        multiplier = CONSTANTS.CONTROLLER_MODES.NORMAL_MULTIPLIER

        if self.controller_manager.creep_mode:
            multiplier = CONSTANTS.CONTROLLER_MODES.CREEP_MULTIPLIER

        if self.controller_manager.reverse_mode:
            multiplier = -multiplier

        return multiplier

    def _convert_axis_value(self, value: float, multiplier: float, constants) -> int:
        """
        Convert axis value to integer w/ bounds checking.

        Args:
            value: Axis value (-1.0 to 1.0)
            multiplier: Mult to apply
            constants: Controller consts

        Returns:
            int: Converted value
        """

        new_value = floor(multiplier * value * 100 + constants.JOYSTICK.NEUTRAL_INT)

        # Clamp to valid range
        if new_value < constants.JOYSTICK.MIN_VALUE:
            new_value = constants.JOYSTICK.MIN_VALUE
        elif new_value > constants.JOYSTICK.MAX_VALUE:
            new_value = constants.JOYSTICK.MAX_VALUE

        return new_value

    def _process_n64_joypad(self, event: Event) -> None:
        """
        Process N64 controller joypad events.

        Args:
            event: Joypad event
        """

        x, y = event.value
        working_const = CONSTANTS.N64

        # X axis
        if x == 0:
            self.controller_manager.controller_state.update_value(
                working_const.NAME,
                working_const.BUTTON.DP_LEFT,
                working_const.BUTTON.OFF,
            )
            self.controller_manager.controller_state.update_value(
                working_const.NAME,
                working_const.BUTTON.DP_RIGHT,
                working_const.BUTTON.OFF,
            )
        elif x == -1:
            self.controller_manager.controller_state.update_value(
                working_const.NAME,
                working_const.BUTTON.DP_LEFT,
                working_const.BUTTON.ON,
            )
            self.controller_manager.controller_state.update_value(
                working_const.NAME,
                working_const.BUTTON.DP_RIGHT,
                working_const.BUTTON.OFF,
            )
        elif x == 1:
            self.controller_manager.controller_state.update_value(
                working_const.NAME,
                working_const.BUTTON.DP_LEFT,
                working_const.BUTTON.OFF,
            )
            self.controller_manager.controller_state.update_value(
                working_const.NAME,
                working_const.BUTTON.DP_RIGHT,
                working_const.BUTTON.ON,
            )

        # Y axis
        if y == 0:
            self.controller_manager.controller_state.update_value(
                working_const.NAME,
                working_const.BUTTON.DP_DOWN,
                working_const.BUTTON.OFF,
            )
            self.controller_manager.controller_state.update_value(
                working_const.NAME, working_const.BUTTON.DP_UP, working_const.BUTTON.OFF
            )
        elif y == -1:
            self.controller_manager.controller_state.update_value(
                working_const.NAME,
                working_const.BUTTON.DP_DOWN,
                working_const.BUTTON.ON,
            )
            self.controller_manager.controller_state.update_value(
                working_const.NAME, working_const.BUTTON.DP_UP, working_const.BUTTON.OFF
            )
        elif y == 1:
            self.controller_manager.controller_state.update_value(
                working_const.NAME,
                working_const.BUTTON.DP_DOWN,
                working_const.BUTTON.OFF,
            )
            self.controller_manager.controller_state.update_value(
                working_const.NAME, working_const.BUTTON.DP_UP, working_const.BUTTON.ON
            )

    def _process_xbox_joypad(self, event: Event) -> None:
        """
        Process Xbox controller joypad events for mode switching.

        Args:
            event: Joypad event
        """

        self.controller_manager.update_mode_flags(event.value, CONSTANTS.XBOX.NAME)
