"""
Tests for ControllerManager advanced functionality.
"""

from unittest.mock import Mock, patch

import pytest

from xbee.core.command_codes import CONSTANTS
from xbee.core.controller_manager import (
    ControllerManager,
    ControllerState,
    InputProcessor,
)


class TestControllerStateAdvanced:
    """Test ControllerState advanced functionality."""

    def test_canonical_controller_name_xbox(self):
        """Test canonical name normalization for Xbox."""
        state = ControllerState()

        assert state.canonical_controller_name("xbox") == CONSTANTS.XBOX.NAME
        assert state.canonical_controller_name("XBOX") == CONSTANTS.XBOX.NAME
        assert state.canonical_controller_name("Xbox") == CONSTANTS.XBOX.NAME

    def test_canonical_controller_name_n64(self):
        """Test canonical name normalization for N64."""
        state = ControllerState()

        assert state.canonical_controller_name("n64") == CONSTANTS.N64.NAME
        assert state.canonical_controller_name("N64") == CONSTANTS.N64.NAME

    def test_canonical_controller_name_invalid_type(self):
        """Test canonical name raises TypeError for non-string."""
        state = ControllerState()

        with pytest.raises(TypeError, match="must be a str"):
            state.canonical_controller_name(123)  # type: ignore[arg-type]  # noqa

    def test_get_alias_for_index(self):
        """Test getting string alias for numeric index."""
        state = ControllerState()

        alias = state.get_alias_for_index(
            CONSTANTS.XBOX.NAME, CONSTANTS.XBOX.JOYSTICK.AXIS_LX
        )
        assert alias == CONSTANTS.XBOX.JOYSTICK.AXIS_LX_STR

    def test_get_alias_for_index_not_found(self):
        """Test getting alias returns None for unknown index."""
        state = ControllerState()

        alias = state.get_alias_for_index(CONSTANTS.XBOX.NAME, 9999)
        assert alias is None

    def test_get_numeric_key_for_alias(self):
        """Test getting numeric key for string alias."""
        state = ControllerState()

        key = state.get_numeric_key_for_alias(
            CONSTANTS.XBOX.NAME, CONSTANTS.XBOX.JOYSTICK.AXIS_LX_STR
        )
        assert key == CONSTANTS.XBOX.JOYSTICK.AXIS_LX

    def test_get_numeric_key_for_alias_not_found(self):
        """Test getting numeric key returns None for unknown alias."""
        state = ControllerState()

        key = state.get_numeric_key_for_alias(CONSTANTS.XBOX.NAME, "unknown_alias")
        assert key is None

    def test_update_value_axis_int(self):
        """Test updating axis value with integer."""
        state = ControllerState()

        state.update_value(CONSTANTS.XBOX.NAME, CONSTANTS.XBOX.JOYSTICK.AXIS_LX, 128)

        values = state.get_controller_values(CONSTANTS.XBOX.NAME)
        assert values[CONSTANTS.XBOX.JOYSTICK.AXIS_LX] == b"\x80"

    def test_update_value_axis_bytes(self):
        """Test updating axis value with bytes."""
        state = ControllerState()

        state.update_value(
            CONSTANTS.XBOX.NAME, CONSTANTS.XBOX.JOYSTICK.AXIS_LX, b"\x64"
        )

        values = state.get_controller_values(CONSTANTS.XBOX.NAME)
        assert values[CONSTANTS.XBOX.JOYSTICK.AXIS_LX] == b"\x64"

    def test_update_value_axis_out_of_range(self):
        """Test updating axis value with out of range value raises error."""
        state = ControllerState()

        with pytest.raises(ValueError, match="out of range"):
            state.update_value(
                CONSTANTS.XBOX.NAME, CONSTANTS.XBOX.JOYSTICK.AXIS_LX, 300
            )

    def test_update_value_trigger_bool(self):
        """Test updating trigger value with bool."""
        state = ControllerState()

        state.update_value(CONSTANTS.XBOX.NAME, CONSTANTS.XBOX.TRIGGER.AXIS_LT, True)

        values = state.get_controller_values(CONSTANTS.XBOX.NAME)
        assert values[CONSTANTS.XBOX.TRIGGER.AXIS_LT] is True

    def test_update_value_trigger_int(self):
        """Test updating trigger value with int."""
        state = ControllerState()

        state.update_value(CONSTANTS.XBOX.NAME, CONSTANTS.XBOX.TRIGGER.AXIS_LT, 1)

        values = state.get_controller_values(CONSTANTS.XBOX.NAME)
        assert values[CONSTANTS.XBOX.TRIGGER.AXIS_LT] is True

    def test_update_value_button_bool(self):
        """Test updating button value with bool."""
        state = ControllerState()
        button_key = CONSTANTS.XBOX.BUTTON.A + CONSTANTS.XBOX.BUTTON_INDEX_OFFSET

        state.update_value(CONSTANTS.XBOX.NAME, button_key, True)

        values = state.get_controller_values(CONSTANTS.XBOX.NAME)
        assert values[button_key] == CONSTANTS.XBOX.BUTTON.ON

    def test_update_value_button_out_of_range(self):
        """Test updating button value with out of range value raises error."""
        state = ControllerState()
        button_key = CONSTANTS.XBOX.BUTTON.A + CONSTANTS.XBOX.BUTTON_INDEX_OFFSET

        with pytest.raises(ValueError, match="out of range"):
            state.update_value(CONSTANTS.XBOX.NAME, button_key, 300)

    def test_update_value_unknown_category(self):
        """Test updating value with unknown category accepts value as-is."""
        state = ControllerState()

        # Use a key that's not in any known category
        state.update_value(CONSTANTS.XBOX.NAME, "unknown_key", 42)

        values = state.get_controller_values(CONSTANTS.XBOX.NAME)
        assert values["unknown_key"] == 42

    def test_n64_numeric_button_indices_not_treated_as_axes(self):
        """N64 button indices overlap with joystick axis indices (0/1).

        Regression: ensure updating N64 button index 0/1 stores 2-bit button
        values (1/2), not axis bytes.
        """
        state = ControllerState()

        state.update_value(CONSTANTS.N64.NAME, CONSTANTS.N64.BUTTON.C_DOWN, CONSTANTS.N64.BUTTON.ON)
        state.update_value(CONSTANTS.N64.NAME, CONSTANTS.N64.BUTTON.A, CONSTANTS.N64.BUTTON.OFF)

        values = state.get_controller_values(CONSTANTS.N64.NAME)

        assert values[CONSTANTS.N64.BUTTON.C_DOWN] == CONSTANTS.N64.BUTTON.ON
        assert values[CONSTANTS.N64.BUTTON.C_DOWN_STR] == CONSTANTS.N64.BUTTON.ON
        assert values[CONSTANTS.N64.BUTTON.A] == CONSTANTS.N64.BUTTON.OFF
        assert values[CONSTANTS.N64.BUTTON.A_STR] == CONSTANTS.N64.BUTTON.OFF

    def test_n64_joystick_axes_can_be_stored_under_string_keys(self):
        """N64 joystick axis values should be storable without colliding with buttons."""
        state = ControllerState()

        state.update_value(CONSTANTS.N64.NAME, CONSTANTS.N64.JOYSTICK.AXIS_X_STR, 173)
        state.update_value(CONSTANTS.N64.NAME, CONSTANTS.N64.JOYSTICK.AXIS_Y_STR, 100)

        values = state.get_controller_values(CONSTANTS.N64.NAME)

        assert values[CONSTANTS.N64.JOYSTICK.AXIS_X_STR] == b"\xad"
        assert values[CONSTANTS.N64.JOYSTICK.AXIS_Y_STR] == b"\x64"


