import pygame
import time

def debug_xbox():
    pygame.init()
    pygame.joystick.init()
    
    count = pygame.joystick.get_count()
    joy = None
    for i in range(count):
        j = pygame.joystick.Joystick(i)
        if "Xbox" in j.get_name():
            joy = j
            break
            
    if not joy:
        print("No Xbox controller found")
        return
        
    joy.init()
    print(f"Monitoring {joy.get_name()}. Move sticks/triggers. Ctrl+C to stop.")
    
    try:
        while True:
            pygame.event.pump()
            axes = [joy.get_axis(i) for i in range(joy.get_numaxes())]
            print(f"\rAxes: " + ", ".join([f"{i}: {v:+.2f}" for i, v in enumerate(axes)]), end="")
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopped.")

if __name__ == "__main__":
    debug_xbox()
