"""
Launcher for XBee control system cause apparently no one knows how to run my code.
Should handle import paths correctly.
"""

import sys
import os

# Add current dir to py path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    from xbee.core.xbee_refactored import main
    main()
# I copied and pasted this from stack overflow cause it looked smart:
except KeyboardInterrupt:
    print("\nShutdown by user")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()