class TestControllerManagerAdvanced:
    """Test ControllerManager advanced functionality."""

    def test_detect_controller_type_xbox(self):
        """Test detecting Xbox controller type."""
        manager = ControllerManager()

        assert manager._detect_controller_type("Xbox Controller") == CONSTANTS.XBOX.NAME
        assert manager._detect_controller_type("X-Box Gamepad") == CONSTANTS.XBOX.NAME

    def test_detect_controller_type_n64(self):
        """Test detecting N64 controller type (dinput)."""
        manager = ControllerManager()

        assert (
            manager._detect_controller_type("DInput Controller") == CONSTANTS.N64.NAME
        )

    def test_detect_controller_type_unknown(self):
        """Test detecting unknown controller type."""
        manager = ControllerManager()

        assert manager._detect_controller_type("Generic Gamepad") is None

    def test_detect_controller_type_non_string(self):
        """Test detecting controller type with non-string returns None."""
        manager = ControllerManager()

        assert manager._detect_controller_type(None) is None  # type: ignore[arg-type]  # noqa
        assert manager._detect_controller_type(123) is None  # type: ignore[arg-type]  # noqa

    def test_should_quit_on_button_xbox_home(self):
        """Test quit detection on Xbox home button."""
        manager = ControllerManager()
        manager.instance_id_values_map[0] = CONSTANTS.XBOX.NAME

        event = Mock()
        event.instance_id = 0
        event.button = CONSTANTS.XBOX.BUTTON.HOME

        assert manager.should_quit_on_button(event) is True

    def test_should_quit_on_button_n64_start(self):
        """Test quit detection on N64 start button."""
        manager = ControllerManager()
        manager.instance_id_values_map[0] = CONSTANTS.N64.NAME

        event = Mock()
        event.instance_id = 0
        event.button = CONSTANTS.N64.BUTTON.START

        assert manager.should_quit_on_button(event) is True

    def test_should_quit_on_button_wrong_button(self):
        """Test quit detection returns False for wrong button."""
        manager = ControllerManager()
        manager.instance_id_values_map[0] = CONSTANTS.XBOX.NAME

        event = Mock()
        event.instance_id = 0
        event.button = CONSTANTS.XBOX.BUTTON.A

        assert manager.should_quit_on_button(event) is False

    def test_should_quit_on_button_unknown_controller(self):
        """Test quit detection returns False for unknown controller."""
        manager = ControllerManager()

        event = Mock()
        event.instance_id = 999
        event.button = 0

        assert manager.should_quit_on_button(event) is False

    @patch.dict("os.environ", {"XBEE_DEFAULT_CREEP": "0"})
    def test_creep_mode_env_disabled(self):
        """Test creep mode can be disabled via environment."""
        manager = ControllerManager()

        assert manager.creep_mode is False

    @patch.dict("os.environ", {"XBEE_DEFAULT_CREEP": "1"})
    def test_creep_mode_env_enabled(self):
        """Test creep mode can be enabled via environment."""
        manager = ControllerManager()

        assert manager.creep_mode is True

    def test_update_mode_flags_reverse_mode_on(self):
        """Test updating reverse mode via joypad."""
        manager = ControllerManager()
        # Setup: select button pressed
        manager.controller_state.update_value(
            CONSTANTS.XBOX.NAME,
            CONSTANTS.XBOX.BUTTON.SELECT + CONSTANTS.XBOX.BUTTON_INDEX_OFFSET,
            CONSTANTS.XBOX.BUTTON.ON,
        )
        manager.controller_state.update_value(
            CONSTANTS.XBOX.NAME,
            CONSTANTS.XBOX.BUTTON.START + CONSTANTS.XBOX.BUTTON_INDEX_OFFSET,
            CONSTANTS.XBOX.BUTTON.OFF,
        )

        manager.update_mode_flags(CONSTANTS.XBOX.JOYPAD.UP, CONSTANTS.XBOX.NAME)

        assert manager.reverse_mode is True

    def test_update_mode_flags_reverse_mode_off(self):
        """Test updating reverse mode off via joypad."""
        manager = ControllerManager()
        manager.reverse_mode = True
        # Setup: select button pressed
        manager.controller_state.update_value(
            CONSTANTS.XBOX.NAME,
            CONSTANTS.XBOX.BUTTON.SELECT + CONSTANTS.XBOX.BUTTON_INDEX_OFFSET,
            CONSTANTS.XBOX.BUTTON.ON,
        )
        manager.controller_state.update_value(
            CONSTANTS.XBOX.NAME,
            CONSTANTS.XBOX.BUTTON.START + CONSTANTS.XBOX.BUTTON_INDEX_OFFSET,
            CONSTANTS.XBOX.BUTTON.OFF,
        )

        manager.update_mode_flags(CONSTANTS.XBOX.JOYPAD.DOWN, CONSTANTS.XBOX.NAME)

        assert manager.reverse_mode is False

    def test_update_mode_flags_creep_mode_on(self):
        """Test updating creep mode via joypad."""
        manager = ControllerManager()
        manager.creep_mode = False
        # Setup: start button pressed
        manager.controller_state.update_value(
            CONSTANTS.XBOX.NAME,
            CONSTANTS.XBOX.BUTTON.SELECT + CONSTANTS.XBOX.BUTTON_INDEX_OFFSET,
            CONSTANTS.XBOX.BUTTON.OFF,
        )
        manager.controller_state.update_value(
            CONSTANTS.XBOX.NAME,
            CONSTANTS.XBOX.BUTTON.START + CONSTANTS.XBOX.BUTTON_INDEX_OFFSET,
            CONSTANTS.XBOX.BUTTON.ON,
        )

        manager.update_mode_flags(CONSTANTS.XBOX.JOYPAD.UP, CONSTANTS.XBOX.NAME)

        assert manager.creep_mode is True

    def test_update_mode_flags_non_xbox_ignored(self):
        """Test mode flags update is ignored for non-Xbox controllers."""
        manager = ControllerManager()
        manager.creep_mode = False
        manager.reverse_mode = False

        manager.update_mode_flags(CONSTANTS.XBOX.JOYPAD.UP, CONSTANTS.N64.NAME)

        assert manager.creep_mode is False
        assert manager.reverse_mode is False


