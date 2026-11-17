# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : test_gui_display.py
# purpose       : display freshness rules (no Tk widget required)
# created on    : 11/16/2026
# ------------------------------------------------------------------
"""Basestation tab freshness: local input state must not blank out while
the rover has not sent telemetry yet."""

from basestation.gui import TELEMETRY_TIMEOUT, telemetry_stale

NOW = 1000.0


def test_no_telemetry_ever_is_not_stale():
    # The pad/keyboard/devices and link status must stay visible while the
    # rover is connected but silent; only stale rover data is cleared.
    assert not telemetry_stale({}, NOW)


def test_fresh_telemetry_is_not_stale():
    assert not telemetry_stale({"_received_at": NOW - 0.1}, NOW)


def test_telemetry_that_went_quiet_is_stale():
    old = NOW - TELEMETRY_TIMEOUT - 0.1
    assert telemetry_stale({"_received_at": old}, NOW)


def test_non_numeric_received_at_is_ignored():
    assert not telemetry_stale({"_received_at": None}, NOW)
    assert not telemetry_stale({"_received_at": "not a timestamp"}, NOW)
