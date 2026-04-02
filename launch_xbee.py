"""
Launcher for XBee control system.

This script handles import paths correctly and provides a convenient
entry point for running the basestation control system.

Usage: python launch_xbee.py
"""

import os
import sys
import warnings


def _configure_warning_filters() -> None:
    warnings.filterwarnings(
        "ignore",
        category=UserWarning,
        message="pkg_resources is deprecated as an API.*",
    )
    warnings.filterwarnings(
        "ignore",
        category=UserWarning,
        message="pkg_resources package is slated for removal.*",
    )


def _prepend_repo_root() -> None:
    """Ensure the current repository root is importable."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)


def main() -> int:
    """Run the basestation launcher and return a process exit code."""
    _configure_warning_filters()
    _prepend_repo_root()

    try:
        from xbee.app import main as app_main

        app_main()
        return 0
    except KeyboardInterrupt:
        print("\nShutdown by user")
        return 0
    except SystemExit:
        # Re-raise SystemExit to preserve explicit exit codes from app code.
        raise
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
