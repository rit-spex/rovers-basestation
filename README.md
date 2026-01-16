# SPEX Rover Basestation

Control system for the RIT SPEX rover. Supports real XBee hardware or UDP simulation for testing.

## Start

### Python 3.12+ (in case basestation isnt check this)

Basestation needs at least python 3.11, the ubuntu version we use for SPEX in the VM is 22.04 which has a default official python version of 3.10 which wont work due to changes with default parameters in 3.11 for int.to_bytes() specifically byteorder which defaults to Big-endian in 3.11 but doesn't have a default in 3.10 or below

^
though tbh i might just pass in the argument and supress warnings so that we dont gotta install a higher version every time someone new joins, but for now the ci-cd pipeline is gonna use ubuntu 22.04 and py 3.11.

Install SDL2: `sudo apt-get install libsdl2-dev`

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

**Note**: XBee libraries are optional. If not installed, the system automatically uses simulation mode.

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

In `xbee/core/command_codes.py`:

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

The basestation is organized into modules, including ones to handle controller input, communication with the rover (note this may be moved to a lib), and provide a UI for updates.

```
*not all files are shown

                    [BaseStation]
                    Main control loop is here and also handles
                    pygame events for controller and cleanup
                    on shutdown
                                     ^
                                     | explanation
                                     |
  start script       init         control
[launch_xbee.py]------------> [base_station.py]-----.
                                    ^ |             |
   And then there is the tkinter    | |             |
   display which is the GUI of      | |             |
   the program, this communicates   | | info        |
   back and forth with the control  | |             |
                                    | v             |
                              [tkinter_display.py]--+--. explanation
                                     GUI            |  |
      .---------------------------------------------*  *-> [TkinterDisplay]
      |                                                    [HeadlessDisplay]
      |   [ControllerManager]                              GUI display using tkinter
      |   [ControllerState]                                for controller stuff,
      |   [InputProcessor]                                 telemetry, and modes.
      |   Control also communicates the pygame             Goes to headless mode for
      |   events to controller_manager.py which            daemon/service operation.
      |   processes the inputs from the controller
      |   and tracks the connected controller(s)                    Simulation
      |   along with all the button, joystick, and     .-> [udp_communication.py]
      |   flags for things like creep & reverse        |   [UdpCommunicationManager]
      |                                                |   [SimulationCommunicationManager]
      *----------------------.                         |   UDP based communication using
                             |                         |   network based msg transmission
                             v                         |   for testing without hardware.
                   [controller_manager.py]             |   Has simulated telemetry
                             |                         |   processing and reception.
                             | controller state        |
                             |                         |
       /```````````````\     v     /````````````````````
      |      .-------[communication.py]-------.
      |      |      general msg handling      |                  Real Hardware
      |      |                                |        .-> [xbee_communication.py]
      |      *-> [CommunicationManager]       |        |   [XbeeCommunicationManager]
      |          [MessageFormatter]           |        |   Xbee based communication to
      |          Formats msgs and transmits.  |        |   rover. Manages the actual
      |          API for sending:             |        |   Xbee radio transmissions
      |           - controller data           |        |   and has duplicate
      |           - heartbeat                 |        |   supression and retries.
      |           - custom msgs               |        |   Also has "in-flight" msg
      |          Where hardware vs simulation |        |   tracking, aka tracking the
      |          mode is abstracted           |        |   rover's status and sending
      |                                       |        |   commands over.
      |                      .----------------*        |
      |         (dependency) | data encoding           |
      |                      v                         |
      |      .---------[encoding.py]                   |
      |      |                                         |
      |      *-> [MessageEncoder]                      |
      |          [Signal]                              |
      |          Technically for both encoding         |
      |          and decoding, I didn't make           |
      |          the name, ask Tyler. Packs            |
      |          compact msgs into efficiently         |
      |          bits wise with Signal defs.           |
      |                                                |
      *------------------------------------------------*

\                                                                                          /
 *```````````````````````````````````````````\/```````````````````````````````````````````*
                                     [command_codes.py]
                                     [CONSTANTS]
                                     Constants and configs.
                                     Has ALL repository wide settings,
                                     controller mappings, message IDs,
                                     and tuning params.
