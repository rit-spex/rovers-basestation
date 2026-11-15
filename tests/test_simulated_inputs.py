"""The simulated input bundle used when --sim-inputs is active."""

from basestation.simulated_input_devices import (SimGamepads, SimKeyboard,
                                                 SimSpaceMouse,
                                                 SimulatedInputs)
from basestation.spacemouse import SpaceMouse


class FakeControl:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


def test_bundle_exposes_the_three_devices():
    sim = SimulatedInputs()
    gamepads, spacemouse, keyboard = sim.devices
    assert isinstance(gamepads, SimGamepads)
    assert isinstance(spacemouse, SimSpaceMouse)
    assert isinstance(keyboard, SimKeyboard)
    assert sim.control is None and sim.panel is None

    control = FakeControl()
    sim.control = control
    sim.stop()
    assert control.stopped and sim.control is None


def test_bundle_can_use_the_real_spacemouse():
    sim = SimulatedInputs(real_spacemouse=True)
    assert isinstance(sim.spacemouse, SpaceMouse)
    assert not isinstance(sim.spacemouse, SimSpaceMouse)
