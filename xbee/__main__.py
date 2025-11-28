"""Entry point for running the xbee package as a module.

Usage: python -m xbee
"""

import sys

from .core.base_station import main

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nShutdown by user")
        sys.exit(0)
    except SystemExit:
        raise  # Re-raise to preserve exit code
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
# No else: do not run main() when imported. Main should only be ran when
# executing the package as a script (python -m xbee or `__main__`).
