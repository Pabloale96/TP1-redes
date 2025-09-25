import socket

class Socket:
    SOCK_STREAM = socket.SOCK_STREAM
    SOCK_DGRAM = socket.SOCK_DGRAM

    def __init__(self, host, port, socket_type = socket.SOCK_STREAM):
        self.host = host
        self.port = port
        self.socket_type = socket_type
        self.socket = None
        try:
            self.socket = socket.socket(socket.AF_INET, socket_type)
        except Exception as e:
            raise e
    
    def bind(self):
        self.socket.bind((self.host, self.port))

    def listen(self, backlog):
        self.socket.listen(backlog)

    def accept(self):
        conn, addr = self.socket.accept()
        # Crea una nueva instancia de Sockets para la conexión del cliente
        host, port = addr
        client_socket = Sockets(host, port, conn.type)
        client_socket.socket = conn
        return client_socket

    def connect(self):
        self.socket.connect((self.host, self.port))

    def send(self, message):
        if not self.socket:
            raise ConnectionError("Socket no está inicializado o está cerrado.")
        self.socket.sendall(message.encode())

    def recv(self, buffer_size):
        if not self.socket:
            raise ConnectionError("Socket no está inicializado o está cerrado.")
        message = self.socket.recv(buffer_size).decode()
        return message

    def sendto(self, message, address):
        if not self.socket:
            raise ConnectionError("Socket no está inicializado o está cerrado.")
        self.socket.sendto(message.encode(), address)

    def recvfrom(self, buffer_size):
        if not self.socket:
            raise ConnectionError("Socket no está inicializado o está cerrado.")
        return self.socket.recvfrom(buffer_size)

    def close(self):
        if self.socket:
            try:
                # Avisa al otro extremo que no se enviarán más datos
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                # El socket podría no estar conectado, lo cual es normal
                pass
            self.socket.close()

    def __del__(self):
        self.close()