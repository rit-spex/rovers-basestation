import serial
import math
import pygame
import os
from pygame.event import Event

from CommandCodes import CommandCodes
from JoystickFeedback import Display

class XbeeControl:
    def __init__(self):
        self.joysticks = {}

        self.quit = False

        self.creepMode = False
        self.reverseMode = False

        self.values = {
            # axis value starts at 100 with the range of [0,200] so 100 is Neutral
            CommandCodes.JOYSTICK.AXIS_LX.index: b'\x64',
            CommandCodes.JOYSTICK.AXIS_LY.index: b'\x64',
            CommandCodes.JOYSTICK.AXIS_RX.index: b'\x64',
            CommandCodes.JOYSTICK.AXIS_RY.index: b'\x64',

            # these are bool values that either 1 or 2
            CommandCodes.TRIGGER.AXIS_LT.index:  1,
            CommandCodes.TRIGGER.AXIS_RT.index:  1,
            CommandCodes.BUTTONS.A.index+6: 1,
            CommandCodes.BUTTONS.B.index+6: 1,
            CommandCodes.BUTTONS.X.index+6: 1,
            CommandCodes.BUTTONS.Y.index+6: 1,
            CommandCodes.BUTTONS.LEFT_BUMPER.index+6: 1,
            CommandCodes.BUTTONS.RIGHT_BUMPER.index+6: 1,
            CommandCodes.BUTTONS.START.index+6: 1,
            CommandCodes.BUTTONS.SELECT.index+6: 1}

        self.XBEE_ENABLE = True
        if (self.XBEE_ENABLE):
            self.PORT = "/dev/ttyUSB0"  # change based on current xbee coms
            self.BAUD_RATE = 230400 # 921600  # change based on xbee baud_rate
            self.xbee_device = XBeeDevice(self.PORT, self.BAUD_RATE)
            self.xbee_device.open()
            self.remote_xbee = RemoteXBeeDevice(self.xbee_device, XBee64BitAddress.from_hex_string("0013A20041B1D309"))

            # self.XbeeCom = serial.Serial(self.PORT,
            #                              self.BAUD_RATE)  # create the actual serial - will error if port doesn't exist

        self.DEADBAND = 0.10  # this is the dead band on the controller
        self.XbeeCom = serial.Serial(self.PORT, self.BAUD_RATE)  # create the actual serial

    """

    """
    def SendCommand(self, newEvent: Event):
        # the different event types
        # JOYAXISMOTION, JOYBALLMOTION, JOYBUTTONDOWN,
        # JOYBUTTONUP, JOYHATMOTION, JOYDEVICEADDED, JOYDEVICEREMOVED

        match (newEvent.type):
            # hot swappable
            case pygame.JOYDEVICEADDED | pygame.JOYDEVICEREMOVED:
                self.HotPluggin(newEvent)
                display.Controller_Display(newEvent)

            # axis
            case pygame.JOYAXISMOTION:
                multiplier = 100
                if(self.creepMode):
                    multiplier = 50
                if(self.reverseMode):
                    multiplier = -multiplier

                if((abs(newEvent.dict['value']) < self.DEADBAND) and (newEvent.dict['axis'] < 4)):
                    self.values[newEvent.dict['axis']] = b'\x64'
                    newEvent.dict['value'] = 0
                elif(newEvent.dict['axis'] < 4):
                    # self.SendAxis(newEvent)
                    newValue = math.floor(multiplier * newEvent.dict['value'] + 100)
                    if(newValue<0):
                        newValue = 0
                    self.values[newEvent.dict['axis']] = newValue.to_bytes(1)
                else:
                    if(newEvent.dict['value'] > 0):
                        self.values[newEvent.dict['axis']] = 2
                    else:
                        self.values[newEvent.dict['axis']] = 1
                display.Controller_Display(newEvent)

            # button
            case pygame.JOYBUTTONDOWN | pygame.JOYBUTTONUP:
                self.SendButton(newEvent)
                display.Controller_Display(newEvent)

            case pygame.JOYHATMOTION:
                self.SendJoyPad(newEvent)
                display.Update_Display2(creep=self.creepMode,reverse=self.reverseMode)
                display.Controller_Display(newEvent)

    def HotPluggin(self, newEvent: Event):
        # Handle hotplugging
        if newEvent.type == pygame.JOYDEVICEADDED:
            # This event will be generated when the program starts for every
            # joystick, filling up the list without needing to create them manually.
            joy = pygame.joystick.Joystick(newEvent.device_index)
            self.joysticks[joy.get_instance_id()] = joy
            print(f"Joystick {joy.get_instance_id()} connencted")

        if newEvent.type == pygame.JOYDEVICEREMOVED:
            self.quit = True
            del self.joysticks[newEvent.instance_id]
            print(f"Joystick {newEvent.instance_id} disconnected")

    def SendAxis(self, newEvent: Event):
        pass

    def SendButton(self, newEvent: Event):
        # result = "Button: "
        newValue = self.joysticks[newEvent.dict['joy']].get_button(newEvent.dict['button'])
        if(newValue == 0):
            # the button is on value is on
            # I choose 1
            self.values[newEvent.dict['button'] + 6] = 1
        else:
            # the button is on value is on
            # I choose 2 b/c = bit value of 10 if error would happen they would be most likely 11 or 00
            self.values[newEvent.dict['button'] + 6] = 2

    def SendJoyPad(self, newEvent: Event):
        x, y = newEvent.dict['value']
        result = ""

        if(x == 0 and y==1):
            if(self.values[CommandCodes.BUTTONS.SELECT.index+6] == 2): # left button is on
                self.reverseMode = False
                result= "reverse off"
            if(self.values[CommandCodes.BUTTONS.START.index+6] == 2): # right button is on
                self.creepMode = False
                result= "creep mode off"

        elif(x == 0 and y==-1):
            if(self.values[CommandCodes.BUTTONS.SELECT.index+6] == 2): # left button is on
                self.reverseMode = True
                result= "reverse on"

            if(self.values[CommandCodes.BUTTONS.START.index+6] == 2): # right button is on
                self.creepMode = True
                result= "creep mode on"
        print(result)

    def UpdateInfo(self):
        self.updateLoop += 1

        # if the xbee is enabled
        if (self.XBEE_ENABLE):

            data = [int.from_bytes(CONSTANTS.START_MESSAGE)]

            # write the initial
            #self.XbeeCom.write(CONSTANTS.START_MESSAGE)

            if (not self.reverseMode):
                # send the regular mode so Left joy stick is left and right joy stick is right
                data.append(int.from_bytes(self.values.get(CONSTANTS.JOYSTICK.AXIS_LY)))
                #self.XbeeCom.write(self.values.get(CONSTANTS.JOYSTICK.AXIS_LY))
                data.append(int.from_bytes(self.values.get(CONSTANTS.JOYSTICK.AXIS_RY)))
                #self.XbeeCom.write(self.values.get(CONSTANTS.JOYSTICK.AXIS_RY))
            else:
                # invert the controller so left joy stick is right and right joy stick is left
                data.append(int.from_bytes(self.values.get(CONSTANTS.JOYSTICK.AXIS_RY)))
                #self.XbeeCom.write(self.values.get(CONSTANTS.JOYSTICK.AXIS_RY))
                data.append(int.from_bytes(self.values.get(CONSTANTS.JOYSTICK.AXIS_LY)))
                #self.XbeeCom.write(self.values.get(CONSTANTS.JOYSTICK.AXIS_LY))

            result = 0
            # the first two bits
            result += 64 * self.values.get(CONSTANTS.BUTTONS.A + 6)
            # the 3rd and 4th bits
            result += 16 * self.values.get(CONSTANTS.BUTTONS.B + 6)
            # the 5th and 6th bits
            result += 4 * self.values.get(CONSTANTS.BUTTONS.X + 6)
            # the 7th and 8th bits
            result += 1 * self.values.get(CONSTANTS.BUTTONS.Y + 6)

            data.append(result)
            #self.XbeeCom.write(result.to_bytes(1))
            result = 0
            # the first two bits
            result += 64 * self.values.get(CONSTANTS.BUTTONS.LEFT_BUMPER + 6)
            # the 3 and 4th bits
            result += 16 * self.values.get(CONSTANTS.BUTTONS.RIGHT_BUMPER + 6)
            # the 5 and 6th bits
            result += 4 * self.values.get(CONSTANTS.TRIGGER.AXIS_LT)
            # the 7 and 8th bits
            result += 1 * self.values.get(CONSTANTS.TRIGGER.AXIS_RT)
            # send all 4 buttons in one byte
            data.append(result)
            # self.XbeeCom.write(result.to_bytes(1))

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
    while (not xbee.quit):
        pygame.time.delay(40)
        xbee.UpdateInfo()
        for event in pygame.event.get():
            xbee.SendCommand(event)
            if(event.type == pygame.QUIT):
                xbee.quit = True
    xbee.XbeeCom.close()
