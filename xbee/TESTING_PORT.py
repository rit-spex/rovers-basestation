import Xbee
import pygame
import CommandCodes
import JoystickFeedback
import socket

HOST = "127.0.0.1"
PORT = 55555

if __name__ == '__main__':
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        conn, addr = s.accept()
        while(True):
            conn.sendall(15)
    # pygame.init()
    # display = JoystickFeedback.Display()
    # xbee = Xbee.XbeeControl()
    # xbee.XbeeCom =
    # done = False
    # while (not done):
    #     pygame.time.delay(100)
    #     xbee.UpdateInfo()
    #     for event in pygame.event.get():
    #         xbee.SendCommand(event)
    #         if(event.type == pygame.QUIT):
    #             done = True
    # xbee.XbeeCom.close()