class TestInputProcessorAdvanced:
    """Test InputProcessor advanced functionality."""

    def test_process_joystick_axis_n64_processed(self):
        """Test joystick axis processing correctly handles N64 controller."""
        manager = ControllerManager()
        manager.instance_id_values_map[0] = CONSTANTS.N64.NAME
        processor = InputProcessor(manager)

        event = Mock()
        event.instance_id = 0
        event.axis = CONSTANTS.N64.JOYSTICK.AXIS_X  # N64 joystick X axis
        event.value = 0.5

        # Should process the N64 axis movement
        processor.process_joystick_axis(event)

        # Verify the value was updated
        values = manager.controller_state.get_controller_values(CONSTANTS.N64.NAME)
        # Value should be around 150 (neutral 100 + 0.5 * 100 = 150)
        axis_value = values.get(CONSTANTS.N64.JOYSTICK.AXIS_X_STR)
        assert axis_value is not None
        # The value is stored as bytes, convert to int for comparison
        if isinstance(axis_value, bytes):
            axis_value = int.from_bytes(axis_value, "big")
        assert axis_value == 150  # neutral + 0.5 * 100

    def test_process_trigger_axis_n64_ignored(self):
        """Test trigger axis processing ignores N64."""
        manager = ControllerManager()
        manager.instance_id_values_map[0] = CONSTANTS.N64.NAME
        processor = InputProcessor(manager)

        event = Mock()
        event.instance_id = 0
        event.axis = CONSTANTS.XBOX.TRIGGER.AXIS_LT
        event.value = 0.5

        # Should return early without processing
        processor.process_trigger_axis(event)

        # No exception means success

    def test_process_button_unknown_controller_ignored(self):
        """Test button processing ignores unknown controllers."""
        manager = ControllerManager()
        processor = InputProcessor(manager)

        event = Mock()
        event.instance_id = 999
        event.button = 0

        # Should return early without processing
        processor.process_button(event)

        # No exception means success

    def test_process_button_joystick_missing(self):
        """Test button processing handles missing joystick gracefully."""
        manager = ControllerManager()
        manager.instance_id_values_map[0] = CONSTANTS.XBOX.NAME
        # No joystick added
        processor = InputProcessor(manager)

        event = Mock()
        event.instance_id = 0
        event.button = 0

        # Should return early without exception
        processor.process_button(event)

    def test_process_joypad_unknown_controller_ignored(self):
        """Test joypad processing ignores unknown controllers."""
        manager = ControllerManager()
        processor = InputProcessor(manager)

        event = Mock()
        event.instance_id = 999
        event.value = (0, 0)

        # Should return early without processing
        processor.process_joypad(event)

        # No exception means success

    def test_calculate_axis_multiplier_n64(self):
        """Test axis multiplier for N64 is always normal."""
        manager = ControllerManager()
        manager.creep_mode = True
        manager.reverse_mode = True
        processor = InputProcessor(manager)

        multiplier = processor._calculate_axis_multiplier(CONSTANTS.N64.NAME)

        assert multiplier == pytest.approx(CONSTANTS.CONTROLLER_MODES.NORMAL_MULTIPLIER)

    def test_calculate_axis_multiplier_creep_mode(self):
        """Test axis multiplier in creep mode."""
        manager = ControllerManager()
        manager.creep_mode = True
        manager.reverse_mode = False
        processor = InputProcessor(manager)

        multiplier = processor._calculate_axis_multiplier(CONSTANTS.XBOX.NAME)

        assert multiplier == pytest.approx(CONSTANTS.CONTROLLER_MODES.CREEP_MULTIPLIER)

    def test_calculate_axis_multiplier_reverse_creep(self):
        """Test axis multiplier in reverse + creep mode."""
        manager = ControllerManager()
        manager.creep_mode = True
        manager.reverse_mode = True
        processor = InputProcessor(manager)

        multiplier = processor._calculate_axis_multiplier(CONSTANTS.XBOX.NAME)

        assert multiplier == pytest.approx(-CONSTANTS.CONTROLLER_MODES.CREEP_MULTIPLIER)

    def test_convert_axis_value_clamping_max(self):
        """Test axis value is clamped to max."""
        manager = ControllerManager()
        processor = InputProcessor(manager)

        # Need value extreme enough to exceed MAX_VALUE (200)
        # With neutral 100, multiplier 100, value needs to be > 1.0 to exceed 200
        result = processor._convert_axis_value(2.0, 100.0, CONSTANTS.XBOX)

        assert result == CONSTANTS.XBOX.JOYSTICK.MAX_VALUE

    def test_convert_axis_value_clamping_min(self):
        """Test axis value is clamped to min."""
        manager = ControllerManager()
        processor = InputProcessor(manager)

        # Need negative value extreme enough to go below MIN_VALUE (0)
        # With neutral 100, multiplier 100, value needs to be < -1.0 to go below 0
        result = processor._convert_axis_value(-2.0, 100.0, CONSTANTS.XBOX)

        assert result == CONSTANTS.XBOX.JOYSTICK.MIN_VALUE

    def test_process_n64_joypad_x_left(self):
        """Test N64 joypad X-axis left."""
        manager = ControllerManager()
        manager.instance_id_values_map[0] = CONSTANTS.N64.NAME
        processor = InputProcessor(manager)

        event = Mock()
        event.instance_id = 0
        event.value = (-1, 0)

        processor.process_joypad(event)

        values = manager.controller_state.get_controller_values(CONSTANTS.N64.NAME)
        assert values[CONSTANTS.N64.BUTTON.DP_LEFT] == CONSTANTS.N64.BUTTON.ON

    def test_process_n64_joypad_x_right(self):
        """Test N64 joypad X-axis right."""
        manager = ControllerManager()
        manager.instance_id_values_map[0] = CONSTANTS.N64.NAME
        processor = InputProcessor(manager)

        event = Mock()
        event.instance_id = 0
        event.value = (1, 0)

        processor.process_joypad(event)

        values = manager.controller_state.get_controller_values(CONSTANTS.N64.NAME)
        assert values[CONSTANTS.N64.BUTTON.DP_RIGHT] == CONSTANTS.N64.BUTTON.ON

    def test_process_n64_joypad_y_up(self):
        """Test N64 joypad Y-axis up."""
        manager = ControllerManager()
        manager.instance_id_values_map[0] = CONSTANTS.N64.NAME
        processor = InputProcessor(manager)

        event = Mock()
        event.instance_id = 0
        event.value = (0, 1)

        processor.process_joypad(event)

        values = manager.controller_state.get_controller_values(CONSTANTS.N64.NAME)
        assert values[CONSTANTS.N64.BUTTON.DP_UP] == CONSTANTS.N64.BUTTON.ON

    def test_process_n64_joypad_y_down(self):
        """Test N64 joypad Y-axis down."""
        manager = ControllerManager()
        manager.instance_id_values_map[0] = CONSTANTS.N64.NAME
        processor = InputProcessor(manager)

        event = Mock()
        event.instance_id = 0
        event.value = (0, -1)

        processor.process_joypad(event)

        values = manager.controller_state.get_controller_values(CONSTANTS.N64.NAME)
        assert values[CONSTANTS.N64.BUTTON.DP_DOWN] == CONSTANTS.N64.BUTTON.ON
