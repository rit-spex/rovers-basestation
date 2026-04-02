"""Re-export CONSTANTS, DataType, INPUT_TYPE from the rover_protocol package."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


def _ensure_shared_protocol_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    candidates = (
        repo_root / "lib" / "rovers-protocol",
        repo_root.parent / "rovers-protocol",
    )
    for candidate in candidates:
        if candidate.exists():
            candidate_str = str(candidate)
            if candidate_str not in sys.path:
                sys.path.insert(0, candidate_str)


_ensure_shared_protocol_on_path()


_shared = importlib.import_module("rover_protocol")
CONSTANTS = _shared.CONSTANTS
DataType = _shared.DataType
INPUT_TYPE = _shared.INPUT_TYPE

__all__ = ["CONSTANTS", "DataType", "INPUT_TYPE"]
