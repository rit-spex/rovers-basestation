# Developer Guide — Rovers Base Station

> Practical guide for new contributors. If you're trying to figure out how things work or how to add a feature, start here.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Package Map](#package-map)
3. [Data Flow](#data-flow)
4. [Shared Protocol (rovers-protocol)](#shared-protocol-rovers-protocol)
5. [How to Add a New Button](#how-to-add-a-new-button)
6. [How to Add a New Message Type](#how-to-add-a-new-message-type)
7. [How to Add a Display Element](#how-to-add-a-display-element)
8. [Key Classes & Where to Find Them](#key-classes--where-to-find-them)
9. [Wire Protocol Reference](#wire-protocol-reference)
10. [Running & Testing](#running--testing)
11. [Common Pitfalls](#common-pitfalls)

---

## System Overview

The **basestation** runs on a Raspberry Pi with a small monitor and game controllers attached. It reads controller input, packs the data into compact byte messages, and sends them over **XBee radio** to the rover. The rover runs **ROS 2** and decodes those same messages. The rover also sends **telemetry** back to the basestation over **UDP**, which the GUI displays.

```
                        - XBee Radio -
  ┌────────────────┐                      ┌───────────────┐
  |                |   ───────────────>   |               |
  │ BASESTATION    │   controller data    │ ROVER (ROS 2) │
  │ (Raspberry Pi) │  <───────────────    │ (Jetson Orin) │
  │                │   telemetry (UDP)    │               │
  └────────────────┘                      └───────────────┘
       │                                      │
       │  reads controllers                   │  decodes msgs → ROS topics
       │  encodes + sends                     │  publishes telemetry back
       │  displays telemetry GUI              │
       │                                      │
       └──── lib/rovers-protocol ─────────────┘
              (shared git submodule)
```

Both repos share the same protocol library (`rovers-protocol`) as a **git submodule** at `lib/rovers-protocol`. This means:

- Message IDs, signal definitions, and encoding/decoding logic are defined **once** in `protocol.yaml`
- You clone with `--recurse-submodules` to get the protocol
- Updating the protocol in one place updates it everywhere

**The basestation code does three things:**
1. Reads game controller input (Xbox, N64)
2. Encodes and sends it to the rover via XBee/UDP
3. Displays telemetry received from the rover in a tkinter GUI

---

## Package Map

```
xbee/
├── app.py                    # BaseStation class + main() entry point
├── __main__.py               # `python -m xbee` entry point
│
├── config/                   # Configuration loaded from protocol.yaml
│   └── constants.py          # CONSTANTS namespace — all IDs, mappings, tuning
│
├── controller/               # Everything about reading gamepads
│   ├── events.py             # InputEvent dataclass + event type constants
│   ├── detection.py          # detect_controller_type(name) — Xbox vs N64
│   ├── state.py              # ControllerState — current button/axis values
│   ├── manager.py            # ControllerManager (hotplug) + InputProcessor
│   └── input_source.py       # InputEventSource — reads OS gamepad events
│
├── protocol/                 # Re-exports from rover_protocol submodule
│   └── encoding.py           # Adds lib/rovers-protocol to sys.path,
│                              # re-exports MessageEncoder + Signal
│
├── communication/            # Sending and receiving data
│   ├── manager.py            # CommunicationManager + MessageFormatter
│   ├── xbee_backend.py       # XbeeCommunicationManager — real XBee radio
│   ├── udp_backend.py        # UdpCommunicationManager — UDP simulation + telemetry
│   └── heartbeat.py          # HeartbeatManager — periodic keep-alive
│
├── display/                  # GUI and headless display
│   ├── base.py               # BaseDisplay ABC, HeadlessDisplay, create_display()
│   ├── gui.py                # TkinterDisplay — full tkinter GUI
│   └── telemetry.py          # Telemetry interpretation helpers
│
lib/
└── rovers-protocol/          # Shared protocol submodule (git submodule)
    ├── protocol.yaml         # THE "source of truth" for all messages
    ├── rover_protocol/
    │   ├── codec.py          # MessageEncoder + Signal (encode/decode)
    │   ├── constants.py      # CONSTANTS namespace built from protocol.yaml
    │   └── schema.py         # YAML loader
    └── tests/
        └── test_codec.py     # Protocol unit tests
```

---

## How Data Flows

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

---

## Shared Protocol (rovers-protocol)

The protocol is a **separate git repo** included as a submodule at `lib/rovers-protocol/`. All message definitions live in `protocol.yaml`.

### Why a submodule?

Both the basestation (this repo) and the rover ROS code need identical encoding/decoding logic. Instead of maintaining two copies, both repos point to the same protocol repo. When you update `protocol.yaml` or `codec.py`:

1. Commit and push in `rovers-protocol`
2. Update the submodule reference in both `rovers-basestation` and `rovers-ros`
   └── Literally just have to cd into it and do a `git pull origin main`
3. Both sides now speak the same language (hence the name protocol)

### How imports work

Since the submodule isn't pip-installed, the wrapper modules add it to `sys.path`:

- **Basestation:** `xbee/protocol/encoding.py` adds `lib/rovers-protocol/` to `sys.path`, then does `from rover_protocol import MessageEncoder, Signal`
- **ROS:** `encoding.py` and `command_codes.py` in the basestation ROS package do the same thing pretty much

This means you always import through the local wrapper:
```python
# In basestation code:
from xbee.protocol.encoding import MessageEncoder

# In ROS code:
from encoding import MessageEncoder # (which extends MessageEncoder)
from command_codes import CONSTANTS
```

### Cloning with the submodule

```bash
git clone --recurse-submodules https://github.com/rit-spex/rovers-basestation.git
```

Or if you already cloned:
```bash
git submodule update --init --recursive
```

---

## How to Add a New Button For Dummies

### Step 1: Add the signal to protocol.yaml

**File: `lib/rovers-protocol/protocol.yaml`**
                                                                     vvvvvvv
Find the controller message (like `xbox`) and add your signal at the **end** of the signals list:
                                                                     ^^^^^^^
```yaml
messages:
  xbox:
    id: 0x02
    direction: to_rover
    signals:
      # ... existing signals ...
      MY_BUTTON:
        type: UINT_2_BOOL
        default: false
```

### Step 2: Add the constant mapping

**File: `lib/rovers-protocol/rover_protocol/constants.py`**

In the appropriate button class (like `_XboxButton`), add your button index and string alias:

```python
class _XboxButton:
    # ... existing buttons ...
    MY_BUTTON = 11;    MY_BUTTON_STR = "MY_BUTTON"
```

### Step 3: Map the OS event code

**File: `xbee/controller/input_source.py`**

Update the button mapping for your controller:

```python
xbox_map = {
    "BTN_SOUTH": CONSTANTS.XBOX.BUTTON.A,
    # ... existing mappings ...
    "BTN_MY_BUTTON": CONSTANTS.XBOX.BUTTON.MY_BUTTON,
}
```

### Step 4: Done

The `MessageEncoder` reads signal definitions from `protocol.yaml` at init time. The new button is automatically included in encoding/decoding. No other files need changes unless you want special stuff. Speaking of special stuff:

### Optional: Show the button in the GUI

**File: `xbee/display/gui.py`** — add display logic in `_insert_controller_values()`.

---

## How to Add a New Message Type

### Step 1: Define the message in protocol.yaml

**File: `lib/rovers-protocol/protocol.yaml`**

```yaml
messages:
  my_sensor:
    id: 0xA0 # Pick an unused byte, first digit 0 for to_rover, F for from_rover
    direction: from_rover  # or to_rover
    signals:
      temperature:
        type: UINT_16
        default: 0
      active:
        type: BOOLEAN
        default: false
```

### Step 2: Add the message ID constant

**File: `lib/rovers-protocol/rover_protocol/constants.py`**

In the `CONSTANTS.COMPACT_MESSAGES` namespace, add the ID:

```python
COMPACT_MESSAGES = _ns(
    # ... existing IDs ...
    MY_SENSOR_ID=_MESSAGE_IDS["my_sensor"],
)
```

### Step 3: Add a send method (if to_rover)

**File: `xbee/communication/manager.py`**

```python
# just as an example
def send_my_sensor(self, data: dict) -> bool:
    encoded = self.formatter.encoder.encode_data(
        data, CONSTANTS.COMPACT_MESSAGES.MY_SENSOR_ID
    )
    return self.hardware_com.send_package(encoded)
```

### Step 4: Handle on the receiving side

If `direction: from_rover`, the basestation's `UdpCommunicationManager._try_handle_protocol_message()` will automatically decode it and pass it to the telemetry handler. The GUI will show it if you add display logic.

If `direction: to_rover`, the ROS-side `basestation_node.py` will automatically create publishers for the new signals (it reads the message definitions from the encoder at startup).

---

## How to Add a Display Element

### Adding to the tkinter GUI

**File: `xbee/display/gui.py`**

1. In `__init__()`, create your widget in the appropriate frame
2. Store it as `self.my_widget`
3. Add an update method and call it from the control loop

### Using the headless display (for tests/CLI)

**File: `xbee/display/base.py`**

1. Add a method to `BaseDisplay` (the abstract base class)
2. Implement it in `HeadlessDisplay` (just log)
3. Implement it in `TkinterDisplay` (in gui.py)

---

## Wire Protocol Reference

Messages are byte arrays. First byte = message ID, then bit-packed signal data.

### Signal Types (defined in protocol.yaml)

| Type | Bits | Range | Python → Wire | Wire → Python |
|------|------|-------|---------------|---------------|
| `UINT_8_JOYSTICK` | 8 | 0–200 (neutral=100) | float → `int(val*100+100)` | int → `(val-100)/100.0` |
| `UINT_2_BOOL` | 2 | 1=OFF, 2=ON | bool → `bool+1` | `val == 2` → bool |
| `BOOLEAN` | 1 | 0–1 | bool → int | int → bool |
| `UINT_8` | 8 | 0–255 | int passthrough | int passthrough |
| `UINT_16` | 16 | 0–65535 | int passthrough | int passthrough |

### Bit Packing

Signals are packed left-to-right starting from the MSB of byte 1 (byte 0 is the message ID). When a signal doesn't fit in the remaining bits of the current byte, it wraps to the next byte.

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

---

## Running & Testing

```bash
# Run the base station
python -m xbee

# Run without GUI (headless / service mode)
XBEE_NO_GUI=1 python -m xbee

# Run all tests
python -m pytest tests/

# Run a specific test file
python -m pytest tests/unit/encoding/test_encoding.py -v

# Run tests matching a name pattern
python -m pytest tests/ -k "test_encode"

# Basestation-side protocol data (auto-enabled in simulation mode)
# To manually enable in XBee mode:
export ROVER_PROTOCOL_TRACE=1 && python -m xbee
```

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------||
| `XBEE_NO_GUI` | `""` | Set to `"1"` to disable tkinter GUI |
| `XBEE_DEFAULT_CREEP` | `1` | Set to `"0"` to disable default creep mode |
| `BASESTATION_LOG_EVERY_UPDATES` | `0` | Log every N control loop iterations (0 = debug only) |
| `XBEE_INFLIGHT_WAIT_TIMEOUT` | `30.0` | Timeout (seconds) for XBee inflight message ack |
| `XBEE_TEST_ENABLE_INPUTS` | `0` | Allow controller inputs under pytest |
| `XBEE_JOYSTICK_RAW_MODE` | `""` | Force joystick raw mode (`signed` or `unsigned`) when auto-detection is not reliable |
| `ROVER_PROTOCOL_TRACE` | `"1"` (sim) / `"0"` (XBee) | Log decoded protocol packets (`[protocol tx]` / `[protocol rx]`). Automatically enabled in simulation mode. On the ROS side (`basestation_node` / `telemetry_uplink_node`) it also defaults to `"1"`. Set to `"0"` to silence. |

---

## Common Mistakes only dumb people (not me ong) make

1. **Signal order in protocol.yaml matters.** The bit-packed wire format depends on the order of signals. So add new signal at the end.

2. **`_STR` suffix constants.** When you see `A_STR = "A"`, that `"A"` is the key used in data dictionaries and the wire protocol. Don't change it unless you update the rover side too otherwise everything will explode.

3. **`@patch` paths.** Must point to where the name is USED, not where it's defined. For example, if `app.py` does `from xbee.communication.manager import CommunicationManager`, then your test must do `@patch("xbee.app.CommunicationManager")`.

4. **Submodule must be initialized.** If `lib/rovers-protocol/` is empty, run `git submodule update --init --recursive`. Tests will fail without it.

5. **Simulation mode.** When XBee hardware isn't available, the system automatically falls back to UDP simulation. This is transparent to the rest of the code. Force it with `CONSTANTS.SIMULATION_MODE = True` in `xbee/config/constants.py`. Protocol tracing is **automatically enabled** in simulation mode so you can see every packet going in and out — that's the whole point of simulation.

6. **Protocol changes require updating the submodule in both repos.** After pushing a change to `rovers-protocol`, update the submodule reference in both `rovers-basestation` and `rovers-ros` with:
   ```bash
   cd lib/rovers-protocol && git pull origin main && cd ../..
   git add lib/rovers-protocol
   git commit -m "Update protocol submodule"
   ```
**Note:** #6 might actually get changed by me in the future to be more automated once I figure out how to update parents that depend on the submodule on a protocol defining commit of the submodule, but for now it's manual.

---

## Future Refactoring Notes

- **`xbee/` package rename:** Rename it to `basestation/`, the reason I am not doing this yet is cause it would touch 62 files, and hundreds of `@patch()` string references. It should probably be done in a proper separate PR.