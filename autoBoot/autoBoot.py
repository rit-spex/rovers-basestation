import serial
import time
from digi.xbee.devices import XBeeDevice # Assuming you are using the Digi XBee Python Library
import xbee.Xbee

# XBee configuration
PORT = "/dev/ttyUSB0"  # Replace with your XBee's serial port
BAUD_RATE = 9600

xbee = None # Initialize xbee device as None

# Loop to continuously try connecting to XBee
while xbee is None:
    try:
        print(f"Attempting to connect to XBee on {PORT} at {BAUD_RATE}...")
        xbee = XBeeDevice(PORT, BAUD_RATE)
        xbee.open()
        print("XBee connected successfully!")
    except serial.SerialException as e:
        print(f"Serial port error: {e}. Retrying in 5 seconds...")
        xbee = None # Ensure xbee remains None if connection failed
        time.sleep(5)
    except Exception as e:
        print(f"An unexpected error occurred: {e}. Retrying in 5 seconds...")
        xbee = None
        time.sleep(5)

# Once connected, proceed with the rest of your script
print("Moving to the next part of the script...")

# executing the xbee python file
xbee.__init__()