```

#### Util Files

| File | Use |
|------|---------|
| **utils/gps.py** | GPS data reading using I2C. Reads NMEA sentences from the GPS module on the rover and parses out location data. May be deprecated when lidar-based localization is implemented. |
| **auto_boot/auto_boot.py** | Auto boot for the raspberry pi we have serving as the basestation on the rover to launch the basestation script on system startup after letting XBee connect first. |
| **launch_xbee.py** | Start script. Sets up the logging and starts the basestation. |

#### Other Files

| File | Use |
|------|---------|
| **pyproject.toml** | Repo's config for python tooling for Black, isort, Ruff, and pytest. |
| **requirements.txt** | Dependencies. |
| **requirements-dev.txt** | Dev dependencies for linting, testing, and type checking. |
| **run_tests.py** | Test runner. |

### File Connections

1. **Startup**:
```
`launch_xbee.py`
    V
`base_station.main()`
    V
Makes a `BaseStation` instance
```
3. **Controller Input**:
```
Pygame events
    V
`BaseStation._process_controller_events()`
    V
`ControllerManager`
    V
`InputProcessor`
    V
Update controller state
```
4. **Msg Transmission**: 
```
Controller state
    V
`CommunicationManager.send_controller_data()`
    V
`MessageFormatter.create_xbox_message()` or `create_n64_message()`
    V
`MessageEncoder.encode_data()` (in encoding.py)
    V
Hardware (`XbeeCommunicationManager` or `UdpCommunicationManager`)
```
5. **Show Updates**:
```
`BaseStation._update_display_data()`
    V
`TkinterDisplay.update_*()` methods
    V
GUI Thingamajigs, Doohickies, Thingamabobs, Doodads, and Whatchamacallits
```
6. **Heartbeat**:
```
`HeartbeatManager.update()`
    V
`CommunicationManager.send_heartbeat()`
    V
Hardware
```
## Message Protocol

### Format

Compact bit-packed messages for bandwidth efficiency:

| Byte | Content |
|------|---------|
| 0 | Message ID |
| 1-N | Payload |

### Message IDs

| ID | Purpose |
|----|---------|
| `0xF0` | Xbox controller data |
| `0xDF` | N64 controller data |
| `0xAA` | Heartbeat |
| `0xFE` | Quit command |
| `0xB0` | Status update |
| `0xC0` | GPS position |
| `0xD0` | Sensor reading |
| `0xE0` | Error code |

### Xbox Controller Message

```
[0xF0][LY][RY][BTN1][BTN2]
```
- LY/RY: Joystick Y-axis (0-200, 100=neutral)
- BTN1/BTN2: Button states (2 bits each)

## Sending Messages

### Built-in Helpers

```python
from xbee.core.communication import CommunicationManager

comm = CommunicationManager(xbee_device, remote_xbee)

comm.send_heartbeat()
comm.send_status_update(status_code=0, battery_level=85, signal_strength=90)
comm.send_gps_position(latitude=40.7128, longitude=-74.0060)
comm.send_sensor_reading(sensor_id=5, value=1234)
```

### Custom Messages

1. Add ID to `command_codes.py`:
```python
COMPACT_MESSAGES.CAMERA = 0xCA
```

2. Send:
```python
comm.send_compact_message([CONSTANTS.COMPACT_MESSAGES.CAMERA, 0x01])
```

## Data Packing

### 16-bit Integer

```python
# Pack
high_byte = (value >> 8) & 0xFF
low_byte = value & 0xFF

# Unpack
value = (high_byte << 8) | low_byte
```

### Float (4 bytes)

```python
import struct
packed = struct.pack('>f', 23.5)
unpacked = struct.unpack('>f', data)[0]
```

### Boolean Flags

```python
# Pack 8 bools into 1 byte
flags = (motor_on << 0) | (camera_on << 1) | (arm_on << 2)

# Unpack
motor_on = (flags >> 0) & 1
```

## Development

### Tools

```bash
pip install -r requirements-dev.txt

black .          # Format
isort .          # Sort imports
ruff check .     # Lint
mypy .           # Type check
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `XBEE_NO_GUI` | Run headless | `0` |
| `XBEE_DEFAULT_CREEP` | Enable creep on startup | `1` |
| `XBEE_PORT` | XBee serial port | From config |
| `XBEE_BAUD` | XBee baud rate | From config |
