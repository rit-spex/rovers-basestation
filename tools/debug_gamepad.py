# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : debug_gamepad.py
# purpose       : print raw gamepad events to check button mappings
# created on    : 7/12/2026 - Ryan
# last modified : 7/12/2026 - Ryan
# ------------------------------------------------------------------
"""Print raw gamepad events. Run it, mash buttons, read the codes."""

import inputs

if __name__ == "__main__":
    print("Listening for gamepad events (Ctrl+C to stop)...")
    try:
        while True:
            for event in inputs.get_gamepad():
                print(f"{event.ev_type} {event.code}: {event.state}")
    except KeyboardInterrupt:
        print("\nStopped.")