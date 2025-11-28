"""
Top-level `utils` package.

This package provides shared utilities for the rover basestation.
"""

from __future__ import annotations

import importlib
import sys

from .bytes import convert_to_bytes, validate_byte_sequence


def _alias_module(alias: str, target: str) -> None:
    """Register a {alias} -> {target} alias in sys.modules if target is available.

    This helps keep imports working on case-insensitive vs case-sensitive
    filesystems during the migration of module names.
    """
    if alias in sys.modules:
        return
    try:
        target_mod = importlib.import_module(target)
    except Exception:
        return
    sys.modules[alias] = target_mod


# Try to ensure both `utils.gps` and `utils.GPS` are available as importable
# modules by aliasing the existing module if the other does not exist.
_alias_module("utils.gps", "utils.GPS")
_alias_module("utils.GPS", "utils.gps")

__all__ = ["convert_to_bytes", "validate_byte_sequence"]
