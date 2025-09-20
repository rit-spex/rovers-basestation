class CONSTANTS:
    # message to send to show start of new values
    START_MESSAGE = b'\xDE'
    QUIT_MESSAGE = b'\xFE'

    # message order:
    # byte Axis
    # 2 bits Trigger
    # 2 bits Buttons

    class CONVERSION:
        NS_PER_MS = 1_000_000
        NS_PER_S = 1_000_000_000
        
        ONE_HUNDRED_MS_TO_NS = 100_000_000
        FIVE_HUNDRED_MS_TO_NS = 500_000_000
    class HEARTBEAT:
        MESSAGE = b'\xAA'  # Heartbeat signal identifier
        MESSAGE_LENGTH = 3  # Length of heartbeat message in bytes

        INTERVAL = 1_000_000_000  # 1 second heartbeat interval
        # Heartbeat consists of 1 byte identifier + 2 bytes timestamp
    
    class TIMING:
        # Timing constants for various operations (in nanoseconds)
        UPDATE_FREQUENCY = 40_000_000  # 40ms update frequency
        DEADBAND_THRESHOLD = 0.10  # Controller deadband threshold
    
    class COMMUNICATION:
        # Communication settings
        DEFAULT_PORT = "/dev/ttyUSB0"
        DEFAULT_BAUD_RATE = 230400
        FALLBACK_BAUD_RATE = 921600
        REMOTE_XBEE_ADDRESS = "0013A200423A7DDD"
    
    class CONTROLLER_MODES:
        # Controller mode multipliers
        NORMAL_MULTIPLIER = 100
        CREEP_MULTIPLIER = 20
        REVERSE_MULTIPLIER = -100  # Will be applied to normal/creep multiplier

    class XBOX:
        # number of processed buttons and axes
        NUM_AXES = 6
        NUM_USED_AXES = 2
        NUM_TRIGGER = 2
        NUM_BUTTONS = 8  # this number is including the triggers

        class INPUT_TYPE:
            # enum for input type
            IS_BUTTON = 0
            IS_AXIS = 1
            IS_TRIGGER = 2

        class JOYSTICK:
            MIN_VALUE = 0
            NEUTRAL_HEX = b'\x64'
            NEUTRAL_INT   = 100
            MAX_VALUE = 200

            AXIS_LX = 0
            AXIS_LY = 1
            AXIS_RX = 5
            AXIS_RY = 4

        # these are treated like buttons for transfer msgs but are classified as axis
        class TRIGGER:
            AXIS_LT = 2
            AXIS_RT = 3

        class BUTTONS:
            SIZE_BUTTON_IN_BITS = 2
            NUM_BUTTONS_PER_BYTE = 8 / SIZE_BUTTON_IN_BITS

            # I choose 2 to represent ON b/c it equals the bit value of 10
            # this means if it error and one of the bit was flipped then it would ignore it.
            # this would make it so 2 bit would need to be changed to produce the wrong result
            ON           = 2
            OFF          = 1

            A            = 0
            B            = 1
            X            = 2
            Y            = 3
            LEFT_BUMPER  = 4
            RIGHT_BUMPER = 5
            SELECT       = 6
            START        = 7
            LEFT_STICK   = 9
            RIGHT_STICK  = 10
            HOME         = 8

        class JOYPAD:
            UP = (0, 1)
            DOWN = (0, -1)
            LEFT = (-1, 0)
            RIGHT = (1, 0)

    class N64:
        NUM_AXES = 2
        NUM_USED_AXES = 0
        NUM_TRIGGER = 0
        NUM_BUTTONS = 14

        class INPUT_TYPE:
            IS_BUTTON = 0
            IS_AXIS = 1
            IS_TRIGGER = 2

        class JOYSTICK:
            MIN_VALUE = 0
            NEUTRAL_HEX = b'\x64'
            NEUTRAL_INT   = 100
            MAX_VALUE = 200

            AXIS_X = 0
            AXIS_Y = 1

        class BUTTONS:
            SIZE_BUTTON_IN_BITS = 2
            NUM_BUTTONS_PER_BYTE = 8 / SIZE_BUTTON_IN_BITS

            ON       = 2
            OFF      = 1

            A        = 1
            B        = 2
            C_UP     = 9
            C_DOWN   = 0
            C_LEFT   = 3
            C_RIGHT  = 8
            L        = 4
            R        = 5
            Z        = 6
            START    = 12
            DP_UP    = 20
            DP_DOWN  = 21
            DP_LEFT  = 22
            DP_RIGHT = 23

        class JOYPAD:
            UP = (0, 1)
            DOWN = (0, -1)
            LEFT = (-1, 0)
            RIGHT = (1, 0)
