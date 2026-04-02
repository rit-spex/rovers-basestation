"""Small utility to print raw Xbox controller events via ``inputs``.

Useful for debugging local controller mappings outside the full app.
"""

import importlib
from collections.abc import Callable, Iterable
from typing import Any, cast


def _iter_events(get_gamepad_fn: Callable[[], Iterable[Any]]) -> Iterable[Any]:
    """Yield events from the ``inputs`` gamepad stream forever."""
    while True:
        yield from get_gamepad_fn()


def debug_xbox() -> None:
    try:
        inputs = importlib.import_module("inputs")
    except Exception as exc:
        print(f"inputs library not available: {exc}")
        return

    get_gamepad = getattr(inputs, "get_gamepad", None)
    if not callable(get_gamepad):
        print("inputs.get_gamepad not available in installed inputs package")
        return
    get_gamepad_fn = cast(Callable[[], Iterable[Any]], get_gamepad)

    print("Listening for gamepad events (Ctrl+C to stop)...")
    try:
        for event in _iter_events(get_gamepad_fn):
            print(f"{event.ev_type} {event.code}: {event.state}")
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    debug_xbox()
