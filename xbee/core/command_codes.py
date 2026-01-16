"""
Module containing command codes and constants used across the project.
"""

from dataclasses import dataclass
from types import SimpleNamespace

# Shared input type constant for controllers; used by XBOX and N64.
INPUT_TYPE = SimpleNamespace(IS_BUTTON=0, IS_AXIS=1, IS_TRIGGER=2)


@dataclass(frozen=True)
class DataType:
    """Representation of a compact message data type.

    DataType objects are used by the encoder/decoder to describe the number
    of bits occupied by a signal and a small numeric ID used in message
    definitions.
    """

    num_bits: int
    id: int


class CONSTANTS:
    # Set to True to run simulator with UDP, False for actual XBee communication
    SIMULATION_MODE = (
        False  # Change this to False when trying to communicate with real rover
    )

    # message to send to show start of new values
    START_MESSAGE = b"\xde"
    QUIT_MESSAGE = b"\xfe"

    # Compact message order: axis bytes, triggers (2 bits), then buttons (2 bits).

    class CONVERSION:
        NS_PER_MS = 1_000_000
        NS_PER_S = 1_000_000_000

        ONE_HUNDRED_MS_TO_NS = 100_000_000
        FIVE_HUNDRED_MS_TO_NS = 500_000_000

    class HEARTBEAT:
        NAME = "heartbeat"

        MESSAGE = b"\xaa"  # Heartbeat signal identifier
        MESSAGE_LENGTH = 3  # Length of heartbeat message in bytes

        TIMESTAMP_MESSAGE = "timestamp"

        INTERVAL = 500_000_000  # 500ms heartbeat interval
        # Heartbeat consists of 1 byte identifier + 2 bytes timestamp

    # COMPACT_MESSAGES is a SimpleNamespace to keep the API stable and accessible via CONSTANTS.COMPACT_MESSAGES.<ATTR>, while avoiding class-name lint warnings.
    COMPACT_MESSAGES = SimpleNamespace()
    # Reserved message IDs (DO NOT USE)
    COMPACT_MESSAGES.CONTROLLER_DATA = 0xDE  # START_MESSAGE
    COMPACT_MESSAGES.N64_ID = 0xDF  # The Id for the N64
    COMPACT_MESSAGES.XBOX_ID = 0xF0  # The Id for the Xbox
    COMPACT_MESSAGES.QUIT_ID = 0xFE  # QUIT_MESSAGE
    COMPACT_MESSAGES.HEARTBEAT_ID = 0xAA  # Heartbeat
    COMPACT_MESSAGES.DATA_TYPE = DataType
    # enum of data types in bits
    COMPACT_MESSAGES.UINT_2_BOOL = DataType(2, 0x01)
    COMPACT_MESSAGES.UINT_8 = DataType(8, 0x02)
    COMPACT_MESSAGES.UINT_16 = DataType(16, 0x03)
    COMPACT_MESSAGES.UINT_8_JOYSTICK = DataType(8, 0x04)  # convert to float on decoding
    COMPACT_MESSAGES.BOOLEAN = DataType(1, 0x05)

    # Available message IDs for custom messages
    COMPACT_MESSAGES.STATUS = 0xB0  # System status update
    COMPACT_MESSAGES.ERROR = 0xE0  # Error codes
    COMPACT_MESSAGES.GPS = 0xC0  # GPS position data
    COMPACT_MESSAGES.SENSOR = 0xD0  # Sensor readings

    class TIMING:
        # Timing constants for various operations (in nanoseconds)
        UPDATE_FREQUENCY = 40_000_000  # 40ms update frequency
        DEADBAND_THRESHOLD = 0.10  # Controller deadband threshold

    class COMMUNICATION:
        # Communication settings
        DEFAULT_PORT = "/dev/ttyUSB0"  # "COM9"
        DEFAULT_BAUD_RATE = 230400
        REMOTE_XBEE_ADDRESS = "0013A200423A7DDD"

        # UDP settings for simulation mode
        UDP_HOST = "127.0.0.1"  # localhost
        UDP_BASESTATION_PORT = 5000  # Port for basestation to send from
        UDP_ROVER_PORT = 5005  # Port to send rover commands to
        UDP_TELEMETRY_PORT = 5002  # Port to receive telemetry data

    # Controller mode multipliers (exposed as a SimpleNamespace to avoid
    # having to define a class in all-caps for linting purposes)
    CONTROLLER_MODES = SimpleNamespace(
        NORMAL_MULTIPLIER=1.0,
        CREEP_MULTIPLIER=0.2,
        REVERSE_MULTIPLIER=-1.0,
    )

    class QUIT:
        NAME = "QUIT"
        VALUE = 1

    class XBOX:
        # Use lowercase "xbox" to keep controller names consistent with other types (e.g., "n64").
        NAME = "xbox"
        NUM_AXES = 6
        NUM_USED_AXES = 2
        NUM_TRIGGER = 2
        NUM_BUTTONS = 8  # this number is including the triggers
        # XBOX compact message layout puts axes/triggers before button indices; use BUTTON_INDEX_OFFSET instead of literals.
        BUTTON_INDEX_OFFSET = 6

        # enum for input type - use module-level shared constant
        INPUT_TYPE = INPUT_TYPE

        class JOYSTICK:
            MIN_VALUE = 0
            NEUTRAL_HEX = b"\x64"
            NEUTRAL_INT = 100
            NEUTRAL_FLOAT = 0.0
            MAX_VALUE = 200

            AXIS_LX = 0
            AXIS_LX_STR = "AXIS_LX"
            AXIS_LY = 1
            AXIS_LY_STR = "AXIS_LY"
            AXIS_RX = 3
            AXIS_RX_STR = "AXIS_RX"
            AXIS_RY = 4
            AXIS_RY_STR = "AXIS_RY"

        # these are treated like buttons for transfer msgs but are classified as axis
        class TRIGGER:
            AXIS_LT = 2
            AXIS_LT_STR = "AXIS_LT"
            AXIS_RT = 5
            AXIS_RT_STR = "AXIS_RT"

        class BUTTON:
            SIZE_BUTTON_IN_BITS = 2
            NUM_BUTTONS_PER_BYTE = 8 / SIZE_BUTTON_IN_BITS

            # Use 2 for ON (binary 10) for 2-bit button encoding.
            ON = 2
            OFF = 1

            A = 0
            A_STR = "A"
            B = 1
            B_STR = "B"
            X = 2
            X_STR = "X"
            Y = 3
            Y_STR = "Y"
            LEFT_BUMPER = 4
            LEFT_BUMPER_STR = "LEFT_BUMPER"
            RIGHT_BUMPER = 5
            RIGHT_BUMPER_STR = "RIGHT_BUMPER"
            SELECT = 6
            SELECT_STR = "SELECT"
            START = 7
            START_STR = "START"
            LEFT_STICK = 9
            LEFT_STICK_STR = "LEFT_STICK"
            RIGHT_STICK = 10
            RIGHT_STICK_STR = "RIGHT_STICK"
            HOME = 8
            HOME_STR = "HOME"

        class JOYPAD:
            UP = (0, 1)
            DOWN = (0, -1)
            LEFT = (-1, 0)
            RIGHT = (1, 0)

    class N64:
        NAME = "n64"
        NUM_AXES = 2
        NUM_USED_AXES = 0
        NUM_TRIGGER = 0
        NUM_BUTTONS = 14

        INPUT_TYPE = INPUT_TYPE

        class JOYSTICK:
            MIN_VALUE = 0
            NEUTRAL_HEX = b"\x64"
            NEUTRAL_INT = 100
            MAX_VALUE = 200

            AXIS_X = 0
            AXIS_X_STR = "AXIS_X"
            AXIS_Y = 1
            AXIS_Y_STR = "AXIS_Y"

        class BUTTON:
            SIZE_BUTTON_IN_BITS = 2
            NUM_BUTTONS_PER_BYTE = 8 / SIZE_BUTTON_IN_BITS

            ON = 2
            OFF = 1

            A = 1
            A_STR = "A"
            B = 2
            B_STR = "B"
            C_UP = 9
            C_UP_STR = "C_UP"
            C_DOWN = 0
            C_DOWN_STR = "C_DOWN"
            C_LEFT = 3
            C_LEFT_STR = "C_LEFT"
            C_RIGHT = 8
            C_RIGHT_STR = "C_RIGHT"
            L = 4
            L_STR = "L"
            R = 5
            R_STR = "R"
            Z = 6
            Z_STR = "Z"
            START = 12
            START_STR = "START"
            DP_UP = 20
            DP_UP_STR = "DP_UP"
            DP_DOWN = 21
            DP_DOWN_STR = "DP_DOWN"
            DP_LEFT = 22
            DP_LEFT_STR = "DP_LEFT"
            DP_RIGHT = 23
            DP_RIGHT_STR = "DP_RIGHT"

        class JOYPAD:
            UP = (0, 1)
            DOWN = (0, -1)
            LEFT = (-1, 0)
            RIGHT = (1, 0)
