import importlib
import logging
import sys
import types


def reload_base_station_module():
    """Helper to reload the base_station module cleanly and return it.

    Note: Retained for compatibility with older tests but we now prefer to
    call _get_log_every_updates_default() directly for deterministic
    behavior without relying on module reloads.
    """
    import xbee.app as bs

    return importlib.reload(bs)


def test_env_var_missing_default(monkeypatch):
    # Ensure the env var is not set
    monkeypatch.delenv("BASESTATION_LOG_EVERY_UPDATES", raising=False)
    # Test helper directly to avoid import-time side effects and module reloads.
    from xbee.app import _get_log_every_updates_default

    assert _get_log_every_updates_default() == 0


def test_env_var_numeric_value(monkeypatch):
    monkeypatch.setenv("BASESTATION_LOG_EVERY_UPDATES", "5")
    from xbee.app import _get_log_every_updates_default

    assert _get_log_every_updates_default() == 5


def test_env_var_invalid_value_warns_and_uses_default(monkeypatch, caplog):
    monkeypatch.setenv("BASESTATION_LOG_EVERY_UPDATES", "notanumber")
    caplog.set_level(logging.WARNING)
    from xbee.app import _get_log_every_updates_default

    assert _get_log_every_updates_default() == 0
    assert any(
        "Invalid BASESTATION_LOG_EVERY_UPDATES" in rec.getMessage()
        for rec in caplog.records
    )


def test_env_flag_parsing(monkeypatch):
    from xbee.app import _env_flag

    monkeypatch.delenv("XBEE_INPUT_DIAGNOSTICS", raising=False)
    assert _env_flag("XBEE_INPUT_DIAGNOSTICS", default=True) is True

    monkeypatch.setenv("XBEE_INPUT_DIAGNOSTICS", "0")
    assert _env_flag("XBEE_INPUT_DIAGNOSTICS", default=True) is False

    monkeypatch.setenv("XBEE_INPUT_DIAGNOSTICS", "yes")
    assert _env_flag("XBEE_INPUT_DIAGNOSTICS", default=False) is True


def test_linux_input_diagnostics_warns_when_no_devices(monkeypatch, caplog):
    from xbee.app import _log_linux_input_runtime_diagnostics

    monkeypatch.setattr("xbee.app.sys.platform", "linux")
    monkeypatch.setattr("xbee.app.glob.glob", lambda _pattern: [])
    monkeypatch.setattr("xbee.app.os.access", lambda _path, _mode: True)
    monkeypatch.setitem(
        sys.modules,
        "hid",
        types.SimpleNamespace(enumerate=lambda _vid, _pid: []),
    )

    caplog.set_level(logging.INFO)
    _log_linux_input_runtime_diagnostics(spacemouse_vendor_id=0x256F, inputs_enabled=True)

    messages = [rec.getMessage() for rec in caplog.records]
    assert any("Input diagnostics (Linux)" in msg for msg in messages)
    assert any(
        "No /dev/input/event* or /dev/hidraw* devices are visible" in msg
        for msg in messages
    )
    assert any("No 3Dconnexion HID devices enumerated" in msg for msg in messages)


def test_linux_input_diagnostics_can_be_disabled(monkeypatch, caplog):
    from xbee.app import _log_linux_input_runtime_diagnostics

    monkeypatch.setenv("XBEE_INPUT_DIAGNOSTICS", "0")
    monkeypatch.setattr("xbee.app.sys.platform", "linux")
    caplog.set_level(logging.INFO)

    _log_linux_input_runtime_diagnostics(spacemouse_vendor_id=0x256F, inputs_enabled=True)

    assert not any("Input diagnostics (Linux)" in rec.getMessage() for rec in caplog.records)


def test_linux_input_diagnostics_noop_on_non_linux(monkeypatch, caplog):
    from xbee.app import _log_linux_input_runtime_diagnostics

    monkeypatch.setattr("xbee.app.sys.platform", "win32")
    caplog.set_level(logging.INFO)

    _log_linux_input_runtime_diagnostics(spacemouse_vendor_id=0x256F, inputs_enabled=True)

    assert caplog.records == []
