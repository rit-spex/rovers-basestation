#import XBeeDevice
from xbee import ZigBee
import serial
import time

# Set up serial connection for Xbee
PORT = "COM4"  # Adjust based on your system
BAUD_RATE = 9600
ser = serial.Serial(PORT, BAUD_RATE)

# Initialize the ZigBee object
xbee = ZigBee(ser)

# Replace with the actual address of the destination Xbee
DEST_ADDR = '13A200423A83A9'  # Example 64-bit address

try:
    while True:
        data = input("Enter message to send: ")
        # Send data to the destination Xbee
        #xbee.send('tx', dest_addr_long=DEST_ADDR, data=data.encode())
        ser.write(data.encode())
        #print(f"Sent: {data}")
        #time.sleep(1)  # Add a delay between transmissions (optional)

except KeyboardInterrupt:
    print("Exiting...")
    ser.close()
