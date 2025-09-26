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
        """Cierra la conexión del protocolo."""
        self.conn.close()

    def upload(self):
        """Sube el archivo local en chunks al servidor vía `self.conn.send`.

        Flujo:
          1) Abre FileManager en modo lectura.
          2) Lee y envía chunks sucesivos.
          3) Reporta progreso por stdout según flags.
        """

        self.__print_info(string_verbose="Validating filepath...")
        __validate_filepath(self.filepath)
        self.__print_info(string_verbose="filepath validated")

        self.__print_info(string_verbose="Creating file_manager...")
        file_manager = fm.FileManager(self.filepath, "r")
        self.__print_info(string_verbose="File_manager has been created")

        self.__print_info(string_verbose="Reading first chunk...")
        chunk = file_manager.read_chunk()

        read_bytes_count = len(chunk)
        file_size = file_manager.get_file_size()
        percentage = read_bytes_count / file_size * 100

        while chunk:
            self.conn.send(chunk)
            self.__print_info(string_normal=f"Percentage uploaded: {percentage}%")
            self.__print_info(string_verbose=f"Bytes sent: {read_bytes_count}/{file_size}[B]")

            chunk = file_manager.read_chunk()
            read_bytes_count += len(chunk)
            percentage = read_bytes_count / file_size * 100

        self.__print_info(
            string_normal=f"{read_bytes_count}[B] have been uploaded to {self.filename} in the server"
        )

    def download(self):
        """Descarga desde el servidor y escribe en `self.filepath` por chunks.

        Flujo:
          1) Abre FileManager en modo escritura (crea/omite si ya existe).
          2) Recibe chunks de `self.conn.rcv`.
          3) Escribe en disco y reporta progreso.
        """
        self.__print_info(string_verbose="Creating file_manager...")
        file_manager = fm.FileManager(self.filepath, "w")
        self.__print_info(string_verbose="File_manager has been created")
        self.__print_info(string_verbose=f"File {self.filepath} has been created")

        self.__print_info(string_verbose="Receiving first chunk...")
        chunk = self.conn.rcv()
        written_bytes_count = len(chunk)

        while chunk:
            file_manager.write_chunk(chunk)
            self.__print_info(string_verbose=f"Bytes written: {written_bytes_count}[B]")
            chunk = self.conn.rcv()
            written_bytes_count += len(chunk)

        self.__print_info(
            string_normal=f"{written_bytes_count}[B] have been written to {self.filepath}"
        )

    def __print_info(self, string_normal=None, string_verbose=None):
        """Imprime mensajes según flags `verbose`/`quiet`."""
        if self.verbose:
            print(string_verbose)
        elif not self.quiet:
            print(string_normal)


def __validate_port(port):
    """Valida y normaliza el puerto (1..65535)."""
    try:
        p = int(port)
    except (TypeError, ValueError):
        raise ValueError(f"Puerto inválido (no numérico): {port!r}")
    if not (1 <= p <= 65535):
        raise ValueError(f"Puerto fuera de rango [1..65535]: {p}")
    return p


def __validate_addr(addr):
    """Valida dirección IP literal (v4/v6). No resuelve hostnames.

    Raises:
        ValueError: si está vacía/no es str o no es IP literal válida.
    """
    if not addr or not isinstance(addr, str):
        raise ValueError("Dirección vacía o no es texto.")
    try:
        ipaddress.ip_address(addr)
        return addr
    except ValueError:
        pass
    # No se intenta DNS aquí; se considera inválido si no es IP literal
    raise ValueError(f"Dirección no es IP literal válida: {addr!r}")


def __is_boolean(boolean):
    """Verifica tipo bool estricto para flags."""
    if not isinstance(boolean, bool):
        return False
    return True

def __is_string(filepath):
    """Verifica tipo string"""
    if not isinstance(filepath, str):
        return False
    return True

def __validate_filepath(filepath):
    """Exige que la ruta exista (para lectura en upload)."""
    if not os.path.exists(filepath):
        raise ValueError("File does not exist")

def __validate_filename(filename):
    """Exige nombre de archivo no vacío."""
    if not filename:
        raise ValueError("Empty Filename")
    if __is_string(filename):
        return filename
    else:
        raise ValueError("filename must be a string")

def __validate_verbose_and_quiet(verbose, quiet):
    """Valida flags de salida (mutuamente excluyentes)."""
    if not __is_boolean(verbose):
        raise TypeError("verbose must be a boolean")

    if not __is_boolean(quiet):
        raise TypeError("quiet must be a boolean")

    if verbose and quiet:
        raise ValueError("You can't have both verbose and quiet")
    return verbose, quiet
