import serial
#import xbee
from xbee import ZigBee as x

PORT = "COM4" #change the port if you are not using Windows to whatever port you are using
BAUD_RATE = 9600
ser = serial.Serial(PORT, BAUD_RATE)

while True:
    try:
        data = input("Send:")
        ser.write(data.encode()) #if you are using python 3 replace data with data.encode()
        ser.send('tx', "13A200", data)
    except KeyboardInterrupt:
        ser.close()
        break