import ipaddress
import os

from .file_manager import FileManager
from .logger import logger
from .protocolo import HEADER_SIZE, Protocol


class Client:

    def __init__(self, addr, port, filepath, filename, verbose, quiet, fileop=0, protocolo=Protocol.STOP_AND_WAIT):
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

        self.addr = _validate_addr(addr)
        self.port = _validate_port(port)
        self.protocolo = _parse_protocol_arg(protocolo)

        if _is_string(filepath):
            self.filepath = filepath
        else:
            raise TypeError("filepath must be a string")

        self.filename = _validate_filename(filename)
        self.verbose, self.quiet = _validate_verbose_and_quiet(verbose, quiet)

        logger.set_verbose(self.verbose)
        logger.set_quiet(self.quiet)

        self.conn = Protocol(addr, port, client=True, recovery_mode=self.protocolo)

    def close(self):
        self.conn.close()

    def upload(self):
        self._print_info(string_verbose="Validating filepath...")
        _validate_filepath(self.filepath)
        self._print_info(string_verbose="filepath validated")

        
        # 1. Crear una instancia de FileManager en modo lectura
        #    (esto lanzará excepción si el archivo no existe o no se puede leer)
        self._print_info(string_verbose="Creating file_manager...")
        file_manager = FileManager(self.filepath, "r")
        self._print_info(string_verbose="File_manager has been created")

        # 2. Conectar al servidor
        self._print_info(string_verbose="Connecting with server...")
        logger.vprint(self.addr, self.port, self.filename)
        if not self.conn.connect((self.addr, self.port), self.filename):
            self._print_info(string_normal="Could not connect to the server.", string_verbose="Connection failed.")
            return
        
        # 3. Enviar el primer chunk y luego sucesivos
        self._print_info(string_verbose="Connected with server")
        self._print_info(string_verbose="Reading first chunk...")
        chunk = file_manager.read_chunk()

        read_bytes_count = len(chunk)
        file_size = file_manager.get_file_size()
        percentage = read_bytes_count / file_size * 100

        while chunk:
            self.conn.send(chunk, type=self.protocolo)
            self._print_info(string_normal=f"Percentage uploaded: {percentage}%")
            self._print_info(string_verbose=f"Bytes sent: {read_bytes_count}/{file_size}[B]")

            chunk = file_manager.read_chunk()
            read_bytes_count += len(chunk)
            percentage = read_bytes_count / file_size * 100

        self._print_info(
            string_normal=f"{read_bytes_count}[B] have been uploaded to {self.filename} in the server"
        )

    def download(self):
        
        # 1. Validar que la ruta de destino exista (no el archivo, que se creará)
        self._print_info(string_verbose="Creating file_manager...")
        file_manager = FileManager(os.path.join(self.filepath, self.filename), "w")
        self._print_info(string_verbose="File_manager has been created")

        self._print_info(string_verbose="Connecting with server...")
        logger.vprint(self.addr, self.port, self.filename)

        # 2. Conectar al servidor con fileop=1 para descarga
        if not self.conn.connect((self.addr, self.port), self.filename, fileop=1):
            self._print_info(string_normal="Could not connect to the server.", string_verbose="Connection failed.")
            return

        self._print_info(string_verbose="Connected with server. Starting download...")

        received_bytes_count = 0
        # No podemos saber el tamaño del archivo de antemano en el download,
        # así que no mostraremos porcentaje, solo bytes recibidos.
        chunk_size = file_manager.getChunkSize()
        size = chunk_size + HEADER_SIZE
        while True:
            chunk = self.conn.recv(size, type=self.protocolo)
            if not chunk:
                break

            file_manager.write_chunk(chunk)
            received_bytes_count += len(chunk)

            self._print_info(
                string_normal=f"Received {received_bytes_count} bytes...",
                string_verbose=f"Received {received_bytes_count} bytes for {self.filename}"
            )

        self._print_info(
            string_normal=f"Total {received_bytes_count}[B] have been downloaded to {os.path.join(self.filepath, self.filename)}"
        )


    def _print_info(self, string_normal=None, string_verbose=None):
        if self.verbose:
            if string_verbose is not None:
                logger.vprint(string_verbose)
        elif not self.quiet:
            if string_normal is not None:
                logger.info(string_normal)


def _validate_port(port):
    try:
        p = int(port)
    except (TypeError, ValueError):
        raise ValueError(f"Puerto inválido (no numérico): {port!r}")
    if not (1 <= p <= 65535):
        raise ValueError(f"Puerto fuera de rango [1..65535]: {p}")
    return p


def _validate_addr(addr):
    if not addr or not isinstance(addr, str):
        raise ValueError("Dirección vacía o no es texto.")
    try:
        ipaddress.ip_address(addr)
        return addr
    except ValueError:
        pass
    raise ValueError(f"Dirección no es IP literal válida: {addr!r}")


def _is_boolean(boolean):
    if not isinstance(boolean, bool):
        return False
    return True


def _is_string(filepath):
    if not isinstance(filepath, str):
        return False
    return True


def _validate_filepath(filepath):
    if not os.path.exists(filepath):
        raise ValueError("File does not exist")


def _validate_filename(filename):
    if not filename:
        raise ValueError("Empty Filename")
    if _is_string(filename):
        return filename
    else:
        raise ValueError("filename must be a string")


def _validate_verbose_and_quiet(verbose, quiet):
    if not _is_boolean(verbose):
        raise TypeError("verbose must be a boolean")

    if not _is_boolean(quiet):
        raise TypeError("quiet must be a boolean")

    if verbose and quiet:
        raise ValueError("You can't have both verbose and quiet")
    return verbose, quiet

def _parse_protocol_arg(protocolo):
    if protocolo is None or protocolo == "":
        return Protocol.STOP_AND_WAIT

    if isinstance(protocolo, int):
        if protocolo in (Protocol.STOP_AND_WAIT, Protocol.SELECTIVE_REPEAT):
            return protocolo
        raise ValueError(f"Invalid protocol numeric value: {protocolo}")

    # revisamos el protocolo
    if isinstance(protocolo, str):
        p = protocolo.strip().upper()
        if p in ("SW", "STOP_AND_WAIT", "STOP-AND-WAIT"):
            return Protocol.STOP_AND_WAIT
        if p in ("SR", "SELECTIVE_REPEAT", "SELECTIVE-REPEAT"):
            return Protocol.SELECTIVE_REPEAT

    raise ValueError(f"Invalid protocol argument: {protocolo!r}")
