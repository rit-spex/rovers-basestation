"""
Launcher for XBee control system.

This script handles import paths correctly and provides a convenient
entry point for running the basestation control system.

Usage: python launch_xbee.py
"""

import os
import sys
import warnings

warnings.filterwarnings(
    "ignore", category=UserWarning, message="pkg_resources is deprecated as an API.*"
)
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message="pkg_resources package is slated for removal.*",
)

if __name__ == "__main__":
    # Add current dir to py path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, current_dir)

    try:
        from xbee.core.base_station import main

        main()
    except KeyboardInterrupt:
        print("\nShutdown by user")
        sys.exit(0)
    except SystemExit:
        # Re-raise SystemExit to preserve exit codes
        raise
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)
