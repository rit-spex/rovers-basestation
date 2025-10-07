# SPEX Rover Basestation - Cool diagram

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    XbeeControlRefactored                        │
│                    (Main Orchestrator)                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ coordinates
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐      ┌──────────────┐
│ Controller   │    │ Heartbeat    │      │  Tkinter     │
│ Manager      │    │ Manager      │      │  Display     │
└──────────────┘    └──────────────┘      └──────────────┘
        │                     │                     │
        │                     │                     │
        ▼                     ▼                     │
┌──────────────┐    ┌──────────────┐                │
│   Input      │    │   Message    │                │
│  Processor   │    │    Codec     │                │
└──────────────┘    └──────────────┘                │
        │                     │                     │
        │                     │                     │
        └─────────┬───────────┘                     │
                  │                                 │
                  ▼                                 │
        ┌──────────────────┐                        │
        │  Communication   │◄───────────────────────┘
        │    Manager       │  (receives updates)
        └──────────────────┘
                  │
                  │
        ┌─────────┴─────────┐
        │                   │
        ▼                   ▼
┌──────────────┐   ┌────────────────┐
│   Message    │   │   Simulation   │
│  Formatter   │   │   Comm Mgr     │
│  (Legacy)    │   │   (UDP)        │
└──────────────┘   └────────────────┘
        │                   │
        │                   │
        ▼                   ▼
┌──────────────┐   ┌────────────────┐
│  XBee Radio  │   │  UDP Network   │
│  Hardware    │   │  (Testing)     │
└──────────────┘   └────────────────┘

Controller:

    ┌──────────────┐
    │  User Input  │  (Physical controller)
    └──────┬───────┘
           │
           ▼
┌─────────────────────────┐
│  Pygame Events          |  (Button press, joystick move)
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  ControllerManager      │  (Captures & organizes events)
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  InputProcessor         │  (Applies modes: creep, reverse)
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  MessageFormatter       │  (Bit-packs into 10 bytes)
│  OR MessageCodec        │  (JSON encodes with header)
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  CommunicationManager   │  (XBee transmission)
│  OR SimulationCommMgr   │  (UDP transmission)
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Rover Receives Data    │  Beep boop baby
└─────────────────────────┘
```

## Old Format (MessageFormatter)
```
[START][LY][RY][BTN1][BTN2][START][N64_B1][N64_B2][N64_B3][N64_B4]
   1     1   1    1     1     1       1       1       1       1
```

## Newer Format (MessageCodec)
```
[TYPE][MSG_ID][TIMESTAMP][LENGTH][JSON_PAYLOAD]
  1      4        8         2        varies
```

### Field Breakdown

- TYPE (1 byte)
  - Msg type ID
  - EX: `0x01` = command, `0x02` = telemetry, `0x03` = heartbeat
  - Allows receiver to quickly categorize incoming messages

- MSG_ID (4 bytes)
  - Unique msg ID
  - Used for tracking and anti-duplication

- TIMESTAMP (8 bytes)
  - Unix timestamp in milliseconds
  - Lets you do time based synchronization and latency calc
  - 64-bit int

- LENGTH (2 bytes)
  - Size of JSON_PAYLOAD in bytes
  - Can be 0
  - Max payload size: 65,535 bytes
  - Lets receiver to allocate appropriate buffer

- JSON_PAYLOAD (variable length)
  - Optional, can be empty
  - command/telemetry data
  - Ex: `{"speed": 128, "direction": "forward"}`

## File Organization

```
rovers-basestation/
├── ARCHITECTURE.md          ← Full UML
├── ARCHITECTURE_DIAGRAM.md  ← Supa Dupa cool diagram
├── launch_xbee.py           ← Launch script
├── run_tests.py             ← Test runner, use `python run_tests.py --both`
└── xbee/
    ├── __init__.py
    ├── __main__.py          ← Start: `python -m xbee`
    └── core/
        ├── command_codes.py      ← Constants
        ├── xbee_refactored.py    ← Main
        ├── controller_manager.py ← Input handling
        ├── communication.py      ← XBee and MessageFormatter
        ├── udp_communication.py  ← Simulation
        ├── message_system.py     ← Codec
        ├── heartbeat.py          ← Heartbeat manager
        └── tkinter_display.py    ← GUI display w/ tkinter
```

## Quick

### Running
```bash
python launch_xbee.py
```

### Testing
```bash
python run_tests.py --both
```