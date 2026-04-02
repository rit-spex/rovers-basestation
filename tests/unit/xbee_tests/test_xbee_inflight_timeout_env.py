from __future__ import annotations

import pytest

from xbee.communication.xbee_backend import XbeeCommunicationManager


def test_xbee_inflight_wait_timeout_env_zero(monkeypatch):
    monkeypatch.setenv("XBEE_INFLIGHT_WAIT_TIMEOUT", "0")
    with pytest.raises(ValueError) as excinfo:
        XbeeCommunicationManager()
    assert "XBEE_INFLIGHT_WAIT_TIMEOUT must be a positive number" in str(excinfo.value)


def test_xbee_inflight_wait_timeout_env_negative(monkeypatch):
    monkeypatch.setenv("XBEE_INFLIGHT_WAIT_TIMEOUT", "-5")
    with pytest.raises(ValueError) as excinfo:
        XbeeCommunicationManager()
    assert "XBEE_INFLIGHT_WAIT_TIMEOUT must be a positive number" in str(excinfo.value)


def test_xbee_inflight_wait_timeout_env_invalid(monkeypatch):
    monkeypatch.setenv("XBEE_INFLIGHT_WAIT_TIMEOUT", "abc")
    with pytest.raises(ValueError) as excinfo:
        XbeeCommunicationManager()
    assert "Invalid XBEE_INFLIGHT_WAIT_TIMEOUT value" in str(excinfo.value)
