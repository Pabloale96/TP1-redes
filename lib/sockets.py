import socket

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
        print(f"Servidor UDP escuchando en {self.addr}")

    def sendto(self, message, addr=None):
        if addr is None:
            addr = self.addr
        print("send message:", message, " to address: ", addr)
        if not self.socket:
            raise ConnectionError("Socket no está inicializado o está cerrado.")
        if isinstance(message, str):
            message = message.encode()
        self.socket.sendto(message, addr)

    def recvfrom(self, buffer_size):
        if not self.socket:
            raise ConnectionError("Socket no está inicializado o está cerrado.")
        data, address = self.socket.recvfrom(buffer_size)
        return data, address


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