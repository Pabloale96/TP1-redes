import socket
SIZE = 5120


class server:

    def __init__(self, addr, port):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addr = addr
        self.port = port

    def start(self):
        self.socket.bind(self.addr, self.port)
        while True:
            data, addr = self.socket.recvfrom(SIZE)
            print(f"Recibido de {addr}: {data.decode()}")
