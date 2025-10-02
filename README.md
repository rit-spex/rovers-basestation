# SPEX Rover Basestation

Control system for the rover with support for both real XBee communication and UDP for simulation and debugging.

## Setup

### Virtual Environment
1. Install virtualenv: `pip install virtualenv`
2. Create environment: `virtualenv venv`
3. Activate environment: `source venv/Scripts/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
4. Install dependencies: `pip install -r requirements.txt`

**Note**: XBee libraries are optional - the system will automatically use simulation mode if they're not available. For real rover communication, install the full requirements: `pip install -r requirements.txt`

### Config
Set the communication mode in `xbee/core/CommandCodes.py`:
```python
SIMULATION_MODE = True   # For testing/simulation w/ UDP
SIMULATION_MODE = False  # For real rover communication using XBee
```

## Usage

### Running the Basestation
```bash
python launch_xbee.py
```

### Testing
Gives a nice text UI:
```bash
python run_tests.py
```
Just runs test_system_pytest.py:
```bash
python run_tests.py --pytest
```
Run easy to understand tests:
```bash
python run_tests.py --human
```
Runs test_system_pytest.py then test_system_human.py:
```bash
python run_tests.py --both
```

## Config

### UDP Ports (Simulation Mode)
```python
class COMMUNICATION:
    UDP_HOST = "127.0.0.1"
    UDP_BASESTATION_PORT = 5000  # Basestation sending
    UDP_ROVER_PORT = 5001        # Rover commands  
    UDP_TELEMETRY_PORT = 5002    # Telemetry data
```

### Adding New Message Types
1. Add new type constant to `MessageType` class in `message_system.py`
2. Create a message class inheriting from `BaseMessage`
3. Make the `encode_payload()` and `decode_payload()` methods
4. Register with `message_codec.register_message_class()` 
5. Test with included mock rover stuff in simulation mode

EX:
```python
# In MessageType class
MY_CUSTOM_DATA = 0x05

# New message class
class MyCustomMessage(BaseMessage):
    def __init__(self, custom_field=""):
        super().__init__(MessageType.MY_CUSTOM_DATA)
        self.custom_field = custom_field
        
    def encode_payload(self):
        return json.dumps({"custom_field": self.custom_field}).encode()
        
    def decode_payload(self, payload_data):
        data = json.loads(payload_data.decode())
        self.custom_field = data["custom_field"]

# Registration
message_codec.register_message_class(MessageType.MY_CUSTOM_DATA, MyCustomMessage)
```

### Controller Configs
Change consts in `CommandCodes.py`:
- Timing settings (`UPDATE_FREQUENCY`, `DEADBAND_THRESHOLD`)
- Controller mappings (`XBOX`, `N64` button/axis definitions)
- Comms settings (`DEFAULT_PORT`, `BAUD_RATE`)