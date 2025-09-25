import sockets 


class Server:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = sockets.Socket(host, port)

    def start(self):
        self.socket.bind()
        self.socket.listen(5)
        print(f"Servidor escuchando en {self.host}:{self.port}")
        while True:
            client_socket, addr = self.socket.accept()
            print(f"Conexión aceptada de {addr}")
            # Aquí puedes agregar la lógica para manejar la conexión del cliente
            # Por ahora, simplemente cerramos la conexión
            client_socket.close()