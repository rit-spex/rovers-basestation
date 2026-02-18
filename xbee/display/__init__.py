"""
Display package for the basestation GUI.

This package provides the graphical interface (or headless fallback)
for showing controller status, telemetry data, and system state.

Usage:
    from xbee.display import create_display
    display = create_display()   # Returns TkinterDisplay or HeadlessDisplay
    display.run()                # Blocks (GUI main loop)

Modules:
    base       - BaseDisplay ABC, HeadlessDisplay, create_display() factory
    gui        - TkinterDisplay: full tkinter GUI
    telemetry  - Helper functions for interpreting telemetry values
"""

from .base import BaseDisplay, HeadlessDisplay, create_display

__all__ = ["BaseDisplay", "HeadlessDisplay", "create_display"]
