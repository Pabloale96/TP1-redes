import socket


class client:
    def __init__(self, addr, port):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addr = addr
        self.port = port

    def close(self):
        self.socket.close()

    def upload(self, filepath, filename):
        print("Uploaded")
        self.socket.sendto("test".encode(), (self.addr, self.port))

    def download(self, filepath, filename):
        print("Downloaded")
