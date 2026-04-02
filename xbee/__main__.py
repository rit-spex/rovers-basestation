"""Entry point for running the xbee package as a module.

Usage: python -m xbee
"""

import sys

from xbee.app import main


def run() -> int:
    try:
        main()
        return 0
    except KeyboardInterrupt:
        print("\nShutdown by user")
        return 0
    except SystemExit:
        raise  # Re-raise to preserve exit code
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    exit_code = run()
    if exit_code != 0:
        raise SystemExit(exit_code)
