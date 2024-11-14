import math

from digi.xbee.devices import XBeeDevice
from CommandCodes import CONSTANTS


class Xbee():
    def __init__(self):
        # the number of iterations without signal
        self.__num_no_signal = 0

        # flag to determine if the xbee should be disabled based
        # on no signal
        self.__is_disabled = False

        # flag to be triggered once the xbee has received any data
        self.__is_first_connected = False

        # all the current values from the xbee
        self.__button_values = [False] * CONSTANTS.NUM_BUTTONS
        self.__axis_values = [0.0] * CONSTANTS.NUM_AXES

    """
    get the current value of selected input

    :param input_type - Specifies what type of input
    :param input_trigger - Controller button or axis, value from CommandCodes
    """

    def get_current_value(self, input_type: int, input_trigger: int) -> int | bool:
        match input_type:
            case CONSTANTS.INPUT_TYPE.IS_AXIS:
                pass
            case CONSTANTS.INPUT_TYPE.IS_AXIS:
                pass
            case CONSTANTS.INPUT_TYPE.IS_BUTTON:
                pass

        return False

    # print all the current values to terminal
    def print_values(self) -> None:

        print("Left Axis: ")
        print(self.get_current_value(CONSTANTS.INPUT_TYPE.IS_AXIS , CONSTANTS.JOYSTICK.AXIS_LY))

        print(" Right Axis: ")
        print(self.get_current_value(CONSTANTS.INPUT_TYPE.IS_AXIS, CONSTANTS.JOYSTICK.AXIS_RY))

        print(" A Button: ")
        print(self.get_current_value(CONSTANTS.INPUT_TYPE.IS_BUTTON, CONSTANTS.BUTTONS.A))

        print(" B Button: ")
        print(self.get_current_value(CONSTANTS.INPUT_TYPE.IS_BUTTON, CONSTANTS.BUTTONS.B))

        print(" X Button: ")
        print(self.get_current_value(CONSTANTS.INPUT_TYPE.IS_BUTTON, CONSTANTS.BUTTONS.X))

        print(" Y Button: ")
        print(self.get_current_value(CONSTANTS.INPUT_TYPE.IS_BUTTON, CONSTANTS.BUTTONS.Y))

        print(" LB Button: ")
        print(self.get_current_value(CONSTANTS.INPUT_TYPE.IS_BUTTON, CONSTANTS.BUTTONS.LEFT_BUMPER))

        print(" RB Button: ")
        print(self.get_current_value(CONSTANTS.INPUT_TYPE.IS_BUTTON, CONSTANTS.BUTTONS.RIGHT_BUMPER))

        print(" LT Button: ")
        print(self.get_current_value(CONSTANTS.INPUT_TYPE.IS_TRIGGER, CONSTANTS.TRIGGER.AXIS_LT))

        print(" RT Button: ")
        print(self.get_current_value(CONSTANTS.INPUT_TYPE.IS_TRIGGER, CONSTANTS.TRIGGER.AXIS_RT))

    # checks if the xbee is disabled
    def is_disabled(self) -> bool:
        return self.__is_disabled

    # clears the disable flag to allow the xbee to continue normal function
    def clear_disable(self) -> None:
        self.__is_disabled = False

    # disable the xbee
    def disable_xbee(self) -> None:
        self.__is_disabled = True

    """
    helper function that is called when message is received, to parse to get values
    
    :param message - a full message that start with start message
    """
    #
    def __parse_incoming_message(self, message: list[int]):
        # the current byte number
        byte_num:int = 0

        # parse for axis
        for i in range(0, CONSTANTS.NUM_AXES, 1):
            if(CONSTANTS.JOYSTICK.MAX_VALUE >= message[byte_num] >= CONSTANTS.JOYSTICK.MIN_VALUE):
                self.__axis_values[i] = (message[byte_num] - 100.0)/(100.0)
                byte_num = byte_num + 1

        # parse for button values
        for i in range(0 , CONSTANTS.NUM_BUTTONS, 1):
            # check if section of byte is on or off
            self.__button_values[i] = (message[byte_num] >> ((i % CONSTANTS.BUTTONS.NUM_BUTTONS_PER_BYTE)*CONSTANTS.BUTTONS.SIZE_BUTTON_IN_BITS) & CONSTANTS.BUTTONS.ON) == CONSTANTS.BUTTONS.ON
            if(i != 0 and i % 4 == 0):
                byte_num = byte_num + 1

    def send_msg(self):
        pass

    def on_message_received(self):
        pass


    def main(self):
        xbee = Xbee()


if __name__ == '__main__':
    main()
