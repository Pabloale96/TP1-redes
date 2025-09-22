import sockets

class Sockets:
    def __init__(self, host, port, socket_type = sockets.SOCK_STREAM):
        self.host = host
        self.port = port
        try:
            self.socket = sockets.socket(sockets.AF_INET, socket_type)
        except Exception as e:
            throw(e)
            
    def bind_socket(self):
        self.socket.bind((self.host, self.port))

    def listen_socket(self, backlog):
        self.socket.listen(backlog)

    def accept_connection(self):
        conn, addr = self.socket.accept()
        return conn, addr

    def connect_socket(self):
        self.socket.connect((self.host, self.port))

    def send_message(self, conn, message):
        conn.sendall(message.encode())

    def receive_message(self, conn, buffer_size):
        message = conn.recv(buffer_size).decode()
        return message

    def close_socket(self):
        self.socket.close()


if __name__ == "__main__":