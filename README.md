# SPEX Rover Basestation

Control system for the RIT SPEX rover. Supports real XBee hardware or UDP simulation for testing.

## Start

### Python 3.11+

Basestation requires Python 3.11+ (see `pyproject.toml`). Ubuntu 22.04 ships with 3.10 by default, so install 3.11+ when setting up the VM or CI.

**Note for nerds:** Using 3.11 due to changes with default parameters in 3.11 for int.to_bytes() specifically byteorder which defaults to Big-endian in 3.11 but doesn't have a default in 3.10 or below. I dunno I could change this later so we dont have to install newer python but whatever.

### Setup

```bash
# Create and activate virtual environment
python -m venv .venv

# Activate (choose based on your shell)
.venv\Scripts\Activate.ps1     # Windows PowerShell
source .venv/Scripts/activate  # Windows with any Bash thingy
source .venv/bin/activate      # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### Shared protocol submodule

This project depends on the shared protocol package used by both basestation and rover ROS:

```bash
git submodule update --init --recursive
```

Expected submodule location:

- `lib/rovers-protocol`

**Note**: XBee libraries are optional at runtime. `requirements.txt` includes them by default, but simulation-only setups can omit those packages and the system will use UDP simulation mode.

### Running

```bash
python launch_xbee.py
# or
python -m xbee
```

### Headless Mode

For running as a service or on devices without a display:

```bash
XBEE_NO_GUI=1 python -m xbee
```

### Testing

```bash
# Run pytest through the run_tests.py script (defaults to pytest)
python run_tests.py
```

## Configuration

### Simulation vs Real Hardware

In `xbee/config/constants.py`:

```python
SIMULATION_MODE = True   # UDP testing mode
SIMULATION_MODE = False  # Real XBee hardware
```

### Communication Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `DEFAULT_PORT` | Serial port for XBee | `/dev/ttyUSB0` (Linux), `COM9` (Windows) |
| `REMOTE_XBEE_ADDRESS` | Target XBee address | `0013A200423A7DDD` |
| `UDP_BASESTATION_PORT` | Basestation send port | `5000` |
| `UDP_ROVER_PORT` | Rover receive port | `5005` |
| `UDP_TELEMETRY_PORT` | Telemetry receive port | `5002` |

### Controller Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `UPDATE_FREQUENCY` | Message send interval | 40ms |
| `DEADBAND_THRESHOLD` | Joystick deadzone | 0.10 |
| `CREEP_MULTIPLIER` | Slow mode multiplier | 0.2 |

Override creep mode default:
```bash
export XBEE_DEFAULT_CREEP=0  # Disable default creep mode
```

## Core Architecture

The basestation runs on a Raspberry Pi with a monitor and game controllers. It reads controller input, encodes it using the shared protocol, and sends it to the rover via XBee radio. The rover sends telemetry back over UDP, which the GUI displays.

The encoding/decoding logic lives in the **rovers-protocol** shared submodule at `lib/rovers-protocol/`. Both this repo and rovers-ros use the same protocol so changes only need to happen once.

```
  ┌────────────────┐    XBee Radio       ┌─────────────────┐
  |                |   ───────────────>  |                 |
  │ BASESTATION    │   controller data   │  ROVER (ROS 2)  │
  │ (Raspberry Pi) │  <───────────────   │  (Jetson Orin)  │
  │                │   telemetry (UDP)   │                 │
  └────────────────┘                     └─────────────────┘
```

### Modules

```
xbee/
├── app.py                  # BaseStation orchestrator + control loop
├── config/constants.py     # All config (from protocol.yaml)
├── controller/             # Gamepad reading, state, hotplug
├── protocol/encoding.py    # Re-exports MessageEncoder from rover_protocol submodule
├── communication/          # XBee + UDP backends
└── display/                # tkinter GUI + headless fallback

lib/rovers-protocol/        # Shared submodule
├── protocol.yaml           # Source of truth for all messages
└── rover_protocol/         # Python package (codec, constants, schema)
```

### Data Flows

### Controller → Rover

```
Gamepad (USB/Bluetooth)
    │
    v
InputEventSource.poll_events()           # OS-level gamepad events
    │
    v
