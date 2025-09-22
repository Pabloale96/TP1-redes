import socket

HOST = '127.0.0.1'  # La dirección IP o hostname del servidor
PORT = 8080        # El puerto que usa el servidor

print("Cliente TCP. Escribe un mensaje y presiona Enter para enviar.")
print("Presiona Ctrl+C para salir.")

try:
    # Usamos 'with' para asegurar que el socket se cierre automáticamente
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        client_socket.connect((HOST, PORT))
        while True:
            message = input("> ")
            client_socket.sendall(message.encode())
            data = client_socket.recv(1024)
            print(f"Respuesta del servidor: {data.decode()}")
except KeyboardInterrupt:
    print("\nCerrando cliente.")
