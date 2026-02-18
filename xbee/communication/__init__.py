"""
Communication package for sending/receiving data.

This package provides the transport layer for sending encoded messages
to the rover, either via real XBee radio hardware or UDP simulation.

DATA FLOW:
    CommunicationManager  (high-level: formatting, dedup, retries)
        |
        +--> XbeeCommunicationManager  (real hardware: XBee radio)
        |    OR
        +--> UdpCommunicationManager   (simulation: UDP sockets)

You usually only interact with CommunicationManager, which picks
the right backend automatically based on simulation_mode.

Modules:
    manager       - CommunicationManager: main interface for sending data
    xbee_backend  - XbeeCommunicationManager: real XBee radio transport
    udp_backend   - UdpCommunicationManager: UDP simulation transport
    heartbeat     - HeartbeatManager: periodic heartbeat signals
"""

from .heartbeat import HeartbeatManager
from .manager import CommunicationManager, MessageFormatter
from .udp_backend import (
    SimulationCommunicationManager,
    UdpCommunicationManager,
    UdpMessage,
)
from .xbee_backend import XbeeCommunicationManager

__all__ = [
    "CommunicationManager",
    "MessageFormatter",
    "XbeeCommunicationManager",
    "UdpCommunicationManager",
    "UdpMessage",
    "SimulationCommunicationManager",
    "HeartbeatManager",
]
