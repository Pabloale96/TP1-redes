import os
import threading

from .file_manager import FileManager
from .logger import logger
from .protocolo import HEADER_SIZE as PROTO_HEADER_SIZE
from .protocolo import Protocol

CHUNK_SIZE = 1024 * 4


def handle_client(client_protocol: Protocol, storage_dir: str):

    try:

        filename = client_protocol.filename
        logger.info(
            f"[Thread {threading.get_ident()}] Connection accepted from {client_protocol.peer_address}. Receiving file: {filename}"
        )

        filepath = os.path.join(storage_dir, filename)
        logger.info(f"[Thread {threading.get_ident()}] Saving in: {filepath}")
        modo = "r" if client_protocol.operation == 1 else "w"
        file_manager = FileManager(filepath, modo, chunk_size=CHUNK_SIZE)
        chunk_size = file_manager.getChunkSize()

        header_size = PROTO_HEADER_SIZE
        size = chunk_size

        if modo == "w":
            while True:

                chunk = client_protocol.recv(size, type=client_protocol.recovery_mode)
                if not chunk:
                    logger.info(
                        f"[Thread {threading.get_ident()}] End of transmission for {filename}."
                    )
                    break

                file_manager.write_chunk(chunk)
                logger.vprint(
                    f"[Thread {threading.get_ident()}] Receiving {len(chunk)} bytes for {filename}"
                )
        else:
            chunk = file_manager.read_chunk()
            while chunk:
                size = client_protocol.send(chunk, type=client_protocol.recovery_mode)
                logger.vprint(
                    f"[Thread {threading.get_ident()}] Received {size} bytes for {filename}"
                )
                logger.vprint(
                    f"[Thread {threading.get_ident()}] Received {len(chunk)} bytes for {filename}"
                )
                chunk = file_manager.read_chunk()

            logger.info(
                f"[Thread {threading.get_ident()}] Download completed for {filename}."
            )
    except Exception as e:
        logger.info(
            f"[Thread {threading.get_ident()}] Error with client {client_protocol.peer_address}: {e}"
        )
    finally:
        if "file_manager" in locals():
            file_manager.close()
        client_protocol.close()
        logger.info(
            f"[Thread {threading.get_ident()}] Connection with {client_protocol.peer_address} closed."
        )


class Server:
    def __init__(self, host, port, storage_dir="."):
        self.host = host
        self.port = port
        self.storage_dir = storage_dir

        self.main_protocol = Protocol(self.host, self.port)
        self.threads = []
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir)
            logger.info(f"Storage directory:'{self.storage_dir}' created.")

    def start(self):
        logger.info(f"Main thread from server listening on {self.host}:{self.port}")
        while True:
            client_protocol = self.main_protocol.accept()

            if client_protocol:
                client_thread = threading.Thread(
                    target=handle_client, args=(client_protocol, self.storage_dir)
                )
                client_thread.start()
                self.threads.append(client_thread)

    def close(self):
        self.main_protocol.close()
        for thread in self.threads:
            thread.join()
