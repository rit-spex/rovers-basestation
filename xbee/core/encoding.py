from command_codes import CONSTANTS

class BaseStationCommunication:

    """Module for encoding and decoding data for XBee communication."""

    def __init__(self):
        self.messages = { # Note: dictationaries are ordered in Python 3.7+
            CONSTANTS.COMPACT_MESSAGES.HEARTBEAT: # byte 0
            {
                "name": "heartbeat",
                "values": {"timestamp": CONSTANTS.COMPACT_MESSAGES.UINT_16} # byte 1-2
            },
            CONSTANTS.COMPACT_MESSAGES.N64_ID: { # byte 0
                "name": "n64",
                "values": {"a": CONSTANTS.COMPACT_MESSAGES.UINT_2, "b": CONSTANTS.COMPACT_MESSAGES.UINT_2, "L": CONSTANTS.COMPACT_MESSAGES.UINT_2, "R": CONSTANTS.COMPACT_MESSAGES.UINT_2, # byte 1
                        "C_UP": CONSTANTS.COMPACT_MESSAGES.UINT_2, "C_DOWN": CONSTANTS.COMPACT_MESSAGES.UINT_2, "C_LEFT": CONSTANTS.COMPACT_MESSAGES.UINT_2, "C_RIGHT": CONSTANTS.COMPACT_MESSAGES.UINT_2, # byte 2
                        "DP_UP": CONSTANTS.COMPACT_MESSAGES.UINT_2, "DP_DOWN": CONSTANTS.COMPACT_MESSAGES.UINT_2, "DP_LEFT": CONSTANTS.COMPACT_MESSAGES.UINT_2, "DP_RIGHT": CONSTANTS.COMPACT_MESSAGES.UINT_2, # byte 3
                        "Z": CONSTANTS.COMPACT_MESSAGES.UINT_2} # byte 4
            },
            CONSTANTS.COMPACT_MESSAGES.Xbox_ID: { # byte 0
                "name": "xbox",
                "values": {"ly": CONSTANTS.COMPACT_MESSAGES.UINT_8, # byte 1
                           "ry": CONSTANTS.COMPACT_MESSAGES.UINT_8, # byte 2
                            "A": CONSTANTS.COMPACT_MESSAGES.UINT_2, "B": CONSTANTS.COMPACT_MESSAGES.UINT_2, "X": CONSTANTS.COMPACT_MESSAGES.UINT_2, "Y": CONSTANTS.COMPACT_MESSAGES.UINT_2, # byte 3
                            "LB": CONSTANTS.COMPACT_MESSAGES.UINT_2, "RB": CONSTANTS.COMPACT_MESSAGES.UINT_2, "LT": CONSTANTS.COMPACT_MESSAGES.UINT_2, "RT": CONSTANTS.COMPACT_MESSAGES.UINT_2} # byte 4
            }
        }

    def encode_data(self, data: dict, ID: int) -> bytes:
        """
        Encode the given data dictionary into bytes for transmission.

        Args:
            data (dict): The data to encode.
            ID (int): The identifier for the data.

        Returns:
            bytes: The encoded data.
        """

        bytes_data = b''

        # the first byte is always the ID
        bytes_data += ID.to_bytes(1, byteorder='big')

        # Calculate the number of bits used for current byte
        bitsRemaining = 8
        current_byte = 0

        # Implement encoding logic here
        for key, signal in self.messages[ID]["values"].items():
            
            # store how many bits we need to store for this key
            signal_bits_size = signal

            # default the value to 0
            signal_value = 0

            if key in data:
                signal_value = data[key]

            # repeat in case of 16 bit values or larger
            while(signal_bits_size > 0):
                if bitsRemaining - signal_bits_size < 0:
                    # use the remaining bits in the current byte
                    signal_bits_size -= bitsRemaining
                    current_byte |= (signal_value >> (signal_bits_size)) & ((1 << bitsRemaining) - 1)
                    bytes_data += current_byte.to_bytes(1, byteorder='big')
                    bitsRemaining = 8
                    current_byte = 0
                else:
                    # the signal fits in the current byte
                    current_byte |= (signal_value & ((1 << signal_bits_size) - 1)) << (bitsRemaining - signal_bits_size)
                    bitsRemaining -= signal_bits_size
                    signal_value = signal_value >> signal_bits_size
                    signal_bits_size = 0

                    # reset the byte if full
                    if bitsRemaining == 0:
                        bytes_data += current_byte.to_bytes(1, byteorder='big')
                        bitsRemaining = 8
                        current_byte = 0

        # if there are remaining bits in the current byte, add it
        if bitsRemaining < 8:
            bytes_data += current_byte.to_bytes(1, byteorder='big')


        return bytes_data


    def decode_data(self, data: bytes) -> tuple[dict, int]:
        """
        Decode the received bytes into a data dictionary.

        Args:
            data (bytes): The data to decode.

        Returns:
            dict: The decoded data.
            int: The identifier for the data.
        """

        # the first byte is always the ID
        ID = int.from_bytes(data[0:1], byteorder='big')

        # start decoding from byte index 1
        byte_index = 1
        bitsRemaining = 8

        # Implement decoding logic here
        decoded_data = {}

        # Implement encoding logic here
        for key, signal in self.messages[ID]["values"].items():
            
            # store how many bits we need to store for this key
            signal_bits_size = signal

            # default the value to 0
            signal_value = 0

            # repeat in case of 16 bit values or larger
            while(signal_bits_size > 0):
                if bitsRemaining - signal_bits_size < 0:
                    # use the remaining bits in the current byte
                    signal_bits_size -= bitsRemaining
                    signal_value <<= bitsRemaining
                    signal_value |= int.from_bytes(data[byte_index:byte_index + 1], byteorder='big') & ((1 << bitsRemaining) - 1)
                    byte_index += 1
                    bitsRemaining = 8
                else:
                    # the signal fits in the current byte
                    signal_value <<= signal_bits_size
                    signal_value |= (int.from_bytes(data[byte_index:byte_index + 1], byteorder='big') >> (bitsRemaining - signal_bits_size)) & ((1 << signal_bits_size) - 1)
                    bitsRemaining -= signal_bits_size
                    signal_bits_size = 0

                    # reset the byte if full
                    if bitsRemaining == 0:
                        bitsRemaining = 8
                        byte_index += 1

            decoded_data[key] = signal_value

        return decoded_data, ID


