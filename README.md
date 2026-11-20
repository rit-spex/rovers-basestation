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

To run without physical controllers, add simulated input devices:

```bash
python -m basestation --sim-inputs
```

This adds a **Sim Inputs** tab inside the main basestation window with
sliders and buttons for the Xbox sticks, triggers, buttons and drive mode,
plus N64, SpaceMouse, and a full on-screen keyboard whose mapped
life-detection keys are highlighted. The XBee link is simulated over UDP in
the same way. The simulated N64 is disabled by default; tick **Enable
simulated N64** to use it.

When launched with `rovers-ros/scripts/sim.sh`, the same controls also
appear in Gazebo under **Simulation Control → Sim Inputs**. The Gazebo
panel sends small JSON datagrams to the basestation on
`127.0.0.1:47813` (`BASESTATION_SIM_CONTROL_PORT`), so the protocol
encoding remains in the basestation and is not duplicated in C++.

Gazebo includes a **Simulation Control** panel directly in the Gazebo window
(loaded from the world GUI plugin):

- Choose the Gazebo rover build. The selection is saved and can be applied
  with **Restart simulation** (restarts only Gazebo and the rover stack).
- Enable arm backdrive and move each joint with a slider. Backdrive bypasses
  the IK target stream; disabling it synchronises the IK target to the
  backdriven pose.

The simulation banner has the module mode selector: **None**, **Arm**,
**Life Detection**, and **Autonomous**. The selected mode controls which
module panel is shown. Keyboard bindings follow the mode: Life Detection
shows the life keys, and Arm shows the arm bindings in both
the Input Devices panel and the simulated keyboard tab.

The robot hardware configuration itself is a Gazebo setting, not a
basestation setting. Launch the rover stack with `robot_config` (see the
`rovers-ros` simulation launch) and the basestation will follow the reported
subsystem telemetry.

To keep the simulated Xbox/N64/keyboard but drive with the physical
SpaceMouse (sent to the rover over the normal link):

```bash
python -m basestation --sim-inputs --real-spacemouse
```

The main basestation Arm panel shows a joint table with each joint's
current angle, motor lock (`X`), and active homing (`X`), an end-effector
pose table (Cartesian XYZ and roll/pitch/yaw), and colored mode/status
chips for Pick and Place, Flipped, Planar, Zenith, Homing, Flipping, Joint Drive,
position/orientation locks, gripper drive, and the solenoid. The rover
publishes the measured pose in the `arm_pose` telemetry packet; until the
first one arrives the pose table shows placeholders.

Example readout with the rover connected (angles in degrees, pose position
in inches, rotation in degrees):

```
JOINT    ANGLE LOCK HOME
Base      12.3  [x]  [ ]
Shldr    -45.0  [ ]  [x]
Elbow     67.9  [ ]  [ ]
WstBnd    12.0  [ ]  [ ]
WstTst    -8.0  [x]  [ ]
Gripper   25.0  [ ]  [ ]

ERROR: -----

Limit Types
F     Flipped    [OFF]
P     Planar     [OFF]
Z     Zenith     [OFF]

Drive Modes
I     Position   [ON ]
J     Joint      [OFF]

Actions
F     Flipping   [OFF]
H     Homing All [OFF]
G     Guide      [ON ]
R     Rest       [OFF]
-     Solenoid   [OFF]

Target Locks
Q     Pos Lock   [OFF]
O     Ori Lock   [ON ]

Lock: 1-5   Lock All: L
Home: Shift+1-5

ARM TELEMETRY: LIVE
Last Packet: 17:45:36   |  00s ago

END EFFECTOR POSE
|A|    X |     Y |     Z |
|T| 22.5 | -11.0 |  18.3 |
|R|  1.1 |  -1.9 |  89.5 |
```

Headless (service / no display):

```bash
XBEE_NO_GUI=1 python -m basestation
```

Headless mode refuses the UDP fallback: if the XBee cannot be opened it exits
non-zero (systemd restarts it until the radio is back). Set
`BASESTATION_SIMULATION=1` to run headless simulation on purpose.

### Autoboot

`auto_boot/` starts the basestation at boot, GUI included. It launches
immediately, so the window comes up and shows "Waiting for rover
telemetry..." until the rover answers — it does not block on the radio.

```bash
./auto_boot/setup.sh                     # rebuild .venv
./auto_boot/setup.sh --install-service   # write + enable the systemd unit
```

The helper takes flags when a deployment needs different behavior:

