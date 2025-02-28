import serial
import math
import pygame
import os
from pygame.event import Event
from pygame.joystick import Joystick
from CommandCodes import CONSTANTS
from JoystickFeedback import Display


class XbeeControl:
    def __init__(self):
        self.joysticks = {}

        self.quit = False

        self.creepMode = False
        self.reverseMode = False

        self.values = {
            "xbox": {
                # Store all the axis
                CONSTANTS.XBOX.JOYSTICK.AXIS_LX: CONSTANTS.XBOX.JOYSTICK.NEUTRAL_HEX,
                CONSTANTS.XBOX.JOYSTICK.AXIS_LY: CONSTANTS.XBOX.JOYSTICK.NEUTRAL_HEX,
                CONSTANTS.XBOX.JOYSTICK.AXIS_RX: CONSTANTS.XBOX.JOYSTICK.NEUTRAL_HEX,
                CONSTANTS.XBOX.JOYSTICK.AXIS_RY: CONSTANTS.XBOX.JOYSTICK.NEUTRAL_HEX,
                # Store all the buttons
                CONSTANTS.XBOX.TRIGGER.AXIS_LT: CONSTANTS.XBOX.BUTTONS.OFF,
                CONSTANTS.XBOX.TRIGGER.AXIS_RT: CONSTANTS.XBOX.BUTTONS.OFF,
                CONSTANTS.XBOX.BUTTONS.A + 6: CONSTANTS.XBOX.BUTTONS.OFF,
                CONSTANTS.XBOX.BUTTONS.B + 6: CONSTANTS.XBOX.BUTTONS.OFF,
                CONSTANTS.XBOX.BUTTONS.X + 6: CONSTANTS.XBOX.BUTTONS.OFF,
                CONSTANTS.XBOX.BUTTONS.Y + 6: CONSTANTS.XBOX.BUTTONS.OFF,
                CONSTANTS.XBOX.BUTTONS.LEFT_BUMPER + 6: CONSTANTS.XBOX.BUTTONS.OFF,
                CONSTANTS.XBOX.BUTTONS.RIGHT_BUMPER + 6: CONSTANTS.XBOX.BUTTONS.OFF,
                CONSTANTS.XBOX.BUTTONS.START + 6: CONSTANTS.XBOX.BUTTONS.OFF,
                CONSTANTS.XBOX.BUTTONS.SELECT + 6: CONSTANTS.XBOX.BUTTONS.OFF,
            },
            "n64": {
                # # Axies
                # CONSTANTS.N64.JOYSTICK.AXIS_X: CONSTANTS.N64.JOYSTICK.NEUTRAL_HEX,
                # CONSTANTS.N64.JOYSTICK.AXIS_Y: CONSTANTS.N64.JOYSTICK.NEUTRAL_HEX,
                # Buttons
                CONSTANTS.N64.BUTTONS.A: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.B: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.C_UP: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.C_DOWN: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.C_LEFT: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.C_RIGHT: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.L: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.R: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.Z: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.DP_UP: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.DP_DOWN: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.DP_LEFT: CONSTANTS.N64.BUTTONS.OFF,
                CONSTANTS.N64.BUTTONS.DP_RIGHT: CONSTANTS.N64.BUTTONS.OFF,
            }
        }

        self.instance_id_values_map = {}

        self.XBEE_ENABLE = True
        if self.XBEE_ENABLE:
            self.PORT = "/dev/ttyUSB0"  # change based on current xbee coms
            self.BAUD_RATE = 230400  # 921600  # change based on xbee baud_rate
            self.xbee_device = XBeeDevice(self.PORT, self.BAUD_RATE)
            self.xbee_device.open()
            self.remote_xbee = RemoteXBeeDevice(
                self.xbee_device, XBee64BitAddress.from_hex_string("0013A20041B1D309")
            )

        self.DEADBAND = 0.10  # this is the dead band on the controller
        self.XbeeCom = serial.Serial(self.PORT, self.BAUD_RATE)  # create the actual serial

        self.__last_message = bytearray()

    def SendCommand(self, newEvent: Event):
        """
        Update the values stored when an event is received from controller
        newEvent: the new event from the controller

        """

        if len(self.joysticks.keys()) == 0 and newEvent.type != pygame.JOYDEVICEADDED:
            return

        # the different event types:
        # JOYAXISMOTION, JOYBALLMOTION, JOYBUTTONDOWN,
        # JOYBUTTONUP, JOYHATMOTION, JOYDEVICEADDED, JOYDEVICEREMOVED
        match (newEvent.type):
            # hot swappable
            case pygame.JOYDEVICEADDED | pygame.JOYDEVICEREMOVED:
                self.HotPluggin(newEvent)
                display.Controller_Display(newEvent)

            # axis
            case pygame.JOYAXISMOTION:
                # Joystick Axis
                if newEvent.dict["axis"] in [
                    CONSTANTS.XBOX.JOYSTICK.AXIS_LX,
                    CONSTANTS.XBOX.JOYSTICK.AXIS_LY,
                    CONSTANTS.XBOX.JOYSTICK.AXIS_RX,
                    CONSTANTS.XBOX.JOYSTICK.AXIS_RY,
                ]:
                    self.SendJoystickAxis(newEvent)
                # Trigger Axis
                else:
                    if(newEvent.dict['value'] > 0):
                        self.values[newEvent.dict['axis']] = 2
                    else:
                        self.values[newEvent.dict['axis']] = 1
                display.Controller_Display(newEvent)

            # button
            case pygame.JOYBUTTONDOWN | pygame.JOYBUTTONUP:
                self.SendButton(newEvent)
                pass

            case pygame.JOYHATMOTION:
                self.SendJoyPad(newEvent)
                display.Update_Display2(creep=self.creepMode, reverse=self.reverseMode)
        display.Controller_Display(newEvent)

    def HotPluggin(self, newEvent: Event):
        """
        Handle events when the controller is plugin or unpluged
        Plugin: Add device to controller array
        Unpluged: Removed the device and kill the code
        """

        # A new device is added
        if newEvent.type == pygame.JOYDEVICEADDED:
            # This event will be generated when the program starts for every
            # joystick, filling up the list without needing to create them manually.
            joy = pygame.joystick.Joystick(newEvent.device_index)
            self.joysticks[joy.get_instance_id()] = joy
            if "xbox" in joy.get_name().lower():
                self.instance_id_values_map[joy.get_instance_id()] = "xbox"
            elif "switch" in joy.get_name().lower():
                self.instance_id_values_map[joy.get_instance_id()] = "n64"
            print(f"Joystick {joy.get_instance_id()} connencted")

        if newEvent.type == pygame.JOYDEVICEREMOVED:
            self.quit = True
            del self.joysticks[newEvent.instance_id]
            print(f"Joystick {newEvent.instance_id} disconnected")

    def SendJoystickAxis(self, newEvent: Event):
        """
        Handle events when an joystick axis is pushed
        """

        values_name = self.instance_id_values_map[newEvent.dict["instance_id"]]
        working_const = CONSTANTS.N64 if values_name == "n64" else CONSTANTS.XBOX

        if values_name == "n64":
            return

        # multiplier out of 100 to scale the output
        multiplier = 100
        if self.creepMode:
            # half the speed of the controller
            multiplier = 20
        if self.reverseMode:
            # flip the direction of axis of the controller
            multiplier = -multiplier

        if self.instance_id_values_map[newEvent.dict["instance_id"]] == "n64":
            multiplier = 100

        # check for deadband. If inside then zero values
        if abs(newEvent.dict["value"]) < self.DEADBAND:
            newEvent.dict["value"] = 0

        # convert the controller to int with multiplier
        newValue = math.floor(
            multiplier * newEvent.dict["value"] + working_const.JOYSTICK.NEUTRAL_INT
        )

        # check if value is between min and max
        if newValue < working_const.JOYSTICK.MIN_VALUE:
            newValue = working_const.JOYSTICK.MIN_VALUE
        elif newValue > working_const.JOYSTICK.MAX_VALUE:
            newValue = working_const.JOYSTICK.MAX_VALUE
        self.values[values_name][newEvent.dict["axis"]] = newValue.to_bytes(
            1
        )  # store the value as one byte

    def SendTriggerAxis(self, newEvent: Event):
        """
        Handle events when an joystick axis is pushed
        """

        if self.instance_id_values_map[newEvent.dict["instance_id"]] == "n64":
            return

        # Treat joystick like a button.
        # If it is over zero then on, otherwise off
        if newEvent.dict["value"] > 0:
            self.values["xbox"][newEvent.dict["axis"]] = CONSTANTS.XBOX.BUTTONS.ON
        else:
            self.values["xbox"][newEvent.dict["axis"]] = CONSTANTS.XBOX.BUTTONS.OFF

    def SendButton(self, newEvent: Event):
        """
        Handle button event
        """

        values_name = self.instance_id_values_map[newEvent.dict["instance_id"]]
        working_const = CONSTANTS.N64 if values_name == "n64" else CONSTANTS.XBOX

        newValue = self.joysticks[newEvent.dict["joy"]].get_button(
            newEvent.dict["button"]
        )

        # if button is home kill the code; ignore if n64
        if values_name == "xbox" and newEvent.dict["button"] == CONSTANTS.XBOX.BUTTONS.HOME or values_name == "n64" and newEvent.dict["button"] == CONSTANTS.N64.BUTTONS.START:
            self.quit = True

        self.values[values_name][newEvent.dict["button"] + (6 if values_name == "xbox" else 0)] = newValue + 1

    def SendJoyPad(self, newEvent: Event):
        """
        Handle JoyPad events
        """

        values_name = self.instance_id_values_map[newEvent.dict["instance_id"]]
        working_const = CONSTANTS.N64 if values_name == "n64" else CONSTANTS.XBOX

        if values_name == "n64":
            x = newEvent.dict["value"][0]
            y = newEvent.dict["value"][1]

            match x:
                case 0:
                    self.values[values_name][working_const.BUTTONS.DP_LEFT] = working_const.BUTTONS.OFF
                    self.values[values_name][working_const.BUTTONS.DP_RIGHT] = working_const.BUTTONS.OFF
                case -1:
                    self.values[values_name][working_const.BUTTONS.DP_LEFT] = working_const.BUTTONS.ON
                    self.values[values_name][working_const.BUTTONS.DP_RIGHT] = working_const.BUTTONS.OFF
                case 1:
                    self.values[values_name][working_const.BUTTONS.DP_LEFT] = working_const.BUTTONS.OFF
                    self.values[values_name][working_const.BUTTONS.DP_RIGHT] = working_const.BUTTONS.ON
            match y:
                case 0:
                    self.values[values_name][working_const.BUTTONS.DP_DOWN] = working_const.BUTTONS.OFF
                    self.values[values_name][working_const.BUTTONS.DP_UP] = working_const.BUTTONS.OFF
                case -1:
                    self.values[values_name][working_const.BUTTONS.DP_DOWN] = working_const.BUTTONS.ON
                    self.values[values_name][working_const.BUTTONS.DP_UP] = working_const.BUTTONS.OFF
                case 1:
                    self.values[values_name][working_const.BUTTONS.DP_DOWN] = working_const.BUTTONS.OFF
                    self.values[values_name][working_const.BUTTONS.DP_UP] = working_const.BUTTONS.ON
            return

        # if joypad is down disable modes
        if newEvent.dict["value"] == CONSTANTS.XBOX.JOYPAD.DOWN:
            if (
                self.values['xbox'][CONSTANTS.XBOX.BUTTONS.SELECT + 6] == CONSTANTS.XBOX.BUTTONS.ON
            ):  # left button is on
                self.reverseMode = False
                print("reverse off")
            if (
                self.values['xbox'][CONSTANTS.XBOX.BUTTONS.START + 6] == CONSTANTS.XBOX.BUTTONS.ON
            ):  # right button is on
                self.creepMode = False
                result= "creep mode off"

        # if joypad is up enable modes
        elif newEvent.dict["value"] == CONSTANTS.XBOX.JOYPAD.UP:
            if (
                self.values['xbox'][CONSTANTS.XBOX.BUTTONS.SELECT + 6] == CONSTANTS.XBOX.BUTTONS.ON
            ):  # left button is on
                self.reverseMode = True
                result= "reverse on"

            if (
                self.values['xbox'][CONSTANTS.XBOX.BUTTONS.START + 6] == CONSTANTS.XBOX.BUTTONS.ON
            ):  # right button is on
                self.creepMode = True
                print("creep mode on")

    def UpdateInfo(self):
        """
        Send the current values to the controller
        """

        self.updateLoop += 1

        # if the xbee is enabled
        if self.XBEE_ENABLE:

            data = [int.from_bytes(CONSTANTS.START_MESSAGE)]

            if not self.reverseMode:
                # send the regular mode so Left joy stick is left and right joy stick is right
                data.append(int.from_bytes(self.values["xbox"].get(CONSTANTS.XBOX.JOYSTICK.AXIS_LY)))
                # self.XbeeCom.write(self.values.get(CONSTANTS.XBOX.JOYSTICK.AXIS_LY))
                data.append(int.from_bytes(self.values["xbox"].get(CONSTANTS.XBOX.JOYSTICK.AXIS_RY)))
                # self.XbeeCom.write(self.values.get(CONSTANTS.XBOX.JOYSTICK.AXIS_RY))
            else:
                # invert the controller so left joy stick is right and right joy stick is left
                data.append(int.from_bytes(self.values["xbox"].get(CONSTANTS.XBOX.JOYSTICK.AXIS_RY)))
                # self.XbeeCom.write(self.values.get(CONSTANTS.XBOX.JOYSTICK.AXIS_RY))
                data.append(int.from_bytes(self.values["xbox"].get(CONSTANTS.XBOX.JOYSTICK.AXIS_LY)))
                # self.XbeeCom.write(self.values.get(CONSTANTS.XBOX.JOYSTICK.AXIS_LY))

            result = 0
            # the first two bits
            result += 1 * self.values["xbox"].get(CONSTANTS.XBOX.BUTTONS.A + 6)
            # the 3rd and 4th bits
            result += 4 * self.values["xbox"].get(CONSTANTS.XBOX.BUTTONS.B + 6)
            # the 5th and 6th bits
            result += 16 * self.values["xbox"].get(CONSTANTS.XBOX.BUTTONS.X + 6)
            # the 7th and 8th bits
            result += 64 * self.values["xbox"].get(CONSTANTS.XBOX.BUTTONS.Y + 6)

            data.append(result)
            result = 0
            # the first two bits
            result += 1 * self.values["xbox"].get(CONSTANTS.XBOX.BUTTONS.LEFT_BUMPER + 6)
            # the 3 and 4th bits
            result += 4 * self.values["xbox"].get(CONSTANTS.XBOX.BUTTONS.RIGHT_BUMPER + 6)
            # the 5 and 6th bits
            result += 16 * self.values["xbox"].get(CONSTANTS.XBOX.TRIGGER.AXIS_LT)
            # the 7 and 8th bits
            result += 64 * self.values["xbox"].get(CONSTANTS.XBOX.TRIGGER.AXIS_RT)
            # send all 4 buttons in one byte
            data.append(result)

            data.append(int.from_bytes(CONSTANTS.START_MESSAGE))
            result = 0
            result += 1 * self.values["n64"].get(CONSTANTS.N64.BUTTONS.A)
            result += 4 * self.values["n64"].get(CONSTANTS.N64.BUTTONS.B)
            result += 16 * self.values["n64"].get(CONSTANTS.N64.BUTTONS.L)
            result += 64 * self.values["n64"].get(CONSTANTS.N64.BUTTONS.R)
            data.append(result)
            result = 0
            result += 1 * self.values["n64"].get(CONSTANTS.N64.BUTTONS.C_UP)
            result += 4 * self.values["n64"].get(CONSTANTS.N64.BUTTONS.C_DOWN)
            result += 16 * self.values["n64"].get(CONSTANTS.N64.BUTTONS.C_LEFT)
            result += 64 * self.values["n64"].get(CONSTANTS.N64.BUTTONS.C_RIGHT)
            data.append(result)
            result = 0
            result += 1 * self.values["n64"].get(CONSTANTS.N64.BUTTONS.DP_UP)
            result += 4 * self.values["n64"].get(CONSTANTS.N64.BUTTONS.DP_DOWN)
            result += 16 * self.values["n64"].get(CONSTANTS.N64.BUTTONS.DP_LEFT)
            result += 64 * self.values["n64"].get(CONSTANTS.N64.BUTTONS.DP_RIGHT)
            data.append(result)
            result = 0
            result += 1 * self.values["n64"].get(CONSTANTS.N64.BUTTONS.Z)
            data.append(result)

            data_bytes = bytearray(data)
            print(data_bytes)
            if data_bytes == self.__last_message:
                print("didnt send")
                return
            self.__last_message = data_bytes
            self.xbee_device.send_data(self.remote_xbee, data_bytes)

    def SendQuitMessage(self):
        """
        Tells the rover to quit once the basestation quits
        """

        data = [int.from_bytes(CONSTANTS.QUIT_MESSAGE)]
        data_bytes = bytearray(data)
        print(f"Telling the rover to quit: {data_bytes}")
        self.xbee_device.send_data(self.remote_xbee, data_bytes)

if __name__ == "__main__":
    # allow the controllers to always work
    os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"

    # start pygame
    pygame.init()

    # create the display
    display = Display()

    # create the xbee
    xbee = XbeeControl()

    timer = time.time_ns()
    while not xbee.quit:
        while timer + xbee.FREQUENCY > time.time_ns() and not xbee.quit:
            for event in pygame.event.get():
                xbee.SendCommand(event)
                if event.type == pygame.QUIT:
                    xbee.quit = True

        xbee.UpdateInfo()
        timer = time.time_ns()

    print("QUITTING")
    xbee.SendQuitMessage()

    if xbee.XBEE_ENABLE:
        xbee.xbee_device.close()
