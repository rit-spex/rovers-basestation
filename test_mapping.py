import pygame
pygame.init()
pygame.joystick.init()
j = pygame.joystick.Joystick(0)
j.init()
print(f"Controller: {j.get_name()}")
print("Axis count:", j.get_numaxes())
