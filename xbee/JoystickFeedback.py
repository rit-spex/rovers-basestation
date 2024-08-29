import pygame
from pygame.event import Event


class Display:

    def __init__(self):

        # Set the width and height of the screen (width, height), and name the window.
        self.screen = pygame.display.set_mode((500, 550))
        self.text_print = TextPrint(self.screen)
        self.joysticks = {}
        self.axis = {}
        pygame.display.set_caption("Joystick Feedback")
        self.creep = False
        self.reverse = False

    def Update_Display2(self, creep, reverse):
        self.creep = creep
        self.reverse = reverse

    def Update_Display(self):
        # Drawing step
        # First, clear the screen to white. Don't put other drawing commands
        # above this, or they will be erased with this command.
        self.screen.fill((255, 255, 255))
        self.text_print.reset()

        # Get count of joysticks.
        joystick_count = pygame.joystick.get_count()

        self.text_print.tprint(f"Number of joysticks: {joystick_count}")
        self.text_print.indent()

        # For each joystick:
        for joystick in self.joysticks.values():
            jid = joystick.get_instance_id()

            self.text_print.tprint(f"Joystick {jid}")
            self.text_print.indent()

            # Get the name from the OS for the controller/joystick.
            name = joystick.get_name()
            self.text_print.tprint(f"Joystick name: {name}")

            guid = joystick.get_guid()
            self.text_print.tprint(f"GUID: {guid}")

            power_level = joystick.get_power_level()
            self.text_print.tprint(f"Joystick's power level: {power_level}")

            # Usually axis run in pairs, up/down for one, and left/right for
            # the other. Triggers count as axes.
            axes = joystick.get_numaxes()
            self.text_print.tprint(f"Number of axes: {axes}")
            self.text_print.indent()

            for i in range(axes):
                axis = self.axis[0][i]
                self.text_print.tprint(f"Axis {i} value: {axis:>6.3f}")
            self.text_print.unindent()

            buttons = joystick.get_numbuttons()
            self.text_print.tprint(f"Number of buttons: {buttons}")
            self.text_print.indent()

            for i in range(buttons):
                button = joystick.get_button(i)
                self.text_print.tprint(f"Button {i:>2} value: {button}")
            self.text_print.unindent()

            hats = joystick.get_numhats()
            self.text_print.tprint(f"Number of hats: {hats}")
            self.text_print.indent()

            # Hat position. All or nothing for direction, not a float like
            # get_axis(). Position is a tuple of int values (x, y).
            for i in range(hats):
                hat = joystick.get_hat(i)
                self.text_print.tprint(f"Hat {i} value: {str(hat)}")
            self.text_print.unindent()

            self.text_print.unindent()

            self.text_print.tprint("CreepMode: " + str(self.creep))
            self.text_print.tprint("ReverseMode: "+ str(self.reverse))
        # Go ahead and update the screen with what we've drawn.
        pygame.display.flip()

    def Controller_Display(self, newEvent: Event):
        # Used to manage how fast the screen updates.
        # clock = pygame.time.Clock()

        # This dict can be left as-is, since pygame will generate a
        # pygame.JOYDEVICEADDED event for every joystick connected
        # at the start of the program.
        # done = False
        # while not done:
        # Event processing step.
        # Possible joystick events: JOYAXISMOTION, JOYBALLMOTION, JOYBUTTONDOWN,
        # JOYBUTTONUP, JOYHATMOTION, JOYDEVICEADDED, JOYDEVICEREMOVED

        # Handle hotplugging
        if newEvent.type == pygame.JOYDEVICEADDED:
            # This event will be generated when the program starts for every
            # joystick, filling up the list without needing to create them manually.
            joy = pygame.joystick.Joystick(newEvent.device_index)
            axis = dict()
            for i in range(joy.get_numaxes()):
                axis[i] = joy.get_axis(i)
            self.joysticks[joy.get_instance_id()] = joy
            self.axis[joy.get_instance_id()] = axis
            print(f"Joystick {joy.get_instance_id()} connencted")

        if newEvent.type == pygame.JOYDEVICEREMOVED:
            del self.joysticks[newEvent.instance_id]
            del self.axis[newEvent.instance_id]
            print(f"Joystick {newEvent.instance_id} disconnected")

        if newEvent.type == pygame.JOYAXISMOTION:
            self.axis[0][newEvent.dict['axis']] = newEvent.dict['value']

        self.Update_Display()


class TextPrint:
    def __init__(self, screen):
        self.reset()
        self.font = pygame.font.Font(None, 25)
        self.screen = screen

    def tprint(self, text):
        text_bitmap = self.font.render(text, True, (0, 0, 0))
        self.screen.blit(text_bitmap, (self.x, self.y))
        self.y += self.line_height

    def reset(self):
        self.x = 10
        self.y = 10
        self.line_height = 15

    def indent(self):
        self.x += 10

    def unindent(self):
        self.x -= 10


if __name__ == '__main__':
    pygame.init()
    display = Display()
    display.Update_Display()
    while(True):
        pygame.time.wait(33)
        for event in pygame.event.get():
            display.Controller_Display(event)
