"""Cliente simple para transferir archivos sobre TCP usando un 'protocolo' externo.
Incluye validaciones básicas de dirección, puerto, rutas y flags de salida.
"""

import ipaddress
import file_manager as fm
import os

class client:
    """Cliente de transferencia de archivos.

    Gestiona conexión (vía `protocolo`), lectura/escritura por chunks con `FileManager`,
    y mensajes de estado controlados por `verbose`/`quiet`.
    """

    def __init__(self, addr, port, filepath, filename, verbose, quiet):
        """Inicializa el cliente y crea la conexión del protocolo.

        Args:
            addr (str): Dirección del servidor (IP literal; no resuelve hostname).
            port (int|str): Puerto del servidor (1..65535).
            filepath (str): Ruta local del archivo (lectura en upload, escritura en download).
            filename (str): Nombre remoto/destino en el servidor.
            verbose (bool): Modo detallado.
            quiet (bool): Silencioso (anula salida normal).

        Raises:
            ValueError/TypeError: Si cualquier validación falla.
        """
        # self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addr = __validate_addr(addr)
        self.port = __validate_port(port)

        if __is_string(filepath):
            self.filepath = filepath
        else:
            raise TypeError("filepath must be a string")

        self.filename = __validate_filename(filename)
        self.verbose, self.quiet = __validate_verbose_and_quiet(verbose, quiet)
        # Instancia de la capa de protocolo (se asume existencia de `protocolo`)
        self.conn = protocol.Protocol(addr, port, filename, verbose, quiet)

    def close(self):
        self.socket.close()

    def upload(self, filepath, filename):
        print("Uploaded")
        self.socket.sendto("test".encode(), (self.addr, self.port))

    def download(self, filepath, filename):
        print("Downloaded")