```bash
.venv/bin/python3 auto_boot/auto_boot.py --wait      # block for the rover ping first
.venv/bin/python3 auto_boot/auto_boot.py --headless  # no GUI
```

The generated systemd unit exports `DISPLAY=:0`, `XAUTHORITY`, and
`XDG_RUNTIME_DIR` so the GUI can appear under the service. If no X server
is reachable it falls back to the headless display automatically.

## Controls

| Input | Action |
|-------|--------|
| Xbox left/right stick (Y) | drive |
| Xbox LT / RT | trigger buttons |
| hold START + Xbox LB / RB | autonomous state -1 / +1 |
| hold SELECT + D-pad up/down | reverse mode on/off |
| hold START + D-pad left/right | decrease/increase drive speed by 25% |
| Xbox HOME or N64 START | quit (sends QUIT to the rover) |
| keyboard Q W S H E R 1-4 Z X C V B | life detection controls (Life Detection mode) |
| keyboard F / H / I / J / V / P / G / Q / O | arm flip / home / position drive / joint drive / PnP / planar / guide / position lock / orientation lock (Arm mode) |
| keyboard Z | zenith straight-up test pose (Arm mode) |
| keyboard L | lock all joints; locks only, never unlocks (Arm mode) |
| keyboard R | Rest mode placeholder, rules TBD (Arm mode) |
| keyboard 1-5 | toggle joint lock 1-5 (Arm mode) |
| keyboard Shift+1-5 | home joint 1-5 (Arm mode) |
| keyboard Left / Right | jog the arm base (Arm mode) |
| keyboard PageUp / PageDown | jog the arm elbow (Arm mode) |
| keyboard Up / Down | drive the gripper (Arm mode) |
| SpaceMouse | 6DOF arm control |

Keyboard settings follow the selected module mode: Life Detection mode uses
the life keys, Arm mode uses the arm bindings derived from
`invKin202627` (camera and test-overlay keys stay local and are not sent).
The basestation owns the key-to-action map: arm actions are sent over the
link as per-action press states (0 = idle, 1 = just pressed, 2 = held,
3 = just released), not as a key bitmask, so the rover only reacts to
"just pressed". The radio is one shared channel, so idle state is not sent:
a stream (Xbox drive, SpaceMouse, keyboard, arm states) is sent every cycle
while it is active, and when it returns to idle the idle value is repeated for
a short burst (5 frames) so a dropped frame cannot leave the rover holding the
last drive command or held jog. Edges and auto-state changes go out once as
they happen. `L` is basestation-only: it is never encoded into `arm_state`, and
is expanded into the individual joint-lock actions before transmission.

The Gazebo rover stack takes a `robot_config` launch argument (`drivebase`,
`arm_drivebase`, or `life_drivebase`) and reports it over telemetry.

The Arm Module panel has an **ERROR** row that shows the last arm command
rejection, such as `Octant 5 requires Planar - press P` or `Planar needs the
base within +/-5 deg`. The rover sends the error code and argument in the
`arm_status` telemetry message; the basestation renders the text. The banner
clears on the next successful arm command, and re-appears on every repeated
press of a failing key.

Unplugging any input device also quits, which stops the rover this is intended and for safety.

## Module map

```
basestation/
  app.py         control loop + main()
  gamepads.py    Xbox/N64 reading, mode flags, hotplug
  spacemouse.py  SpaceMouse HID reader
  keyboard.py    life/arm keys with press states
  simulated_input_devices.py  simulated controllers + panel (--sim-inputs)
  arm_view/      standalone 3D renderer (not wired into the app)
  comms.py       XBee/UDP link, dedup, telemetry decode
  gui.py         tkinter GUI + headless fallback
  gui_arm_elements.py  Arm panel: joint table, pose, modes, errors
  protocol.py    shared rovers-protocol import shim
tools/           debug_gamepad.py, gps_reader.py
auto_boot/       boot helper + systemd service (starts the GUI)
tests/           wire-format and behavior tests
```

## Configuration

Everything shared (ports, message IDs, timing, controller mappings) comes
from `protocol.yaml` in the submodule. Environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `XBEE_NO_GUI` | off | headless mode |
| `BASESTATION_SIMULATION` | off | force UDP simulation even with a radio |
| `BASESTATION_SIM_INPUTS` | off | use on-screen simulated controllers |
| `BASESTATION_REAL_SPACEMOUSE` | off | with sim inputs, read the physical SpaceMouse |
| `XBEE_PORT` / `XBEE_BAUD` | from protocol.yaml | XBee serial port settings |
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
