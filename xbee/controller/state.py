"""
Controller state storage.

Stores the current value of every button and axis for each controller type.
Values are stored as a dict keyed by controller name ("xbox" or "n64"),
where each value is a dict mapping input keys to their current values.

The dual-key system:
    Each input has BOTH a numeric key and a string alias key.
    Example: Xbox button A has numeric key 6 and string alias "A".
    When you update one, both keys are updated automatically.
    This exists because the gamepad driver gives us numeric indices,
    but the wire protocol uses string keys.

Value types by input category:
    - Axes:     bytes (single byte, 0-200, 100=center)
    - Triggers: bool (True=pressed, False=released)
    - Buttons:  int (1=OFF, 2=ON in 2-bit encoding)
"""

import threading
from typing import Any, Dict, Optional, Union

from xbee.config.constants import CONSTANTS
from xbee.protocol.encoding import MessageEncoder

BYTES_LIKE = (bytes, bytearray, memoryview)

# Pre-computed sets for fast category lookup (avoids rebuilding on every call)
_XBOX = CONSTANTS.XBOX
_N64 = CONSTANTS.N64

AXIS_ALIASES = frozenset(
    {
        _XBOX.JOYSTICK.AXIS_LX_STR,
        _XBOX.JOYSTICK.AXIS_LY_STR,
        _XBOX.JOYSTICK.AXIS_RX_STR,
        _XBOX.JOYSTICK.AXIS_RY_STR,
        _N64.JOYSTICK.AXIS_X_STR,
        _N64.JOYSTICK.AXIS_Y_STR,
    }
)

TRIGGER_ALIASES = frozenset(
    {
        _XBOX.TRIGGER.AXIS_LT_STR,
        _XBOX.TRIGGER.AXIS_RT_STR,
    }
)

BUTTON_ALIASES = frozenset(
    {
        _XBOX.BUTTON.A_STR,
        _XBOX.BUTTON.B_STR,
        _XBOX.BUTTON.X_STR,
        _XBOX.BUTTON.Y_STR,
        _XBOX.BUTTON.LEFT_BUMPER_STR,
        _XBOX.BUTTON.RIGHT_BUMPER_STR,
        _XBOX.BUTTON.START_STR,
        _XBOX.BUTTON.SELECT_STR,
        _N64.BUTTON.A_STR,
        _N64.BUTTON.B_STR,
        _N64.BUTTON.C_UP_STR,
        _N64.BUTTON.C_DOWN_STR,
        _N64.BUTTON.C_LEFT_STR,
        _N64.BUTTON.C_RIGHT_STR,
        _N64.BUTTON.L_STR,
        _N64.BUTTON.R_STR,
        _N64.BUTTON.Z_STR,
        _N64.BUTTON.DP_UP_STR,
        _N64.BUTTON.DP_DOWN_STR,
        _N64.BUTTON.DP_LEFT_STR,
        _N64.BUTTON.DP_RIGHT_STR,
    }
)


