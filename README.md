# SPEX Rover Basestation

Control system for the rover. Works with real XBee hardware or UDP simulation for testing.

## Quick Start

### Setup
```bash
# Install virtualenv if you don't have it
pip install virtualenv

# Create and activate virtual environment
virtualenv venv
source venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

**Note**: XBee libraries are optional. If they're not installed, the system automatically switches to simulation mode. Install the full requirements for real rover comms.

### Running
```bash
python launch_xbee.py
```

Or:
```bash
python -m xbee
```

### Testing
```bash
python run_tests.py        # Interactive menu
python run_tests.py --pytest   # Automated tests
python run_tests.py --human    # Human-readable test output
python run_tests.py --both     # Run both
```

## Config

### Simulation vs Real Hardware

Edit `xbee/core/command_codes.py`:
```python
SIMULATION_MODE = True   # UDP testing mode
SIMULATION_MODE = False  # Real XBee hardware
```

### UDP Ports (Simulation Mode)

Check `xbee/core/command_codes.py` for port settings:
- `UDP_BASESTATION_PORT = 5000` - Basestation sends from here
- `UDP_ROVER_PORT = 5001` - Rover receives commands here
- `UDP_TELEMETRY_PORT = 5002` - Telemetry data comes back here

### XBee Settings (Real Hardware)

Also in `command_codes.py`:
- `DEFAULT_PORT = "COM9"` - Serial port for XBee
- `DEFAULT_BAUD_RATE = 230400` - Baud rate
- `REMOTE_XBEE_ADDRESS` - Target XBee address

## How things work

### Controller Flow

```
User Input → Pygame Events → ControllerManager → InputProcessor 
→ MessageFormatter/MessageCodec → CommunicationManager → Rover
```

### Message Formats

The code supports two msg formats:

**Old Format (10 bytes, compact)**
- Used by `MessageFormatter` 
- Fixed size, bit-packed controller data
- Good for embedded systems with limited bandwidth

Format:
```
[START][LY][RY][BTN1][BTN2][START][N64_B1][N64_B2][N64_B3][N64_B4]
   1     1   1    1     1     1       1       1       1       1
```

**New Format (variable size, JSON)**
- Used by `MessageCodec`
- Header: type (1 byte) + msg ID (4 bytes) + timestamp (8 bytes) + length (2 bytes)
- Payload: JSON data (variable length)
- Better for debugging and extensibility

Format:
```
[TYPE][MSG_ID][TIMESTAMP][LENGTH][JSON_PAYLOAD]
  1      4        8         2        varies
```

- TYPE (1 byte)
  - Msg type ID
  - EX: `0x01` = command, `0x02` = telemetry, `0x03` = heartbeat
  - Lets the receiver to quickly categorize incoming messages

- MSG_ID (4 bytes)
  - Unique msg ID
  - Can be used for tracking and anti-duplication

- TIMESTAMP (8 bytes)
  - Unix timestamp in ms
  - Lets you do time based syncing and calc latency
  - 64-bit int (could probably lower but whatev)

- LENGTH (2 bytes)
  - Size of JSON_PAYLOAD in bytes
  - Can be 0
  - Max payload size: 65,535 bytes
  - Lets receiver to allocate appropriate buffer

- JSON_PAYLOAD (variable length)
  - Optional, can be empty
  - command/telemetry data
  - Ex: `{"speed": 128, "direction": "forward"}`

The compact format should be used for rover comms. See the compact msgs section below:

## Sending Messages

### Quick Example

```python
from xbee.core.communication import CommunicationManager

# Create comm manager
comm = CommunicationManager(xbee_device, remote_xbee)

# Send a simple 2-byte msg
comm.send_compact_message([0xCA, 0x01])
```

### Built-in Message Helpers

For common tasks, use these helper methods (they're already in `CommunicationManager`):

```python
# Send a heartbeat (3 bytes)
comm.send_heartbeat()

# Send status update (4 bytes)
comm.send_status_update(motor_speed=128, battery_level=85, temperature=25)

# Send error code (3 bytes)
comm.send_error_code(error_code=42, subsystem_id=1)

# Send GPS position (9 bytes)
comm.send_gps_position(latitude=40.7128, longitude=-74.0060)

# Send sensor reading (4 bytes)
comm.send_sensor_reading(sensor_id=5, value=1234)
```

### Creating Custom Messages

**Step 1**: Pick a msg ID and add it to `xbee/core/command_codes.py`

```python
class COMPACT_MESSAGES:
    # Reserved IDs - don't use these
    CONTROLLER_DATA = 0xDE
    QUIT = 0xFE
    HEARTBEAT = 0xAA
    
    # Pre-defined IDs
    STATUS = 0xB0
    ERROR = 0xE0
    GPS = 0xC0
    SENSOR = 0xD0
    
    # Add yours here (any unused value from 0x00-0xFF)
    CAMERA = 0xCA
    ARM = 0xA0
    SCIENCE = 0xDD
```

**Step 2**: Send your msg

```python
from xbee.core.command_codes import CONSTANTS

# 2-byte camera command
comm.send_compact_message([CONSTANTS.COMPACT_MESSAGES.CAMERA, 0x01])

