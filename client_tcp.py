from lib.sockets import Socket

HOST = '127.0.0.1'  # La dirección IP o hostname del servidor
PORT = 8080        # El puerto que usa el servidor

print("Cliente TCP. Escribe un mensaje y presiona Enter para enviar.")
print("Presiona Ctrl+C para salir.")

try:
    # 1. Crear una instancia de tu clase Socket
    client_socket = Socket(HOST, PORT)
    # 2. Conectar al servidor
    client_socket.connect()
    while True:
        message = input("> ")
        # 3. Enviar mensaje (tu clase ya lo codifica)
        client_socket.send(message)
        # 4. Recibir respuesta (tu clase ya la decodifica)
        data = client_socket.recv(1024)
        print(f"Respuesta del servidor: {data}")
except KeyboardInterrupt:
    print("\nCerrando cliente.")
