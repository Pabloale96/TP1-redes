import socket

HOST = '127.0.0.1'  # The server's hostname or IP address
PORT = 8080        # The port used by the server

try:
    # 1. Crear el socket con el tipo SOCK_DGRAM para UDP
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
        while True:
            message = input("Ingrese el mensaje a enviar (o Ctrl+C para salir): ")
            # 2. Enviar el mensaje al servidor usando sendto
            client_socket.sendto(message.encode(), (HOST, PORT))

            # 3. Recibir la respuesta del servidor
            data, server_address = client_socket.recvfrom(1024)
            print(f"Recibido del servidor {server_address}: {data.decode()}")
except KeyboardInterrupt:
    print("\nCliente interrumpido por el usuario.")
except Exception as e:
    print(f"Ha ocurrido un error: {e}")
