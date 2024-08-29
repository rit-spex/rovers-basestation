import serial
import math
import pygame
import os
import time
from pygame.event import Event
from CommandCodes import CommandCodes
from JoystickFeedback import Display


class XbeeControl:
    def __init__(self):
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
            # Store all the axis
            CommandCodes.JOYSTICK.AXIS_LX: CommandCodes.JOYSTICK.NEUTRAL_HEX,
            CommandCodes.JOYSTICK.AXIS_LY: CommandCodes.JOYSTICK.NEUTRAL_HEX,
            CommandCodes.JOYSTICK.AXIS_RX: CommandCodes.JOYSTICK.NEUTRAL_HEX,
            CommandCodes.JOYSTICK.AXIS_RY: CommandCodes.JOYSTICK.NEUTRAL_HEX,

            # Store all the buttons
            CommandCodes.TRIGGER.AXIS_LT: CommandCodes.BUTTONS.OFF,
            CommandCodes.TRIGGER.AXIS_RT: CommandCodes.BUTTONS.OFF,
            CommandCodes.BUTTONS.A + 6: CommandCodes.BUTTONS.OFF,
            CommandCodes.BUTTONS.B + 6: CommandCodes.BUTTONS.OFF,
            CommandCodes.BUTTONS.X + 6: CommandCodes.BUTTONS.OFF,
            CommandCodes.BUTTONS.Y + 6: CommandCodes.BUTTONS.OFF,
            CommandCodes.BUTTONS.LEFT_BUMPER + 6: CommandCodes.BUTTONS.OFF,
            CommandCodes.BUTTONS.RIGHT_BUMPER + 6: CommandCodes.BUTTONS.OFF,
            CommandCodes.BUTTONS.START + 6: CommandCodes.BUTTONS.OFF,
            CommandCodes.BUTTONS.SELECT + 6: CommandCodes.BUTTONS.OFF}

        self.XBEE_ENABLE = False
        if (self.XBEE_ENABLE):
            self.PORT = "COM11"  # change based on current xbee coms
            self.BAUD_RATE = 9600  # change based on xbee baud_rate
            self.XbeeCom = serial.Serial(self.PORT,
                                         self.BAUD_RATE)  # create the actual serial - will error if port doesn't exist

        self.DEADBAND = 0.10  # this is the dead band on the controller
        self.FREQUENCY = 40000  # how often the message is sent, (ns)
        self.updateLoop = 0

    """
    Update the values stored when an event is received from controller
    newEvent: the new event from the controller
    """

    def SendCommand(self, newEvent: Event):
        # the different event types
        # JOYAXISMOTION, JOYBALLMOTION, JOYBUTTONDOWN,
        # JOYBUTTONUP, JOYHATMOTION, JOYDEVICEADDED, JOYDEVICEREMOVED

        match (newEvent.type):
            # controller was added or removed
            case pygame.JOYDEVICEADDED | pygame.JOYDEVICEREMOVED:
                self.HotPluggin(newEvent)

            # axis
            case pygame.JOYAXISMOTION:
                # Joystick Axis
                if (newEvent.dict['axis'] < 4):
                    self.SendJoystickAxis(newEvent)
                # Trigger Axis
                else:
                    self.SendTriggerAxis(newEvent)

            # button
            case pygame.JOYBUTTONDOWN | pygame.JOYBUTTONUP:
                self.SendButton(newEvent)

            case pygame.JOYHATMOTION:
                self.SendJoyPad(newEvent)
                display.Update_Display2(creep=self.creepMode, reverse=self.reverseMode)
        display.Controller_Display(newEvent)

    """
    Handle events when the controller is plugin or unpluged
    Plugin: Add device to controller array
    Unpluged: Removed the device and kill the code
    """

    def HotPluggin(self, newEvent: Event):
        # A new device is added
        if newEvent.type == pygame.JOYDEVICEADDED:
            # This event will be generated when the program starts for every
            # joystick, filling up the list without needing to create them manually.
            joy = pygame.joystick.Joystick(newEvent.device_index)
            self.joysticks[joy.get_instance_id()] = joy
            print(f"Joystick {joy.get_instance_id()} connencted")

        # A device is removed
        if newEvent.type == pygame.JOYDEVICEREMOVED:
            # remove the controller from the joystick list and kill the code
            self.quit = True
            del self.joysticks[newEvent.instance_id]
            print(f"Joystick {newEvent.instance_id} disconnected")

    """
    Handle events when an joystick axis is pushed
    """

    def SendJoystickAxis(self, newEvent: Event):
        # multiplier out of 100 to scale the output
        multiplier = 100
        if (self.creepMode):
            # half the speed of the controller
            multiplier = 20
        if (self.reverseMode):
            # flip the direction of axis of the controller
            multiplier = -multiplier

        # check for deadband. If inside then zero values
        if (abs(newEvent.dict['value']) < self.DEADBAND):
            newEvent.dict['value'] = 0

        # convert the controller to int with multiplier
        newValue = math.floor(multiplier * newEvent.dict['value'] + CommandCodes.JOYSTICK.NEUTRAL_INT)

        # check if value is between min and max
        if (newValue < CommandCodes.JOYSTICK.MIN_VALUE):
            newValue = CommandCodes.JOYSTICK.MIN_VALUE
        elif (newValue > CommandCodes.JOYSTICK.MAX_VALUE):
            newValue = CommandCodes.JOYSTICK.MAX_VALUE

        self.values[newEvent.dict['axis']] = newValue.to_bytes(1)  # store the value as one byte

    """
    Handle events when an joystick axis is pushed
    """

    def SendTriggerAxis(self, newEvent: Event):
        # Treat joystick like a button.
        # If it is over zero then on, otherwise off
        if (newEvent.dict['value'] > 0):
            self.values[newEvent.dict['axis']] = CommandCodes.BUTTONS.ON
        else:
            self.values[newEvent.dict['axis']] = CommandCodes.BUTTONS.OFF

    """
    Handle button event
    """

    def SendButton(self, newEvent: Event):
        newValue = self.joysticks[newEvent.dict['joy']].get_button(newEvent.dict['button'])
        if (newValue == 0):
            # the button is off
            self.values[newEvent.dict['button'] + 6] = CommandCodes.BUTTONS.OFF
        else:
            # the button is on
            self.values[newEvent.dict['button'] + 6] = CommandCodes.BUTTONS.ON

        # if button is home kill the code
        if(newEvent.dict['button'] == CommandCodes.BUTTONS.HOME):
            self.quit = True


    """
    Handle JoyPad events
    """

    def SendJoyPad(self, newEvent: Event):

        # if joypad is down disable modes
        if (newEvent.dict['value'] == CommandCodes.JOYPAD.DOWN):
            if (self.values[CommandCodes.BUTTONS.SELECT + 6] == CommandCodes.BUTTONS.ON):  # left button is on
                self.reverseMode = False
                print("reverse off")
            if (self.values[CommandCodes.BUTTONS.START + 6] == CommandCodes.BUTTONS.ON):  # right button is on
                self.creepMode = False
                print("creep mode off")

        # if joypad is up enable modes
        elif (newEvent.dict['value'] == CommandCodes.JOYPAD.UP):
            if (self.values[CommandCodes.BUTTONS.SELECT + 6] == CommandCodes.BUTTONS.ON):  # left button is on
                self.reverseMode = True
                print("reverse on")

            if (self.values[CommandCodes.BUTTONS.START + 6] == CommandCodes.BUTTONS.ON):  # right button is on
                self.creepMode = True
                print("creep mode on")

    """
    Send the current values to the controller
    """

    def UpdateInfo(self):
        self.updateLoop+=1
        print(self.updateLoop)
        # if the xbee is enabled
        if (self.XBEE_ENABLE):

            # write the initial
            self.XbeeCom.write(CommandCodes.START_MESSAGE)

            if (not self.reverseMode):
                # send the regular mode so Left joy stick is left and right joy stick is right
                self.XbeeCom.write(self.values.get(CommandCodes.JOYSTICK.AXIS_LY))
                self.XbeeCom.write(self.values.get(CommandCodes.JOYSTICK.AXIS_RY))
            else:
                # invert the controller so left joy stick is right and right joy stick is left
                self.XbeeCom.write(self.values.get(CommandCodes.JOYSTICK.AXIS_RY))
                self.XbeeCom.write(self.values.get(CommandCodes.JOYSTICK.AXIS_LY))

            result = 0
            # the first two bits
            result += 64 * self.values.get(CommandCodes.BUTTONS.A + 6)
            # the 3rd and 4th bits
            result += 16 * self.values.get(CommandCodes.BUTTONS.B + 6)
            # the 5th and 6th bits
            result += 4 * self.values.get(CommandCodes.BUTTONS.X + 6)
            # the 7th and 8th bits
            result += 1 * self.values.get(CommandCodes.BUTTONS.Y + 6)

            self.XbeeCom.write(result.to_bytes(1))
            result = 0
            # the first two bits
            result += 64 * self.values.get(CommandCodes.BUTTONS.LEFT_BUMPER + 6)
            # the 3 and 4th bits
            result += 16 * self.values.get(CommandCodes.BUTTONS.RIGHT_BUMPER + 6)
            # the 5 and 6th bits
            result += 4 * self.values.get(CommandCodes.TRIGGER.AXIS_LT)
            # the 7 and 8th bits
            result += 1 * self.values.get(CommandCodes.TRIGGER.AXIS_RT)
            # send all 4 buttons in one byte
            self.XbeeCom.write(result.to_bytes(1))

            # make sure all the byte are sent
            self.XbeeCom.flush()


if __name__ == '__main__':
    # allow the controllers to always work
    os.environ['SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS'] = '1'

    # start pygame
    pygame.init()

    # create the display
    display = Display()

    # create the xbee
    xbee = XbeeControl()

    timer = time.time_ns()
    while (not xbee.quit):
        while (timer + xbee.FREQUENCY > time.time_ns() and not xbee.quit):
            for event in pygame.event.get():
                xbee.SendCommand(event)
                if (event.type == pygame.QUIT):
                    xbee.quit = True

        xbee.UpdateInfo()
        timer = time.time_ns()

    if(xbee.XBEE_ENABLE):
        xbee.XbeeCom.close()
