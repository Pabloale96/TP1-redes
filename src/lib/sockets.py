import socket

from .logger import logger


class Socket:
    SOCK_STREAM = socket.SOCK_STREAM
    SOCK_DGRAM = socket.SOCK_DGRAM

    def __init__(self, host, port):
        self.addr = (host, port)
        self.socket = None
        try:
            self.socket = socket.socket(socket.AF_INET, self.SOCK_DGRAM)
        except Exception as e:
            raise e

    def bind(self):
        self.socket.bind(self.addr)
        logger.vprint(f"UDP server listening on {self.addr}")

    def sendto(self, message, addr=None):
        if addr is None:
            addr = self.addr
        # logger.vprint("send message:", message, " to address: ", addr)
        if not self.socket:
            raise ConnectionError("Socket is not initialized or is closed.")
        if isinstance(message, str):
            message = message.encode()
        self.socket.sendto(message, addr)

    def recvfrom(self, buffer_size):
        if not self.socket:
            raise ConnectionError("Socket is not initialized or is closed.")
        data, address = self.socket.recvfrom(buffer_size)
        return data, address

    def close(self):
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.socket.close()

    def __del__(self):
        self.close()
