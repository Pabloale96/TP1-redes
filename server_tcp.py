from sockets import Socket
import threading

HOST = '127.0.0.1'  # Standard loopback interface address (localhost)
PORT = 8080        # Port to listen on

def handle_client(client_socket: Socket):
    """Maneja la comunicación con un único cliente TCP."""
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

server = Socket(HOST, PORT)
server.bind()
server.listen(5)
print(f"Servidor TCP escuchando en {HOST}:{PORT}")

while True:
    # Acepta nuevas conexiones
    client = server.accept()
    # Inicia un nuevo hilo para manejar al cliente
    client_thread = threading.Thread(target=handle_client, args=(client,))
    client_thread.start()