if __name__ == "__main__":
    comm = BaseStationCommunication()

    test_data = { # byte 0
                "ly": CONSTANTS.COMPACT_MESSAGES.UINT_8, # byte 1
                           "ry": CONSTANTS.COMPACT_MESSAGES.UINT_8, # byte 2
                            "A": CONSTANTS.COMPACT_MESSAGES.UINT_2, "B": CONSTANTS.COMPACT_MESSAGES.UINT_2, "X": CONSTANTS.COMPACT_MESSAGES.UINT_2, "Y": CONSTANTS.COMPACT_MESSAGES.UINT_2, # byte 3
                            "LB": CONSTANTS.COMPACT_MESSAGES.UINT_2, "RB": CONSTANTS.COMPACT_MESSAGES.UINT_2, "LT": CONSTANTS.COMPACT_MESSAGES.UINT_2, "RT": CONSTANTS.COMPACT_MESSAGES.UINT_2 # byte 4
            }


    encoded = comm.encode_data(test_data, CONSTANTS.COMPACT_MESSAGES.Xbox_ID)
    print(f"Encoded Data: {encoded}, ID: {hex(CONSTANTS.COMPACT_MESSAGES.Xbox_ID)}")

    decoded, ID = comm.decode_data(encoded)
    print(f"Decoded Data: {decoded}, ID: {hex(ID)}")