BaseStation.send_command(event)          # Routes to ControllerManager
    │
    v
InputProcessor                           # Normalizes axis/button values
    │
    v
ControllerState                          # Stores current values per controller
    │
    v
CommunicationManager.send_controller_data()
    │
    v
MessageFormatter.create_xbox_message()   # Calls MessageEncoder.encode_data()
    │                                     # which bit-packs values per protocol.yaml
    v
XbeeCommunicationManager.send_package()  # Actual radio stuff ┐
    -- OR --                                                  |> Based on flag
UdpCommunicationManager.send_package()   # Simulation ────────┘
```

### Rover → Basestation (telemetry mostly)

```
Rover ROS nodes publish to /ROVER/TELEMETRY/* topics
    │
    v
TelemetryUplink ROS node               # Collects topics, encodes with MessageEncoder
    │
    v
UDP packet                             # Sent to basestation_ip:5002
    │
    v
UdpCommunicationManager._receive_loop()
    │
    v
MessageEncoder.decode_data()           # Decodes compact bytes back to dict
    │
    v
BaseStation._handle_telemetry_data()   # Stores in self.telemetry_data
    │
    v
TkinterDisplay.update_telemetry()      # GUI shows latest values
```

### Other Files

| File | Use |
|------|---------|
| **utils/gps.py** | GPS data reading using I2C from the GPS module. |
| **auto_boot/auto_boot.py** | Auto-starts basestation on Raspberry Pi boot. |
| **launch_xbee.py** | Start script — sets up logging and launches basestation. |

## Message Protocol

All message definitions live in `lib/rovers-protocol/protocol.yaml`.

### Format

Compact bit-packed messages for bandwidth efficiency:

| Byte | Content |
|------|---------|
| 0 | Message ID |
| 1-N | Bit-packed signal payload |

### Message IDs (from protocol.yaml)

**To Rover (basestation → rover):**

| ID | Name | Signals |
|----|------|---------|
| `0x01` | heartbeat | timestamp (16-bit) |
| `0x02` | xbox | AXIS_LY, AXIS_RY, A, B, X, Y, LEFT_BUMPER, RIGHT_BUMPER, AXIS_LT, AXIS_RT |
| `0x03` | n64 | A, B, L, R, C_UP, C_DOWN, C_LEFT, C_RIGHT, DP_UP–DP_RIGHT, Z |
| `0x04` | quit | QUIT (1-bit bool) |
| `0x05` | auto_state | auto_state (8-bit) |

**From Rover (rover → basestation telemetry):**

| ID | Name | Signals |
|----|------|---------|
| `0xF0` | life_detection | color_sensor, limit switches, auger, pump, slides, tubes |
| `0xF1` | arm_encoders | base, shoulder, elbow, wrist, claw (all 16-bit) |
| `0xF2` | drive_imu | speed L/R (joystick), yaw/pitch/roll (16-bit) |
| `0xF3` | rover_estop | rover_estop (1-bit bool) |
| `0xF4` | subsystem_enabled | arm, auto, life enabled (1-bit bools) |
| `0xF5` | control_mode | control_mode (8-bit) |

## Development

```bash
pip install -r requirements-dev.txt

black .          # Format
isort .          # Sort imports
ruff check .     # Lint
mypy .           # Type check
```

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `XBEE_NO_GUI` | `""` | Set to `"1"` to disable tkinter GUI |
| `XBEE_DEFAULT_CREEP` | `1` | Set to `"0"` to disable default creep mode |
| `BASESTATION_LOG_EVERY_UPDATES` | `0` | Log every N control loop iterations (0 = debug only) |
| `XBEE_INFLIGHT_WAIT_TIMEOUT` | `30.0` | Timeout (seconds) for XBee inflight message ack |
| `XBEE_TEST_ENABLE_INPUTS` | `0` | Allow controller inputs under pytest |
| `XBEE_JOYSTICK_RAW_MODE` | `""` | Force joystick raw mode (`signed` or `unsigned`) when auto-detection is not reliable |
| `ROVER_PROTOCOL_TRACE` | `""` | Set to `"1"` to enable real-time hex-level protocol tracing for TX/RX messages |

> For nerds that want more details, see [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md).