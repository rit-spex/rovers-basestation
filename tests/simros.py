# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : simros.py
# purpose       : simulate rover packet response over UDP
# created on    : 11/9/2026 - Zach
# last modified : 11/9/2026 - Zach
# ------------------------------------------------------------------

import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from basestation.protocol import CONSTANTS, MSG, MessageEncoder

COMM = CONSTANTS.COMMUNICATION # harder to read w/o shortening


def main():
    encoder = MessageEncoder()
    request_size = len(encoder.encode_data({}, MSG.AUTO_STATE_ID))
    target = (COMM.UDP_HOST, COMM.UDP_TELEMETRY_PORT)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as rover:
        rover.bind((COMM.UDP_HOST, COMM.UDP_ROVER_PORT))
        print(f"Listening on {COMM.UDP_HOST}:{COMM.UDP_ROVER_PORT} (Ctrl+C to stop)")
        try:
            while True:
                data, _ = rover.recvfrom(4096)
                if (len(data) != request_size) or (data[0] != MSG.AUTO_STATE_ID):
                    continue
                values, _ = encoder.decode_data(data)
                mode = values["auto_state"]
                reply = encoder.encode_data({"control_mode": mode}, MSG.CONTROL_MODE_ID)
                rover.sendto(reply, target)
                print(f"auto_state {mode} -> control_mode {mode}")
        except KeyboardInterrupt:
            print("\nstopped\n")


if __name__ == "__main__":
    main()
