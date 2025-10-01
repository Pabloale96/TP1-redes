from lib.sockets import Socket
import socket

HOST = '127.0.0.1'  # Standard loopback interface address (localhost)
PORT = 8080        # Port to listen on (non-privileged ports are > 1023)

# 1. Crear el socket con el tipo SOCK_DGRAM para UDP
server_socket = Socket(HOST, PORT, socket_type=socket.SOCK_DGRAM)
server_socket.bind()
print(f"Servidor UDP escuchando en {HOST}:{PORT}")

try:
    # 2. Bucle para recibir y responder datagramas
    while True:
        # recvfrom devuelve los datos y la dirección del cliente
        data, address = server_socket.recvfrom(1024)
        message = data.decode()
        print(f"Recibido de {address}: {message}")
        # Enviar el eco de vuelta a la dirección del cliente
        server_socket.sendto(message, address)

except KeyboardInterrupt:
    print("\nCerrando el servidor.")
finally:
    server_socket.close()
