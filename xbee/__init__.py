"""XBee Control System Package.

Provides controller input, wire-protocol encoding, communication backends,
and a GUI / headless display for the rover basestation.

Package layout:
    xbee.config         – Constants, controller definitions
    xbee.controller     – Input handling, state, events
    xbee.protocol       – Wire-protocol encoding / decoding
    xbee.communication  – XBee / UDP backends, message formatting
    xbee.display        – tkinter GUI and headless fallback
    xbee.app            – BaseStation orchestrator and main()

"""

from xbee.communication.manager import CommunicationManager, MessageFormatter
from xbee.communication.heartbeat import HeartbeatManager
from xbee.communication.udp_backend import (
    SimulationCommunicationManager,
    UdpCommunicationManager,
    UdpMessage,
)
from xbee.controller.manager import ControllerManager, InputProcessor
from xbee.controller.state import ControllerState
from xbee.protocol.encoding import MessageEncoder

__all__ = [
    "CommunicationManager",
    "ControllerManager",
    "ControllerState",
    "HeartbeatManager",
    "InputProcessor",
    "MessageEncoder",
    "MessageFormatter",
    "SimulationCommunicationManager",
    "UdpCommunicationManager",
    "UdpMessage",
]
