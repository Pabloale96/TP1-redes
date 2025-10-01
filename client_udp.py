from lib.sockets import Socket

HOST = '127.0.0.1'  # The server's hostname or IP address
PORT = 8080        # The port used by the server

try:
    # 1. Crear una instancia de tu clase Socket para UDP
    client_socket = Socket(HOST, PORT, socket_type=Socket.SOCK_DGRAM)
    while True:
        message = input("Ingrese el mensaje a enviar (o Ctrl+C para salir): ")
        # 2. Enviar el mensaje al servidor usando el método de tu clase
        #    (la codificación a bytes se hace dentro del método)
        client_socket.sendto(message, (HOST, PORT))

        # 3. Recibir la respuesta del servidor
        data, server_address = client_socket.recvfrom(1024)
        print(f"Recibido del servidor {server_address}: {data.decode()}")
except KeyboardInterrupt:
    print("\nCliente interrumpido por el usuario.")
except Exception as e:
    print(f"Ha ocurrido un error: {e}")
