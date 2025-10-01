from .protocolo import Protocol, HEADER_SIZE as PROTO_HEADER_SIZE
from .file_manager import FileManager
import threading
import os
from .logger import logger

def handle_client(client_protocol: Protocol, storage_dir: str):

    try:

        filename = client_protocol.filename
        logger.info(f"[Hilo {threading.get_ident()}] Conexión aceptada de {client_protocol.peer_address}. Recibiendo archivo: {filename}")

        filepath = os.path.join(storage_dir, filename)
        logger.info(f"[Hilo {threading.get_ident()}] Guardando en: {filepath}")
        modo = "r" if client_protocol.operation == 1 else "w"
        file_manager = FileManager(filepath, modo)
        chunk_size = file_manager.getChunkSize()

        header_size = PROTO_HEADER_SIZE
        size = chunk_size + header_size

        if modo == "w":
            while True:

                chunk = client_protocol.recv(size, type=client_protocol.recovery_mode)
                if not chunk:
                    logger.info(f"[Hilo {threading.get_ident()}] Fin de la transferencia para {filename}.")
                    break

                file_manager.write_chunk(chunk)
                logger.vprint(f"[Hilo {threading.get_ident()}] Recibidos {len(chunk)} bytes para {filename}")
        else:
            chunk = file_manager.read_chunk()
            while chunk:
                size = client_protocol.send(chunk, type=client_protocol.recovery_mode)
                logger.vprint(f"[Hilo {threading.get_ident()}] Enviados {size} bytes para {filename}")
                logger.vprint(f"[Hilo {threading.get_ident()}] Enviados {len(chunk)} bytes para {filename}")
                chunk = file_manager.read_chunk()

            logger.info(f"[Hilo {threading.get_ident()}] Transferencia de descarga completada para {filename}.")
    except Exception as e:
        logger.info(f"[Hilo {threading.get_ident()}] Error con el cliente {client_protocol.peer_address}: {e}")
    finally:
        if 'file_manager' in locals():
            file_manager.close()
        client_protocol.close()
        logger.info(f"[Hilo {threading.get_ident()}] Conexión con {client_protocol.peer_address} cerrada.")

class Server:
    def __init__(self, host, port, storage_dir="."):
        self.host = host
        self.port = port
        self.storage_dir = storage_dir

        self.main_protocol = Protocol(self.host, self.port)
        self.threads = []
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir)
            logger.info(f"Directorio de almacenamiento '{self.storage_dir}' creado.")

    def start(self):
        logger.info(f"Servidor principal escuchando en {self.host}:{self.port}")
        while True:

            # 1. Usar el socket principal para aceptar una nueva conexión.
            #    accept() ahora devolverá un nuevo objeto Protocol para el cliente.
            client_protocol = self.main_protocol.accept()
            
            # 2. Si la conexión fue exitosa, iniciar un hilo para manejar al cliente.
            #    El nuevo 'client_protocol' ya está "conectado" y tiene su propio socket.
            if client_protocol:
                client_thread = threading.Thread(target=handle_client, args=(client_protocol, self.storage_dir))
                client_thread.start()
                self.threads.append(client_thread)

    def close(self):
        self.main_protocol.close()
        for thread in self.threads:
            thread.join()