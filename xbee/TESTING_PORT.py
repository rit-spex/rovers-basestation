import socket

HOST = "127.0.0.1"
PORT = 5005

if __name__ == '__main__':
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind((HOST, PORT))
        while(True):
            data, addr = s.recvfrom(1024) # buffer size is 1024 bytes
            print("received message: %s" % data)


