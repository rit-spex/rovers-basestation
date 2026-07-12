# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : protocol.py
# purpose       : make the shared rovers-protocol package importable
#                 and re-export the pieces the basestation uses
# created on    : 7/12/2026 - Ryan
# last modified : 7/12/2026 - Ryan
# ------------------------------------------------------------------
"""Shared protocol access.

The wire format lives in the rovers-protocol repo (protocol.yaml plus the
rover_protocol package). It is normally checked out as a git submodule at
lib/rovers-protocol; a sibling checkout next to this repo also works.
"""

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

for _candidate in (_ROOT / "lib" / "rovers-protocol", _ROOT.parent / "rovers-protocol"):
    if (_candidate / "rover_protocol").exists():
        if str(_candidate) not in sys.path:
            sys.path.insert(0, str(_candidate))
        break

from rover_protocol import CONSTANTS, MessageEncoder  # noqa: E402

# Message id namespace (XBOX_ID, N64_ID, HEARTBEAT_ID, ...)
MSG = CONSTANTS.COMPACT_MESSAGES


def env_flag(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable ("1"/"true"/"yes"/"on" is on)."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


__all__ = ["CONSTANTS", "MessageEncoder", "MSG", "env_flag"]