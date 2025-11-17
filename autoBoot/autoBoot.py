import time
import subprocess
import os
from digi.xbee.devices import XBeeDevice, XBeeException

# --- Configuration ---
PORT = "/dev/ttyUSB0"          # Replace with your XBee's serial port (e.g., '/dev/ttyUSB0' on Linux)
BAUD_RATE = 9600       # Adjust to your XBee's baud rate
RETRY_DELAY = 1        # seconds between connection attempts
XBEE_SCRIPT_DIR = "~/rovers-basestation"   # Replace with actual folder containing Xbee.py
XBEE_SCRIPT_NAME = "xbee"

remote_xbee = "0013A200423A7DDD"

def wait_for_xbee_connection():
    """Loop until XBee successfully connects to the robot."""
    print("Waiting for Digi XBee to connect to robot...")

    while True:
        try:
            # Try to open a connection
            device = XBeeDevice(PORT, BAUD_RATE)
            device.open()

            try:
                device.send_data(remote_xbee, "ping")
                print("✅ Robot XBee reachable! Connection established.")
                device.close()
                return True
            except XBeeException as e:
                print("⚠️ Robot XBee not responding yet:", e)

            device.close()
            return True

        except (XBeeException, OSError) as e:
            print(f"⚠️ Connection failed: {e}")
            print(f"Retrying in {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)

def launch_xbee_script():
    print(f"📂 Changing directory to: {XBEE_SCRIPT_DIR}")
    os.chdir(XBEE_SCRIPT_DIR)
    """Launch the main Xbee.py script."""
    print("🚀 Launching Xbee.py...")

    subprocess.run(["python", "-m xbee"], check=True)

if __name__ == "__main__":
    wait_for_xbee_connection()
    launch_xbee_script()
