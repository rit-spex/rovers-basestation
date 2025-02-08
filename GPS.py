import time
import board
import busio

i2c = busio.I2C(board.SCL, board.SDA, 115200)

devices = i2c.scan()
if len(devices) == 0:
    print("no i2c devices")
    exit()

device = devices[0]
print(f"reading off device {device}")

buffer = []
while(True):
    i2c.readfrom_into(device, buffer)
    print(buffer)
    time.sleep(0.5)
