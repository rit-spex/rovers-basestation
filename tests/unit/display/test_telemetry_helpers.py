from xbee.display.telemetry import resolve_boolean_flag, resolve_estop_status


def test_resolve_boolean_flag_strips_whitespace():
    telemetry = {"enabled": "  false  "}
    assert resolve_boolean_flag(telemetry, ["enabled"]) is False


def test_resolve_boolean_flag_missing_returns_none():
    telemetry = {"other": True}
    assert resolve_boolean_flag(telemetry, ["enabled", "active"]) is None


def test_resolve_boolean_flag_string_true_and_mixed_case_are_normalized():
    assert resolve_boolean_flag({"enabled": "true"}, ["enabled"]) is True
    assert resolve_boolean_flag({"enabled": "True"}, ["enabled"]) is True
    assert resolve_boolean_flag({"enabled": "FALSE"}, ["enabled"]) is False


def test_resolve_boolean_flag_boolean_values_pass_through_unchanged():
    assert resolve_boolean_flag({"enabled": True}, ["enabled"]) is True
    assert resolve_boolean_flag({"enabled": False}, ["enabled"]) is False


def test_resolve_estop_status_not_estopped_string_returns_false():
    telemetry = {"rover_status": "not estopped"}
    assert resolve_estop_status(telemetry) is False


def test_resolve_estop_status_estop_string_returns_true():
    telemetry = {"rover_status": "E-STOP ACTIVE"}
    assert resolve_estop_status(telemetry) is True


def test_resolve_estop_status_nominal_string_returns_false():
    telemetry = {"rover_status": "nominal"}
    assert resolve_estop_status(telemetry) is False


def test_resolve_estop_status_unrecognized_string_returns_none():
    telemetry = {"rover_status": "status unknown"}
    assert resolve_estop_status(telemetry) is None


def test_resolve_estop_status_not_substring_inside_word_does_not_negate():
    telemetry = {"rover_status": "cannot e-stop"}
    assert resolve_estop_status(telemetry) is True


def test_resolve_estop_status_missing_key_returns_none():
    assert resolve_estop_status({}) is None
