from xbee.config.constants import CONSTANTS
from xbee.controller.events import JOYBUTTONDOWN, InputEvent
from xbee.controller.manager import ControllerManager


def test_bumper_updates_auto_state_clamped_range():
    manager = ControllerManager()
    manager._add_device(1, "Xbox Controller")

    # At minimum already, left bumper should not go below min.
    left_event = InputEvent(
        type=JOYBUTTONDOWN,
        instance_id=1,
        button=CONSTANTS.XBOX.BUTTON.LEFT_BUMPER,
        value=1,
    )
    manager.handle_button_down(left_event)
    assert manager.auto_state == CONSTANTS.AUTO_STATE.MIN

    # Increment more than max and ensure clamped.
    right_event = InputEvent(
        type=JOYBUTTONDOWN,
        instance_id=1,
        button=CONSTANTS.XBOX.BUTTON.RIGHT_BUMPER,
        value=1,
    )
    for _ in range(20):
        manager.handle_button_down(right_event)

    assert manager.auto_state == CONSTANTS.AUTO_STATE.MAX

    # Decrement once from max.
    manager.handle_button_down(left_event)
    assert manager.auto_state == CONSTANTS.AUTO_STATE.MAX - 1
