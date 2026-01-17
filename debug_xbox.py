import importlib
from typing import Any, Callable, Iterable, cast


def debug_xbox():
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
        while True:
            for event in get_gamepad_fn():
                print(f"{event.ev_type} {event.code}: {event.state}")
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    debug_xbox()
