import os

class FileManager:
    def __init__(self, path, mode, chunk_size=400):
        self.path = path
        self.chunk_size = chunk_size
        try:
            self.file = open(path, mode + "b")
        except FileNotFoundError:
            raise FileNotFoundError(f"El archivo '{path}' no existe.")
        except PermissionError:
            raise PermissionError(f"No hay permisos para acceder al archivo '{path}'.")
        self.file.seek(0, 2)
        self.file_size = self.file.tell()
        self.file.seek(0)

    def getChunkSize(self):
        return self.chunk_size

    def read_chunk(self, offset = None) -> bytes:
        if offset is not None:
            if offset < 0:
                raise ValueError("El offset no puede ser negativo")
            if offset > self.file_size:
                raise ValueError(f"El offset {offset} está fuera del rango del archivo ({self.file_size} bytes).")
            self.file.seek(offset)
        return self.file.read(self.chunk_size)

    def write_chunk(self, data, offset=None):
        if self.file.writable() is False:
            raise ValueError(f"El archivo '{self.path}' no fue abierto en modo escritura.")

        if offset is not None:
            self.file.seek(offset)
        self.file.write(data)
        self.file.flush()

    def get_file_size(self):
        return self.file_size

    def delete(self):
        self.close()
        try:
            os.remove(self.path)
        except FileNotFoundError:
            raise FileNotFoundError(f"El archivo '{self.path}' no existe.")
        except PermissionError:
            raise PermissionError(f"No hay permisos para eliminar el archivo '{self.path}'.")

    def close(self):
        if not self.file.closed:
            self.file.close()

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
