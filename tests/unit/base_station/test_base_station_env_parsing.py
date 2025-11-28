import importlib
import logging


def reload_base_station_module():
    """Helper to reload the base_station module cleanly and return it.

    Note: Retained for compatibility with older tests but we now prefer to
    call _get_log_every_updates_default() directly for deterministic
    behavior without relying on module reloads.
    """
    import xbee.core.base_station as bs

    return importlib.reload(bs)


def test_env_var_missing_default(monkeypatch):
    # Ensure the env var is not set
    monkeypatch.delenv("BASESTATION_LOG_EVERY_UPDATES", raising=False)
    # Test helper directly to avoid import-time side effects and module reloads.
    from xbee.core.base_station import _get_log_every_updates_default

    assert _get_log_every_updates_default() == 0


def test_env_var_numeric_value(monkeypatch):
    monkeypatch.setenv("BASESTATION_LOG_EVERY_UPDATES", "5")
    from xbee.core.base_station import _get_log_every_updates_default

    assert _get_log_every_updates_default() == 5


def test_env_var_invalid_value_warns_and_uses_default(monkeypatch, caplog):
    monkeypatch.setenv("BASESTATION_LOG_EVERY_UPDATES", "notanumber")
    caplog.set_level(logging.WARNING)
    from xbee.core.base_station import _get_log_every_updates_default

    assert _get_log_every_updates_default() == 0
    assert any(
        "Invalid BASESTATION_LOG_EVERY_UPDATES" in rec.getMessage()
        for rec in caplog.records
    )
