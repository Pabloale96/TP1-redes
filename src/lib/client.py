import socket


class client:
    def __init__(self, addr, port):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def close(self):
        self.socket.close()

    def upload(self, filepath, filename):
        print("Uploaded")

    def download(self, filepath, filename):
        print("Downloaded")
