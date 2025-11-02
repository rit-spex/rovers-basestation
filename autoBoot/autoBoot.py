import time
import subprocess
from digi.xbee.devices import XBeeDevice, XBeeException

# --- Configuration ---
PORT = "/dev/ttyUSB0"          # Replace with your XBee's serial port (e.g., '/dev/ttyUSB0' on Linux)
BAUD_RATE = 9600       # Adjust to your XBee's baud rate
RETRY_DELAY = 5        # seconds between connection attempts

def wait_for_xbee_connection():
    """Loop until XBee successfully connects to the robot."""
    print("Waiting for Digi XBee to connect to robot...")

    while True:
        try:
            # Try to open a connection
            device = XBeeDevice(PORT, BAUD_RATE)
            device.open()

            # Optionally test a ping or read parameter to ensure it's responsive
            node_id = device.get_node_id()
            print(f"✅ XBee connected successfully (Node ID: {node_id})")

            device.close()
            return True

        except (XBeeException, OSError) as e:
            print(f"⚠️ Connection failed: {e}")
            print(f"Retrying in {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)

def launch_xbee_script():
    """Launch the main Xbee.py script."""
    print("🚀 Launching Xbee.py...")
    subprocess.run(["python", "Xbee.py"], check=True)

if __name__ == "__main__":
    wait_for_xbee_connection()
    launch_xbee_script()