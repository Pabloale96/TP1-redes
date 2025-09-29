from .protocolo import Protocol
from .file_manager import FileManager
import threading
import os

def handle_client_upload(client_protocol: Protocol, storage_dir: str):
    """
    Maneja la subida de un archivo desde un cliente en un hilo dedicado.
    """
    try:
        # El nombre del archivo ya fue recibido por client_protocol.accept()
        filename = client_protocol.filename
        print(f"[Hilo {threading.get_ident()}] Conexión aceptada de {client_protocol.peer_address}. Recibiendo archivo: {filename}")

        filepath = os.path.join(storage_dir, filename)
        file_manager = FileManager(filepath, "w")

        while True:
            # Recibe un chunk de datos del archivo
            chunk = client_protocol.recv(4096) # Usar un buffer más grande
            if not chunk:
                print(f"[Hilo {threading.get_ident()}] Fin de la transferencia para {filename}.")
                break  # El cliente terminó de enviar o cerró la conexión

            file_manager.write_chunk(chunk)
            print(f"[Hilo {threading.get_ident()}] Recibidos {len(chunk)} bytes para {filename}")

    except Exception as e:
        print(f"[Hilo {threading.get_ident()}] Error con el cliente {client_protocol.peer_address}: {e}")
    finally:
        if 'file_manager' in locals():
            file_manager.close()
        client_protocol.close()
        print(f"[Hilo {threading.get_ident()}] Conexión con {client_protocol.peer_address} cerrada.")

class Server:
    def __init__(self, host, port, storage_dir="."):
        self.host = host
        self.port = port
        self.storage_dir = storage_dir
        # El socket principal del servidor que escucha por nuevas conexiones.
        self.main_protocol = Protocol(self.host, self.port)
        self.threads = []
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir)
            print(f"Directorio de almacenamiento '{self.storage_dir}' creado.")

    def start(self):
        """
        Bucle principal del servidor. Escucha por conexiones entrantes en el socket principal
        y crea un nuevo hilo con un nuevo socket para cada cliente.
        """
        print(f"Servidor principal escuchando en {self.host}:{self.port}")
        while True:
            # 1. Usar el socket principal para aceptar una nueva conexión.
            #    accept() ahora devolverá un nuevo objeto Protocol para el cliente.
            client_protocol = self.main_protocol.accept()
            
            if client_protocol:
                # 2. Si la conexión fue exitosa, iniciar un hilo para manejar al cliente.
                #    El nuevo 'client_protocol' ya está "conectado" y tiene su propio socket.
                client_thread = threading.Thread(target=handle_client_upload, args=(client_protocol, self.storage_dir))
                client_thread.start()
                self.threads.append(client_thread)

    def close(self):
        self.main_protocol.close()
        for thread in self.threads:
            thread.join()