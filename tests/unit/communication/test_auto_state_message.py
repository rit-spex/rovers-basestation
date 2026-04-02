from xbee.communication.manager import CommunicationManager
from xbee.config.constants import CONSTANTS
from xbee.protocol.encoding import MessageEncoder


def test_send_auto_state_encodes_and_clamps():
    manager = CommunicationManager(
        xbee_device=None, remote_xbee=None, simulation_mode=False
    )
    encoder = MessageEncoder()

    sent_payloads = []

    def fake_send_package(data, skip_duplicate_check=False):
        sent_payloads.append(bytes(data))
        return True

    manager.send_package = fake_send_package  # type: ignore[assignment]

    assert manager.send_auto_state(99) is True
    assert len(sent_payloads) == 1

    decoded, msg_id = encoder.decode_data(sent_payloads[0])
    assert msg_id == CONSTANTS.COMPACT_MESSAGES.AUTO_STATE_ID
    assert decoded["auto_state"] == CONSTANTS.AUTO_STATE.MAX


def test_send_auto_state_deduplicates_identical_payload():
    manager = CommunicationManager(
        xbee_device=None, remote_xbee=None, simulation_mode=False
    )

    calls = {"count": 0}

    def fake_send_package(data, skip_duplicate_check=False):
        calls["count"] += 1
        return True

    manager.send_package = fake_send_package  # type: ignore[assignment]

    assert manager.send_auto_state(2) is True
    assert manager.send_auto_state(2) is True
    assert calls["count"] == 1
