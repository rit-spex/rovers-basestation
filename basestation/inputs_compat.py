# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : inputs_compat.py
# purpose       : work around inputs 0.5's one-shot type-code map so
#                 hotplug rescans keep working
# created on    : 11/16/2026
# last modified : 11/16/2026
# ------------------------------------------------------------------
"""Compatibility helpers for the optional ``inputs`` library.

``inputs`` 0.5 stores ``EVENT_MAP['type_codes']`` as a generator.  Importing
the module builds one ``DeviceManager``, which drains that generator, so the
next ``DeviceManager()`` has no ``LED`` type code and construction raises
``KeyError: 'LED'`` on Linux.  The basestation rebuilds a ``DeviceManager``
every half second to detect hotplug, so the second scan would always fail.

Rebuild the generator entry from ``EVENT_TYPES`` before every scan instead of
relying on the package ``__init__`` running first.
"""

try:
    import inputs
except Exception:  # inputs is optional; the callers handle None
    inputs = None


def repair_event_map(module=None):
    """Make ``module.EVENT_MAP['type_codes']`` re-iterable.

    Safe to call repeatedly and on test doubles without those attributes.
    ``module`` defaults to the real ``inputs`` module.
    """
    module = inputs if module is None else module
    if module is None:
        return
    event_map = getattr(module, "EVENT_MAP", None)
    event_types = getattr(module, "EVENT_TYPES", None)
    if not event_map or not event_types:
        return
    items = event_map.items() if isinstance(event_map, dict) else event_map
    module.EVENT_MAP = tuple(
        (key, tuple((name, code) for code, name in event_types))
        if key == "type_codes" else (key, value)
        for key, value in items)


def device_manager(module=None):
    """Build a fresh ``DeviceManager``, repairing ``EVENT_MAP`` first.

    Returns ``None`` when ``inputs`` is unavailable.
    """
    module = inputs if module is None else module
    if module is None:
        return None
    repair_event_map(module)
    return module.DeviceManager()
