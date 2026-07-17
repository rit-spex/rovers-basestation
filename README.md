# SPEX Rover Basestation

Control system for the RIT SPEX rover. Reads game controllers, a SpaceMouse,
and a keyboard; encodes their state with the shared rover protocol; and sends
it to the rover over XBee radio (or UDP when no radio is present). Telemetry
from the rover is decoded and shown in a tkinter GUI.

```
                      XBee radio / UDP
                      
  +----------------+  ----------------->  +-----------------+
  | BASESTATION    |   controller data    |  ROVER (ROS 2)  |
  | (Raspberry Pi) |  <-----------------  |  (Jetson Orin)  |
  +----------------+   telemetry          +-----------------+
          |                                       |
          +--------- lib/rovers-protocol ---------+
                    (shared git submodule)
```

The wire format lives entirely in
[rovers-protocol](https://github.com/rit-spex/rovers-protocol)
(`protocol.yaml`). This repo never defines message bytes itself.

## Setup

Requires Python 3.10+.

```bash
git clone --recurse-submodules https://github.com/rit-spex/rovers-basestation
cd rovers-basestation
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Running

```bash
python -m basestation
```

With no XBee radio attached it automatically runs in **UDP simulation mode**,
sending to the same loopback ports the `rovers-ros` `xbee_udp` node listens
on, so you can test end-to-end against the ROS stack on one machine.

Headless (service / no display):

```bash
XBEE_NO_GUI=1 python -m basestation
```

Headless mode refuses the UDP fallback: if the XBee cannot be opened it exits
non-zero (systemd restarts it until the radio is back). Set
`BASESTATION_SIMULATION=1` to run headless simulation on purpose.

## Controls

| Input | Action |
|-------|--------|
| Xbox left/right stick (Y) | drive |
| Xbox LT / RT | trigger buttons |
| Xbox LB / RB | autonomous state -1 / +1 |
| hold SELECT + D-pad up/down | reverse mode on/off |
| hold START + D-pad up/down | creep mode on/off |
| Xbox HOME or N64 START | quit (sends QUIT to the rover) |
| keyboard Q W S H E R 1-4 Z X C V B | life detection controls |
| SpaceMouse | 6DOF arm control |

Unplugging any input device also quits, which stops the rover this is intended and for safety.

## Module map

```
basestation/
  app.py         control loop + main()
  gamepads.py    Xbox/N64 reading, mode flags, hotplug
  spacemouse.py  SpaceMouse HID reader
  keyboard.py    life-detection keys with press states
  comms.py       XBee/UDP link, dedup, telemetry decode
  gui.py         tkinter GUI + headless fallback
  protocol.py    shared rovers-protocol import shim
tools/           debug_gamepad.py, gps_reader.py
auto_boot/       systemd service for the Pi
tests/           wire-format and behavior tests
```

## Configuration

Everything shared (ports, message IDs, timing, controller mappings) comes
from `protocol.yaml` in the submodule. Environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `XBEE_NO_GUI` | off | headless mode |
| `BASESTATION_SIMULATION` | off | force UDP simulation even with a radio |
| `XBEE_PORT` / `XBEE_BAUD` | from protocol.yaml | XBee serial port settings |
| `XBEE_DEFAULT_CREEP` | `1` | start in creep mode |
| `XBEE_JOYSTICK_RAW_MODE` | `signed` | set `unsigned` for 0-255 stick adapters |
| `XBEE_TRIGGER_THRESHOLD` | `0.05` | trigger press threshold (0-1) |
| `ROVER_PROTOCOL_TRACE` | on in simulation | log every tx/rx packet |

## Ports (UDP simulation)

| Port | Direction | What |
|------|-----------|------|
| 5005 | basestation -> rover | encoded controller messages |
| 5002 | rover -> basestation | encoded telemetry |

* Please let a maintainer know if you change these ports on either end

## Testing

```bash
pip install pytest
pytest
```

## Known gaps

- Arm control modes ([#20](https://github.com/rit-spex/rovers-basestation/issues/20))
  need a new to-rover message in `protocol.yaml` first; not implemented here.