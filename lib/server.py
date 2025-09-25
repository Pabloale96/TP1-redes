from .sockets import Socket 
from .file_manager import FileManager
import threading

# Corregido: El type hint debe ser solo `Socket`
def handle_client(client_socket: Socket):
        print(f"Conexión aceptada desde {client_socket.host}:{client_socket.port}")
        try:
            while True:
                # Recibe datos del cliente
                data = client_socket.recv(1024)
                if not data:
                    print(f"Cliente {client_socket.host}:{client_socket.port} desconectado.")
                    break  # El cliente cerró la conexión

                print(f"Recibido de {client_socket.host}:{client_socket.port}: {data}")
                # Devuelve los mismos datos al cliente (eco)
                client_socket.send(data)
        except Exception as e:
            print(f"Error con el cliente {client_socket.host}:{client_socket.port}: {e}")
        finally:
           client_socket.close()

class Server:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        # Corregido: Se usa la clase directamente y se cambia a TCP (SOCK_STREAM)
        self.socket = Socket(host, port, socket_type=Socket.SOCK_STREAM)
        self.threads = []
        self.clients = []
        self.file = FileManager("prueba.txt","r")
        self.file_copy = FileManager("prueba_copy.txt","w")


    def __del__(self):
        self.close()

    def accept(self):
        client_socket, addr = self.socket.accept()
        self.clients.append(client_socket)

    def close(self):
        self.socket.close()
        for thread in self.threads:
            thread.join()
        for client in self.clients:
            client.join()

    def bind(self):
        self.socket.bind()

    def listen(self, number):
        self.socket.listen(number)


    def upload(self):
        print("upload...")
        size = self.file.get_file_size()
        offset = 0
        while offset < size:
            read_bytes = self.file.read_chunk(offset)
            offset += len(read_bytes)

            self.file_copy.write_chunk(read_bytes)


    def start(self):
        self.bind()
        self.listen(5)
        print(f"Servidor escuchando en {self.host}:{self.port}")
        while True:
            # Acepta nuevas conexiones
            client = self.accept()
            # Inicia un nuevo hilo para manejar al cliente
            client_thread = threading.Thread(target=handle_client, args=(client,))
            client_thread.start()
            self.threads.append(client_thread)