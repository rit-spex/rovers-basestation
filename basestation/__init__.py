# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : __init__.py
# purpose       : basestation package marker; repairs the one-shot
#                 EVENT_MAP generator in the inputs library
# created on    : 7/12/2026 - Ryan
# last modified : 11/16/2026
# ------------------------------------------------------------------
"""RIT SPEX rover basestation: controller input -> rover, telemetry -> GUI."""

from basestation.inputs_compat import repair_event_map

# Repair once for anything that imports DeviceManager directly; the hotplug
# monitors also repair before each rescan (see inputs_compat.device_manager).
repair_event_map()
