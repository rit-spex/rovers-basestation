"""
Tests for xbee/__main__.py entry point.
"""

import sys
from unittest.mock import Mock


class TestXbeeMain:
    """Test xbee package main entry point."""

    def test_main_calls_base_station_main(self):
        """Test that running the package as a script calls base_station.main()."""
        # Inject a stub module so that executing `python -m xbee` does not call the real base_station
        import importlib
        import runpy
        import types

        stub_mod = types.ModuleType("xbee.app")
        stub_mod.main = Mock()  # type: ignore[attr-defined]

        old_mod = sys.modules.get("xbee.app")
        try:
            sys.modules["xbee.app"] = stub_mod
            # Ensure the module is reimported fresh for the test
            importlib.invalidate_caches()
            if "xbee.__main__" in sys.modules:
                del sys.modules["xbee.__main__"]
            runpy.run_module("xbee", run_name="__main__")
            # Run the package as a script to simulate `python -m xbee` which should call main()
            # The stub main should have been called once during script execution
            stub_mod.main.assert_called_once()
        finally:
            # Clean up xbee.__main__ to avoid test interference
            if "xbee.__main__" in sys.modules:
                del sys.modules["xbee.__main__"]
            # Restore previous module if any
            if old_mod is not None:
                sys.modules["xbee.app"] = old_mod
            else:
                del sys.modules["xbee.app"]

    def test_main_module_can_be_found(self):
        """Test module can be loaded for running."""
        # Test that the module can be imported
        import importlib.util

        spec = importlib.util.find_spec("xbee.__main__")
        assert spec is not None

    def test_main_entry_point_structure(self):
        """Test the __main__ module has expected structure (loads cleanly without starting app when imported)."""
        import importlib
        import types

        stub_mod = types.ModuleType("xbee.app")
        stub_mod.main = Mock()  # type: ignore[attr-defined]

        old_mod = sys.modules.get("xbee.app")
        try:
            sys.modules["xbee.app"] = stub_mod
            importlib.invalidate_caches()
            if "xbee.__main__" in sys.modules:
                del sys.modules["xbee.__main__"]
            importlib.import_module("xbee.__main__")
            # Verify the stub main was not called during import of the module
            # since importing should not trigger the main entry point.
            stub_mod.main.assert_not_called()
        finally:
            # Clean up xbee.__main__ to avoid test interference
            if "xbee.__main__" in sys.modules:
                del sys.modules["xbee.__main__"]
            if old_mod is not None:
                sys.modules["xbee.app"] = old_mod
            else:
                del sys.modules["xbee.app"]
