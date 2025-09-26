import socket
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