# Multi-byte arm position command
comm.send_compact_message([CONSTANTS.COMPACT_MESSAGES.ARM, 45, 90, 120, 0])
```

**Step 3** (optional): Add a helper method to `CommunicationManager`

This makes it easier to call repeatedly. Add this to `xbee/core/communication.py`:

```python
def send_camera_cmd(self, cmd: int) -> bool:
    """Send a 2-byte camera command."""
    return self.send_compact_message([0xCA, cmd])

# Now you can just do:
comm.send_camera_cmd(1)
```

### Receiving Messages

On the rover side, read the first byte to identify the msg type, then parse the rest:

```python
def handle_message(data: bytes):
    msg_id = data[0]
    
    if msg_id == 0xCA:  # Camera
        cmd = data[1]
        handle_camera(cmd)
        
    elif msg_id == 0xA0:  # Arm
        joint1, joint2, joint3, gripper = data[1:5]
        move_arm(joint1, joint2, joint3, gripper)
        
    elif msg_id == 0xB0:  # Status
        motor, battery, temp = data[1:4]
        update_status(motor, battery, temp)
```

## Data Packing Tips

To keep msgs small, here's how to pack different data types:

### 16-bit Integers (0-65535) → 2 bytes

```python
# Example: packing the value 1234

# Sender
value = 1234
high_byte = (value >> 8) & 0xFF
low_byte = value & 0xFF
comm.send_compact_message([0xDE, high_byte, low_byte])

# Receiver
value = (high_byte << 8) | low_byte  # Returns 1234
```

### Floats → 4 bytes

```python
import struct

# Example: sending temperature 23.5°C

# Sender
temp = 23.5
temp_bytes = struct.pack('>f', temp)  # Big-endian float
comm.send_compact_message([0xEF, *temp_bytes])

# Receiver
temp = struct.unpack('>f', data[1:5])[0]  # Returns 23.5
```

### 8 Boolean Flags → 1 byte

```python
# Example: system status flags

# Sender - pack 8 true/false values into one byte
flags = 0
flags |= (1 << 0)  # motor_on = True
flags |= (1 << 1)  # camera_on = True
flags |= (0 << 2)  # arm_on = False
flags |= (1 << 7)  # emergency_stop = True
comm.send_compact_message([0xF1, flags])

# Receiver - unpack the flags
motor_on = (flags >> 0) & 1   # Returns 1
camera_on = (flags >> 1) & 1  # Returns 1
arm_on = (flags >> 2) & 1     # Returns 0
emergency = (flags >> 7) & 1  # Returns 1
```

## File Organization

```
launch_xbee.py          - Main launcher script
run_tests.py            - Test runner

xbee/
  __main__.py           - Entry point (python -m xbee)
  core/
    command_codes.py         - Constants and config
    xbee_refactored.py       - Main control system
    controller_manager.py    - Controller input handling
    communication.py         - XBee comms + MessageFormatter
    udp_communication.py     - Simulation mode comms
    message_system.py        - MessageCodec (JSON format)
    heartbeat.py             - Heartbeat manager
    tkinter_display.py       - GUI display
```

## System Architecture

Here's how stuff connects to each other:

```
┌─────────────────────────────────────────────────────────────┐
│              XbeeControlRefactored (Main)                   │
│                                                             │
│  - Coordinates all components                               │
│  - Chooses XBee or UDP based on SIMULATION_MODE             │
└─────────────────────────────────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           │                  │                  │
           ▼                  ▼                  ▼
    ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
    │ Controller  │   │ Heartbeat   │   │  Tkinter    │
    │  Manager    │   │  Manager    │   │  Display    │
    └─────────────┘   └─────────────┘   └─────────────┘
           │                  │                  │
           ▼                  │                  │
    ┌─────────────┐           │                  │
    │   Input     │           │                  │
    │ Processor   │           │                  │
    └─────────────┘           │                  │
           │                  │                  │
           └──────────┬───────┘                  │
                      │                          │
                      ▼                          │
            ┌──────────────────┐                 │
            │ Communication    │◄────────────────┘
            │   Manager        │
            └──────────────────┘
                      │
         ┌────────────┴────────────┐
         │                         │
         ▼                         ▼
┌─────────────────┐       ┌─────────────────┐
│ MessageFormatter│       │ SimulationComm  │
│  (bit-packed)   │       │   Manager       │
└─────────────────┘       └─────────────────┘
         │                         │
         ▼                         ▼
┌─────────────────┐       ┌─────────────────┐
│  XBee Hardware  │       │  UDP Network    │
│   (Real Rover)  │       │   (Testing)     │
└─────────────────┘       └─────────────────┘
```

Controller input:

```
User Input (physical controller)
    │
    ▼
Pygame Events (button/joystick)
    │
    ▼
ControllerManager (captures state)
    │
    ▼
InputProcessor (applies modes: creep, reverse)
    │
    ▼
MessageFormatter (packs into bytes)
    │
    ▼
CommunicationManager (sends via XBee or UDP)
    │
    ▼
Rover receives data
```

## Controller Settings

You can tweak controller behavior in `command_codes.py`:

- `UPDATE_FREQUENCY`   - How often to send msgs (default: 40ms)
- `DEADBAND_THRESHOLD` - Joystick deadzone (default: 0.10)
- `CREEP_MULTIPLIER`   - Slow mode speed multiplier (default: 20)
- `REVERSE_MULTIPLIER` - Reverse mode multiplier (default: -100)

Xbox and N64 button mappings are also defined there if you need to remap anything.