class ControllerState:
    """Stores current values for all controller inputs.

    Thread-safe: all reads and writes go through an RLock.
    """

    def __init__(self):
        # Maps: numeric_index -> string_alias for each controller
        self.index_conversion = self._build_index_conversion()
        # Reverse maps: string_alias -> numeric_index
        self.reverse_index_conversion = {
            name: {str_key: num_key for num_key, str_key in mapping.items()}
            for name, mapping in self.index_conversion.items()
        }

        # Current values: controller_name -> {key: value}
        self.values: Dict[str, Dict[Any, Any]] = {}
        self._values_lock = threading.RLock()

        # Populate with defaults from the message encoder
        self._initialize_values_from_messages()

    def _build_index_conversion(self) -> dict:
        """Build the numeric-index-to-string-alias mapping for each controller."""
        xbox = CONSTANTS.XBOX
        n64 = CONSTANTS.N64
        offset = xbox.BUTTON_INDEX_OFFSET

        return {
            xbox.NAME: {
                # Joystick axes
                xbox.JOYSTICK.AXIS_LX: xbox.JOYSTICK.AXIS_LX_STR,
                xbox.JOYSTICK.AXIS_LY: xbox.JOYSTICK.AXIS_LY_STR,
                xbox.JOYSTICK.AXIS_RX: xbox.JOYSTICK.AXIS_RX_STR,
                xbox.JOYSTICK.AXIS_RY: xbox.JOYSTICK.AXIS_RY_STR,
                # Triggers
                xbox.TRIGGER.AXIS_LT: xbox.TRIGGER.AXIS_LT_STR,
                xbox.TRIGGER.AXIS_RT: xbox.TRIGGER.AXIS_RT_STR,
                # Buttons (offset to avoid collision with axis indices)
                xbox.BUTTON.A + offset: xbox.BUTTON.A_STR,
                xbox.BUTTON.B + offset: xbox.BUTTON.B_STR,
                xbox.BUTTON.X + offset: xbox.BUTTON.X_STR,
                xbox.BUTTON.Y + offset: xbox.BUTTON.Y_STR,
                xbox.BUTTON.LEFT_BUMPER + offset: xbox.BUTTON.LEFT_BUMPER_STR,
                xbox.BUTTON.RIGHT_BUMPER + offset: xbox.BUTTON.RIGHT_BUMPER_STR,
                xbox.BUTTON.START + offset: xbox.BUTTON.START_STR,
                xbox.BUTTON.SELECT + offset: xbox.BUTTON.SELECT_STR,
            },
            n64.NAME: {
                # N64 joystick axes are NOT included here because their indices
                # (0, 1) collide with button indices (C_DOWN=0, A=1).
                # N64 axes are stored under string keys directly instead.
                n64.BUTTON.A: n64.BUTTON.A_STR,
                n64.BUTTON.B: n64.BUTTON.B_STR,
                n64.BUTTON.C_UP: n64.BUTTON.C_UP_STR,
                n64.BUTTON.C_DOWN: n64.BUTTON.C_DOWN_STR,
                n64.BUTTON.C_LEFT: n64.BUTTON.C_LEFT_STR,
                n64.BUTTON.C_RIGHT: n64.BUTTON.C_RIGHT_STR,
                n64.BUTTON.L: n64.BUTTON.L_STR,
                n64.BUTTON.R: n64.BUTTON.R_STR,
                n64.BUTTON.Z: n64.BUTTON.Z_STR,
                n64.BUTTON.DP_UP: n64.BUTTON.DP_UP_STR,
                n64.BUTTON.DP_DOWN: n64.BUTTON.DP_DOWN_STR,
                n64.BUTTON.DP_LEFT: n64.BUTTON.DP_LEFT_STR,
                n64.BUTTON.DP_RIGHT: n64.BUTTON.DP_RIGHT_STR,
            },
        }

    def _initialize_values_from_messages(self) -> None:
        """Populate default values from the encoder's message definitions."""
        encoder = MessageEncoder()
        known_types = set(self.index_conversion.keys())

        for _msg_id, message in encoder.get_messages().items():
            name = message.get("name")
            if not isinstance(name, str) or name not in known_types:
                continue
            self.values[name] = {}
            for signal_name, signal in message.get("values", {}).items():
                if not hasattr(signal, "default_value"):
                    continue
                # Find numeric key if one exists for this signal name
                num_key = self.reverse_index_conversion.get(name, {}).get(signal_name)
                key = num_key if num_key is not None else signal_name
                self.update_value(name, key, signal.default_value)

    # --- Public API ---

    def canonical_controller_name(self, controller_type: str) -> str:
        """Normalize controller type string (case-insensitive).

        >>> state.canonical_controller_name("XBOX")
        'xbox'
        """
        if not isinstance(controller_type, str):
            raise TypeError("controller_type must be a str")
        lower = controller_type.lower()
        if lower == CONSTANTS.XBOX.NAME.lower():
            return CONSTANTS.XBOX.NAME
        if lower == CONSTANTS.N64.NAME.lower():
            return CONSTANTS.N64.NAME
        return controller_type

    def get_alias_for_index(self, controller_type: str, index: int) -> Optional[str]:
        """Get the string alias for a numeric index (e.g., 6 -> "A" for xbox)."""
        name = self.canonical_controller_name(controller_type)
        return self.index_conversion.get(name, {}).get(index)

    def get_numeric_key_for_alias(
        self, controller_type: str, alias: str
    ) -> Optional[int]:
        """Get the numeric index for a string alias (e.g., "A" -> 6 for xbox)."""
        name = self.canonical_controller_name(controller_type)
        return self.reverse_index_conversion.get(name, {}).get(alias)

    def get_controller_values(self, controller_type: str) -> Dict:
        """Get a copy of current values for a controller type.

        Returns a shallow copy so callers can iterate without races.
        """
        name = self.canonical_controller_name(controller_type)
        with self._values_lock:
            vals = self.values.get(name)
            return vals.copy() if vals else {}

    def update_value(self, controller_type: str, key: Union[int, str], value) -> None:
        """Update a controller input value.

        Args:
            controller_type: "xbox" or "n64"
            key: Numeric index or string alias for the input
            value: The new value (type depends on input category)

        Value types by category:
            Axis:    int (0-255) or bytes (1 byte) -> stored as bytes
            Trigger: bool or int -> stored as bool
            Button:  int (1=OFF, 2=ON) or bool -> stored as int
        """
        name = self.canonical_controller_name(controller_type)
        with self._values_lock:
            self.values.setdefault(name, {})

            # Normalize value based on input category
            converted = self._convert_value(name, key, value)
            # Store under both numeric and string keys
            self._store_value(name, key, converted)

    # --- Internal helpers ---

    def _convert_value(self, name: str, key: Union[int, str], value):
        """Normalize a value based on its input category (axis/trigger/button)."""
        alias = self._get_alias(name, key)
        category = self._categorize(alias)

        if category == "axis":
            return self._normalize_axis(key, value)
        if category == "trigger":
            return self._normalize_trigger(key, value)
        if category == "button":
            return self._normalize_button(key, value)
        return value  # Unknown category: pass through

    def _store_value(self, name: str, key: Union[int, str], converted) -> None:
        """Store value under both the provided key and its alias (if any)."""
        self.values[name][key] = converted

        mapping = self.index_conversion.get(name, {})
        if isinstance(key, int) and key in mapping:
            # Numeric key -> also store under string alias
            self.values[name][mapping[key]] = converted
        elif isinstance(key, str):
            # String key -> also store under numeric index
            num_key = self.reverse_index_conversion.get(name, {}).get(key)
            if num_key is not None:
                self.values[name][num_key] = converted

    def _get_alias(self, name: str, key: Union[int, str]) -> Optional[str]:
        """Get the string alias for a key, or the key itself if already a string."""
        if isinstance(key, int):
            return self.index_conversion.get(name, {}).get(key)
        if isinstance(key, str):
            return key
        return None

    def _categorize(self, alias: Optional[str]) -> str:
        """Categorize an alias as 'axis', 'trigger', 'button', or 'unknown'."""
        if alias is None:
            return "unknown"
        if alias in AXIS_ALIASES:
            return "axis"
        if alias in TRIGGER_ALIASES:
            return "trigger"
        if alias in BUTTON_ALIASES:
            return "button"
        return "unknown"

    def _normalize_axis(self, key, value) -> bytes:
        """Convert axis value to a single byte (0-255)."""
        if isinstance(value, int):
            if value < 0 or value > 255:
                raise ValueError(f"Axis value out of range for key {key}: {value}")
            return int(value).to_bytes(1, byteorder="big")
        if isinstance(value, BYTES_LIKE):
            raw = bytes(value)
            if len(raw) != 1:
                raise ValueError(
                    f"Axis value must be single byte for key {key}; got {len(raw)}"
                )
            return raw
        raise ValueError(f"Unsupported axis value type for key {key}: {type(value)}")

    def _normalize_trigger(self, key, value) -> bool:
        """Convert trigger value to bool."""
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return bool(value)
        raise ValueError(f"Unsupported trigger value type for key {key}: {type(value)}")

    def _normalize_button(self, key, value) -> int:
        """Convert button value to 2-bit encoding (1=OFF, 2=ON)."""
        if isinstance(value, bool):
            return CONSTANTS.XBOX.BUTTON.ON if value else CONSTANTS.XBOX.BUTTON.OFF
        if isinstance(value, int):
            if value in (0, CONSTANTS.XBOX.BUTTON.OFF, CONSTANTS.XBOX.BUTTON.ON):
                return CONSTANTS.XBOX.BUTTON.OFF if value == 0 else int(value)
            raise ValueError(f"Button value out of range for key {key}: {value}")
        raise ValueError(f"Unsupported button value type for key {key}: {type(value)}")
