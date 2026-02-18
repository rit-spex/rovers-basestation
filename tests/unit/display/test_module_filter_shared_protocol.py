from xbee.display.telemetry import filter_telemetry_for_module


def test_filter_telemetry_for_module_includes_new_life_keys():
    telemetry = {
        "color_sensor": 12,
        "limit_switch_1": True,
        "arm_base_position": 100,
        "drive_speed_left": 0.4,
    }

    filtered = filter_telemetry_for_module(telemetry, "life")

    assert filtered["color_sensor"] == 12
    assert filtered["limit_switch_1"] is True
    assert "arm_base_position" not in filtered


def test_filter_telemetry_for_module_includes_new_arm_keys():
    telemetry = {
        "arm_base_position": 10,
        "shoulder_position": 11,
        "color_sensor": 1,
    }

    filtered = filter_telemetry_for_module(telemetry, "arm")

    assert filtered["arm_base_position"] == 10
    assert filtered["shoulder_position"] == 11
    assert "color_sensor" not in filtered
