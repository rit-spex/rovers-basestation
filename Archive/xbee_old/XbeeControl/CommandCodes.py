class CommandCodes:
    class JOYSTICK:
        class AXIS_LX:
            command = b'\xc9'
            index = 0

        class AXIS_LY:
            command = b'\xca'
            index = 1

        class AXIS_RX:
            command = b'\xcb'
            index = 2

        class AXIS_RY:
            command = b'\xcc'
            index = 3

    class TRIGGER:
        class AXIS_LT:
            command = b'\xcd'
            index = 4

        class AXIS_RT:
            command = b'\xce'
            index = 5

    class BUTTONS:
        class A:

            OnCommand = b'\xcf'
            OffCommand = b'\xd0'
            index = 0

        class B:
            OnCommand = b'\xd1'
            OffCommand = b'\xd2'
            index = 1

        class X:
            OnCommand = b'\xd3'
            OffCommand = b'\xd4'
            index = 2

        class Y:
            OnCommand = b'\xd5'
            OffCommand = b'\xd6'
            index = 3

        class LEFT_BUMPER:
            OnCommand = b'\xd7'
            OffCommand = b'\xd8'
            index = 4

        class RIGHT_BUMPER:
            OnCommand = b'\xd9'
            OffCommand = b'\xda'
            index = 5

        class SELECT:
            OnCommand = b'\xdb'
            OffCommand = b'\xdc'
            index = 6

        class START:
            OnCommand = b'\xdd'
            OffCommand = b'\xde'
            index = 7

        class LEFT_STICK:
            OnCommand = b'\xdf'
            OffCommand = b'\xe0'
            index = 8

        class RIGHT_STICK:
            OnCommand = b'\xe1'
            OffCommand = b'\xe2'
            index = 9

        class HOME:
            OnCommand = b'\xe3'
            OffCommand = b'\xe4'
            index = 10

    class JOYPAD:
        command = b'\xe5'
        index = 0