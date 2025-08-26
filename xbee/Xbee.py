import serial
import math
import pygame
import os
import time
import configparser
from pygame.event import Event
from pygame.joystick import Joystick
from JoystickFeedback import Display
from digi.xbee.devices import XBeeDevice, RemoteXBeeDevice, XBee64BitAddress

# Flag to express the start of a message
START_MESSAGE = b'\xDE'

# Flag to express that the rover should cease functions
QUIT_MESSAGE = b'\xFE'

# The starting value of an axis input
NEUTRAL_HEX = b'\x64'

# The neutral value of an axis input after conversion to int
NEUTRAL_INT   = 100

# The minimum value an axis input can have after conversion to int
MIN_VALUE = 0

# The maximum value an axis input can have after conversion to int
MAX_VALUE = 200

# The bit value representing a button being on
ON = 2

# The bit value representing a button being off
OFF = 1


class XbeeControl:
    def __init__(self):
        # settings
        self.settings = configparser.ConfigParser()
        self.settings.read("./settings.ini")

        # a set to hold multiple joysticks
        self.joysticks = {}

        # flag to quit the program
        self.quit = False

        # flag to half the speed
        self.creepMode = False

        # flag to flip the drive control
        self.reverseMode = False

        # initialize all of values
        self.values = {
            "xbox": {
                # Store all the axis
                int(self.settings['drive_base_IDs']["left_stick_x"]): NEUTRAL_HEX,
                int(self.settings['drive_base_IDs']["left_stick_y"]): NEUTRAL_HEX,
                int(self.settings['drive_base_IDs']["right_stick_x"]): NEUTRAL_HEX,
                int(self.settings['drive_base_IDs']["right_stick_y"]): NEUTRAL_HEX,
                # Store all the buttons
                int(self.settings['drive_base_IDs']['left_trigger']): OFF,
                int(self.settings['drive_base_IDs']['right_trigger']): OFF,
                int(self.settings['drive_base_IDs']['a']) + 6: OFF,
                int(self.settings['drive_base_IDs']['b']) + 6: OFF,
                int(self.settings['drive_base_IDs']['x']) + 6: OFF,
                int(self.settings['drive_base_IDs']['y']) + 6: OFF,
                int(self.settings['drive_base_IDs']['left_bumper']) + 6: OFF,
                int(self.settings['drive_base_IDs']['right_bumper']) + 6: OFF,
                int(self.settings['drive_base_IDs']['start']) + 6: OFF,
                int(self.settings['drive_base_IDs']['select']) + 6: OFF,
            },
            "n64": {
                # Buttons
                int(self.settings['arm_IDs']['a']): OFF,
                int(self.settings['arm_IDs']['b']): OFF,
                int(self.settings['arm_IDs']['c_up']): OFF,
                int(self.settings['arm_IDs']['c_down']): OFF,
                int(self.settings['arm_IDs']['c_left']): OFF,
                int(self.settings['arm_IDs']['c_right']): OFF,
                int(self.settings['arm_IDs']['left_bumper']): OFF,
                int(self.settings['arm_IDs']['right_bumper']): OFF,
                int(self.settings['arm_IDs']['z_bumper']): OFF,
                int(self.settings['arm_IDs']['dp_up']): OFF,
                int(self.settings['arm_IDs']['dp_down']): OFF,
                int(self.settings['arm_IDs']['dp_left']): OFF,
                int(self.settings['arm_IDs']['dp_right']): OFF,
            }
        }

        self.drive_base_instance_ID = -1
        self.arm_instance_ID = -1

        self.XBEE_ENABLE = True
        if self.XBEE_ENABLE:
            self.PORT = self.settings['peripherals']['port']
            self.BAUD_RATE = self.settings['peripherals']['baud_rate']
            self.xbee_device = XBeeDevice(self.PORT, self.BAUD_RATE)
            self.xbee_device.open()
            self.remote_xbee = RemoteXBeeDevice(
                self.xbee_device, XBee64BitAddress.from_hex_string(self.settings['peripherals']['address']) # old one that broke, lmao 0013A20041B1D309
            )

        # this is the dead zone on the controller
        self.DEAD_ZONE = self.settings['preferences']['dead_zone']

        # how often the message is sent, (ns)
        self.FREQUENCY = 40000000

        self.updateLoop = 0

        # last sent message
        # used for checking if a new message should be sent
        self.__last_message = bytearray()

    def SendCommand(self, newEvent: Event):
        """Update the values stored when an event is received from controller

        Args:
            newEvent (Event): the new event from the controller
        """

        # disregard this event if this isn't a new controller
        # event and we don't have any controller connected
        if len(self.joysticks.keys()) == 0 and newEvent.type != pygame.JOYDEVICEADDED:
            return

        # the different event types:
        # JOYAXISMOTION, JOYBALLMOTION, JOYBUTTONDOWN,
        # JOYBUTTONUP, JOYHATMOTION, JOYDEVICEADDED, JOYDEVICEREMOVED
        match (newEvent.type):
            # controller was added or removed
            case pygame.JOYDEVICEADDED | pygame.JOYDEVICEREMOVED:
                self.HotPluggin(newEvent)

            # Dealing with Axis
            case pygame.JOYAXISMOTION:
                # Dealing with Joystick Axis
                if newEvent.dict["axis"] in [
                    self.settings['drive_base_IDs']['left_stick_x'],
                    self.settings['drive_base_IDs']['left_stick_y'],
                    self.settings['drive_base_IDs']['right_stick_x'],
                    self.settings['drive_base_IDs']['right_stick_y'],
                ]:
                    self.SendJoystickAxis(newEvent)
                # Dealing with Trigger Axis
                else:
                    self.SendTriggerAxis(newEvent)

            # Dealing with Buttons
            case pygame.JOYBUTTONDOWN | pygame.JOYBUTTONUP:
                self.SendButton(newEvent)

            # Dealing with a DPad
            case pygame.JOYHATMOTION:
                self.SendJoyPad(newEvent)
                display.Update_Display2(creep=self.creepMode, reverse=self.reverseMode)

            case _:
                print(f"event {event} not accounted for")

        display.Controller_Display(newEvent)

    def HotPluggin(self, newEvent: Event):
        """Handle events when the controller is plugin or unpluged

        On Plugin: Add device to controller array
        On Unpluged: Remove the device and kill the code

        Args:
            newEvent (Event): the new event from the controller
        """

        # A new device is added
        if newEvent.type == pygame.JOYDEVICEADDED:
            # This event will be generated when the program starts for every
            # joystick, filling up the list without needing to create them manually.
            joy = pygame.joystick.Joystick(newEvent.device_index)
            self.joysticks[joy.get_instance_id()] = joy
            if joy.get_name() == self.settings['peripherals']['drive_base_name']:
                self.instance_id_values_map[joy.get_instance_id()] = "xbox"
            elif joy.get_name() == self.settings['peripherals']['arm_name']:
                self.instance_id_values_map[joy.get_instance_id()] = "n64"
            print(f"Joystick {joy.get_instance_id()} connencted")

        # A device is removed
        if newEvent.type == pygame.JOYDEVICEREMOVED:
            # Remove the controller from the joystick list and kill the code
            self.quit = True
            del self.joysticks[newEvent.instance_id]
            print(f"Joystick {newEvent.instance_id} disconnected")

    def SendJoystickAxis(self, newEvent: Event):
        """Handle events when an joystick axis is pushed

        Args:
            newEvent (Event): the new event from the controller
        """

        # get the key for the controller values
        values_name = self.instance_id_values_map[newEvent.dict["instance_id"]]

        # disregard this event if this is from the arm controller
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

        # check for DEAD_ZONE. If inside then zero values
        if abs(newEvent.dict["value"]) < self.DEAD_ZONE:
            newEvent.dict["value"] = 0

        # convert the controller to int with multiplier
        newValue = math.floor(
            multiplier * newEvent.dict["value"] + NEUTRAL_INT
        )

        # check if value is between min and max
        if newValue < MIN_VALUE:
            newValue = MIN_VALUE
        elif newValue > MAX_VALUE:
            newValue = MAX_VALUE

        # store the value as one byte
        self.values[values_name][newEvent.dict["axis"]] = newValue.to_bytes(
            1
        )

    def SendTriggerAxis(self, newEvent: Event):
        """Handle events when an joystick axis is pushed

        Args:
            newEvent (Event): the new event from the controller
        """

        # disregard this event if this is from the arm controller
        if self.instance_id_values_map[newEvent.dict["instance_id"]] == "n64":
            return

        # Treat joystick like a button.
        # If it is over zero then on, otherwise off
        if newEvent.dict["value"] > 0:
            self.values["xbox"][newEvent.dict["axis"]] = ON
        else:
            self.values["xbox"][newEvent.dict["axis"]] = OFF

    def SendButton(self, newEvent: Event):
        """Handle button event

        Args:
            newEvent (Event): the new event from the controller
        """

        # get the key for the controller values
        values_name = self.instance_id_values_map[newEvent.dict["instance_id"]]

        newValue = self.joysticks[newEvent.dict["joy"]].get_button(
            newEvent.dict["button"]
        )

        # if button is home kill the code; ignore if n64
        if values_name == "xbox" and newEvent.dict["button"] == self.settings['drive_base_IDs']['home'] or values_name == "n64" and newEvent.dict["button"] == self.settings['arm_IDs']['start']:
            self.quit = True

        # update current values
        self.values[values_name][newEvent.dict["button"] + (6 if values_name == "xbox" else 0)] = newValue + 1

    def SendJoyPad(self, newEvent: Event):
        """Handle JoyPad events

        Args:
            newEvent (Event): the new event from the controller
        """

        # get the key for the controller values
        values_name = self.instance_id_values_map[newEvent.dict["instance_id"]]

        # do seperate code if this is from the arm controller
        if values_name == "n64":
            x = newEvent.dict["value"][0]
            y = newEvent.dict["value"][1]

            match x:
                case 0:
                    self.values[values_name][self.settings['arm_IDs']['dp_left']] = OFF
                    self.values[values_name][self.settings['arm_IDs']['dp_right']] = OFF
                case -1:
                    self.values[values_name][self.settings['arm_IDs']['dp_left']] = ON
                    self.values[values_name][self.settings['arm_IDs']['dp_right']] = OFF
                case 1:
                    self.values[values_name][self.settings['arm_IDs']['dp_left']] = OFF
                    self.values[values_name][self.settings['arm_IDs']['dp_right']] = ON
            match y:
                case 0:
                    self.values[values_name][self.settings['arm_IDs']['dp_down']] = OFF
                    self.values[values_name][self.settings['arm_IDs']['dp_up']] = OFF
                case -1:
                    self.values[values_name][self.settings['arm_IDs']['dp_down']] = ON
                    self.values[values_name][self.settings['arm_IDs']['dp_up']] = OFF
                case 1:
                    self.values[values_name][self.settings['arm_IDs']['dp_down']] = OFF
                    self.values[values_name][self.settings['arm_IDs']['dp_up']] = ON
            return

        # if joypad is down disable modes
        if newEvent.dict["value"] == int(self.settings['drive_base_IDs']['down']):
            if (
                self.values['xbox'][int(self.settings['drive_base_IDs']['SELECT']) + 6] == ON
            ):  # left button is on
                self.reverseMode = False
                print("reverse off")
            if (
                self.values['xbox'][int(self.settings['drive_base_IDs']['start']) + 6] == ON
            ):  # right button is on
                self.creepMode = False
                print("creep mode off")

        # if joypad is up enable modes
        elif newEvent.dict["value"] == int(self.settings['drive_base_IDs']['up']):
            if (
                self.values['xbox'][int(self.settings['drive_base_IDs']['select']) + 6] == ON
            ):  # left button is on
                self.reverseMode = True
                print("reverse on")

            if (
                self.values['xbox'][int(self.settings['drive_base_IDs']['start']) + 6] == ON
            ):  # right button is on
                self.creepMode = True
                print("creep mode on")

    def UpdateInfo(self):
        """Send the current values to the controller
        """

        self.updateLoop += 1

        # if the xbee is enabled
        if self.XBEE_ENABLE:

            data = [int.from_bytes(START_MESSAGE)]

            # write the initial
            # self.XbeeCom.write(CONSTANTS.START_MESSAGE)

            if not self.reverseMode:
                # send the regular mode so Left joy stick is left and right joy stick is right
                data.append(int.from_bytes(self.values["xbox"].get(int(self.settings['drive_base_IDs']['left_stick_y']))))
                data.append(int.from_bytes(self.values["xbox"].get(int(self.settings['drive_base_IDs']['right_stick_y']))))
            else:
                # invert the controller so left joy stick is right and right joy stick is left
                data.append(int.from_bytes(self.values["xbox"].get(int(self.settings['drive_base_IDs']['right_stick_y']))))
                data.append(int.from_bytes(self.values["xbox"].get(int(self.settings['drive_base_IDs']['left_stick_y']))))

            result = 0
            # the first two bits
            result += 1 * self.values["xbox"].get(int(self.settings['drive_base_IDs']['a']) + 6)
            # the 3rd and 4th bits
            result += 4 * self.values["xbox"].get(int(self.settings['drive_base_IDs']['b']) + 6)
            # the 5th and 6th bits
            result += 16 * self.values["xbox"].get(int(self.settings['drive_base_IDs']['x']) + 6)
            # the 7th and 8th bits
            result += 64 * self.values["xbox"].get(int(self.settings['drive_base_IDs']['y']) + 6)
            data.append(result)

            result = 0
            # the first two bits
            result += 1 * self.values["xbox"].get(int(self.settings['drive_base_IDs']['left_bumper']) + 6)
            # the 3 and 4th bits
            result += 4 * self.values["xbox"].get(int(self.settings['drive_base_IDs']['right_bumper']) + 6)
            # the 5 and 6th bits
            result += 16 * self.values["xbox"].get(int(self.settings['drive_base_IDs']['left_trigger']))
            # the 7 and 8th bits
            result += 64 * self.values["xbox"].get(int(self.settings['drive_base_IDs']['right_trigger']))
            # send all 4 buttons in one byte
            data.append(result)

            data.append(int.from_bytes(START_MESSAGE))
            result = 0
            result += 1 * self.values["n64"].get(int(self.settings['arm_IDs']['a']))
            result += 4 * self.values["n64"].get(int(self.settings['arm_IDs']['b']))
            result += 16 * self.values["n64"].get(int(self.settings['arm_IDs']['left_bumper']))
            result += 64 * self.values["n64"].get(int(self.settings['arm_IDs']['right_bumper']))
            data.append(result)
            result = 0
            result += 1 * self.values["n64"].get(int(self.settings['arm_IDs']['c_up']))
            result += 4 * self.values["n64"].get(int(self.settings['arm_IDs']['c_down']))
            result += 16 * self.values["n64"].get(int(self.settings['arm_IDs']['c_left']))
            result += 64 * self.values["n64"].get(int(self.settings['arm_IDs']['c_right']))
            data.append(result)
            result = 0
            result += 1 * self.values["n64"].get(int(self.settings['arm_IDs']['dp_up']))
            result += 4 * self.values["n64"].get(int(self.settings['arm_IDs']['dp_down']))
            result += 16 * self.values["n64"].get(int(self.settings['arm_IDs']['dp_left']))
            result += 64 * self.values["n64"].get(int(self.settings['arm_IDs']['dp_right']))
            data.append(result)
            result = 0
            result += 1 * self.values["n64"].get(int(self.settings['arm_IDs']['z_bumper']))
            # result += 4 * self.values["n64"].get()
            # result += 16 * self.values["n64"].get()
            # result += 64 * self.values["n64"].get()
            data.append(result)

            # make sure all the byte are sent
            # self.XbeeCom.flush()
            data_bytes = bytearray(data)
            print(data_bytes)
            if data_bytes == self.__last_message:
                print("didnt send")
                return

            # update last message
            self.__last_message = data_bytes

            # push the message
            self.xbee_device.send_data(self.remote_xbee, data_bytes)

    def SendQuitMessage(self):
        """Tells the rover to quit once the basestation quits
        """

        data = [int.from_bytes(QUIT_MESSAGE)]
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

                # if pygame quits, quit the program
                if event.type == pygame.QUIT:
                    xbee.quit = True

        xbee.UpdateInfo()
        timer = time.time_ns()

    print("QUITTING")
    xbee.SendQuitMessage()

    if xbee.XBEE_ENABLE:
        xbee.xbee_device.close()
