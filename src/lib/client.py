import socket
        """Descarga desde el servidor y escribe en `self.filepath` por chunks.

        Flujo:
          1) Abre FileManager en modo escritura (crea/omite si ya existe).
          2) Recibe chunks de `self.conn.rcv`.
          3) Escribe en disco y reporta progreso.
        """
        file_manager = fm.FileManager(self.filepath, "w")

class client:
        chunk = self.conn.rcv()
        written_bytes_count = len(chunk)

        while chunk:
            file_manager.write_chunk(chunk)
            chunk = self.conn.rcv()
            written_bytes_count += len(chunk)

    def upload(self, filepath, filename):
        print("Uploaded")
        )

    def download(self, filepath, filename):
        print("Downloaded")
