from __future__ import annotations

import pytest

from xbee.communication.udp_backend import (
    SimulationCommunicationManager,
    UdpCommunicationManager,
    UdpMessage,
)


def test_udp_message_handler_receives_parsed_udpmessage(monkeypatch):
    # Avoid binding sockets in __init__ for test; don't start the background thread
    monkeypatch.setattr(UdpCommunicationManager, "_setup_sockets", lambda self: None)
    manager = UdpCommunicationManager()

    # Prepare a UdpMessage and encode it
    msg = UdpMessage("telemetry", {"battery": 12.5}, timestamp=123.456)
    msg_bytes = msg.to_json().encode("utf-8")

    received = {}

    def handler(udp_msg: UdpMessage):
        # Handler should receive a UdpMessage object
        assert isinstance(udp_msg, UdpMessage)
        # Check the contents are preserved
        assert udp_msg.message_type == "telemetry"
        assert udp_msg.data["battery"] == pytest.approx(12.5)
        # Timestamp should be preserved (tolerant comparison)
        assert udp_msg.timestamp == pytest.approx(123.456)
        received["called"] = True

    # Register handler and call _handle_received_message with bytes
    manager.register_message_handler("telemetry", handler)
    manager._handle_received_message(msg_bytes)

    assert received.get("called", False)


def test_simulation_manager_register_telemetry_handler(monkeypatch):
    monkeypatch.setattr(UdpCommunicationManager, "_setup_sockets", lambda self: None)
    # Prevent starting receiving thread in SimulationCommunicationManager
    monkeypatch.setattr(UdpCommunicationManager, "start", lambda self: None)
    sim = SimulationCommunicationManager()

    captured = {}

    def telemetry_handler(data: dict):
        assert isinstance(data, dict)
        captured["data"] = data

    # Register telemetry handler; SimulationCommunicationManager should wrap and register UdpMessage handler
    sim.register_telemetry_handler(telemetry_handler)

    # Manually create a telemetry message and invoke the underlying manager's handler
    msg = UdpMessage("telemetry", {"temp": 22.1})
    sim.udp_manager._handle_received_message(msg.to_json().encode("utf-8"))

    assert "data" in captured
    assert captured["data"]["temp"] == pytest.approx(22.1)
