"""Regression tests for InputEventSource axis normalization."""

from __future__ import annotations

import pytest

from xbee.controller.input_source import InputEventSource


class TestInputSourceAxisNormalization:
    def test_joystick_small_delta_not_amplified(self):
        """Tiny raw joystick changes should stay near neutral.

        Regression target:
        Previous adaptive min/max normalization could turn a 1-count raw delta
        (e.g. 128 -> 129) into ~0.5 normalized value, which then bypasses
        deadband and produces visibly wrong non-neutral outputs.
        """
        source = InputEventSource(enable=False)

        baseline = source._normalize_axis_value(128, "ABS_X", instance_id=1)
        delta = source._normalize_axis_value(129, "ABS_X", instance_id=1)

        assert abs(baseline) < 0.05
        assert abs(delta) < 0.05

    def test_unsigned_raw_mode_can_reach_full_throw(self):
        """Unsigned joystick ranges should still map to near full-scale output."""
        source = InputEventSource(enable=False)

        # Prime mode detection near unsigned center.
        source._normalize_axis_value(128, "ABS_X", instance_id=2)
        left = source._normalize_axis_value(0, "ABS_X", instance_id=2)
        right = source._normalize_axis_value(255, "ABS_X", instance_id=2)

        assert left <= -0.95
        assert right >= 0.95

    def test_signed_raw_mode_near_zero_stays_neutral(self):
        """Signed joystick ranges around zero should not be misclassified."""
        source = InputEventSource(enable=False)

        baseline = source._normalize_axis_value(0, "ABS_Y", instance_id=3)
        delta = source._normalize_axis_value(1, "ABS_Y", instance_id=3)

        assert abs(baseline) < 0.05
        assert abs(delta) < 0.05

    def test_forced_unsigned_mode_handles_off_center_start(self, monkeypatch):
        """Forced unsigned mode allows deterministic handling for unsigned devices."""
        monkeypatch.setenv("XBEE_JOYSTICK_RAW_MODE", "unsigned")
        source = InputEventSource(enable=False)

        left = source._normalize_axis_value(0, "ABS_X", instance_id=4)
        right = source._normalize_axis_value(255, "ABS_X", instance_id=4)

        assert left <= -0.95
        assert right >= 0.95

    @pytest.mark.parametrize("raw_state", [0, 64, 128, 255])
    def test_trigger_axes_remain_normalized_to_unit_interval(self, raw_state: int):
        """Trigger axis scaling remains bounded in [0, 1]."""
        source = InputEventSource(enable=False)

        normalized = source._normalize_axis_value(raw_state, "ABS_Z", instance_id=1)

        assert 0.0 <= normalized <= 1.0
