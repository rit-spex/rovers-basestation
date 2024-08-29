class CommandCodes:
    START_MESSAGE = b'\xDE'

    class JOYSTICK:
        MIN_VALUE = 0
        NEUTRAL_HEX = b'\x64'
        NEUTRAL_INT   = 100
        MAX_VALUE = 200

        AXIS_LX = 0
        AXIS_LY = 1
        AXIS_RX = 2
        AXIS_RY = 3

    class TRIGGER:
        AXIS_LT = 4
        AXIS_RT = 5

    class BUTTONS:
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
        LEFT_STICK   = 8
        RIGHT_STICK  = 9
        HOME         = 10

    class JOYPAD:
        UP = (0, 1)
        DOWN = (0, -1)