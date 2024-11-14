import serial 
import time
from xbee import ZigBee

PORT = "COM3" #change the port if you are not using Windows to whatever port you are using
BAUD_RATE = 9600
ser = serial.Serial(PORT, BAUD_RATE)

# Create API object

xbee = ZigBee(ser)

# Continuously read and print packets
while True:
    try:
        response = xbee.wait_read_frame()

        print("\nPacket received at %s : %s" %(time.time(), response))

    except KeyboardInterrupt:
        ser.close()
        break