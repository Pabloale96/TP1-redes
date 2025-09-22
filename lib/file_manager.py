import os

class FileManager:
    """
    Clase que encapsula la gestión de archivos para operaciones de transferencia (UPLOAD/DOWNLOAD).
    Permite abrir, leer y escribir archivos en modo binario, utilizando chunks de tamaño fijo.
    """
    def __init__(self, path, mode, chunk_size=400):
        """
        Inicializa el administrador de archivos.

        :param path: Ruta del archivo a manejar. :param mode: Modo de apertura ('r' para lectura, 'w' para escritura, etc.).
                     El modo se fuerza siempre a binario añadiendo 'b'.
        :param chunk_size: Cantidad de bytes a leer/escribir por operación.
        :raises FileNotFoundError: Si el archivo no existe en modo lectura.
        :raises PermissionError: Si no hay permisos para acceder al archivo.
        """
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

    def read_chunk(self, offset = None) -> bytes:
        """
        Lee un bloque del archivo.

        :param offset: Posición en bytes en el archivo desde donde leer. Si es None, lee desde la posición actual.
        :return: Bytes leídos. Puede ser menor al tamaño solicitado si se alcanza EOF.
                 Devuelve b'' si ya no hay más datos que leer.

        Nota: el puntero del archivo queda desplazado al final de los datos leídos.
        """
        if offset is not None:
            if offset < 0:
                raise ValueError("El offset no puede ser negativo")
            if offset > self.file_size:
                raise ValueError(f"El offset {offset} está fuera del rango del archivo ({self.file_size} bytes).")
            self.file.seek(offset)
        return self.file.read(self.chunk_size)

    def write_chunk(self, data, offset):
        """
        Escribe un bloque de bytes en el archivo.

        :param data: Bytes a escribir.
        :param offset: Posición en bytes el archivo donde escribir.
                       Si es None, escribe en la posición actual del puntero.
        :raises ValueError: Si el archivo fue abierto en modo lectura.

        Nota: el puntero del archivo queda desplazado al final de los datos escritos.
        Esto afecta la siguiente operación de escritura sin offset.
        """
        if self.file.writable() is False:
            raise ValueError(f"El archivo '{self.path}' no fue abierto en modo escritura.")

        if offset is not None:
            self.file.seek(offset)
        self.file.write(data)
        self.file.flush()

    def delete(self):
        """Cierra y elimina el archivo asociado."""
        self.close()
        try:
            os.remove(self.path)
        except FileNotFoundError:
            raise FileNotFoundError(f"El archivo '{self.path}' no existe.")
        except PermissionError:
            raise PermissionError(f"No hay permisos para eliminar el archivo '{self.path}'.")

    def close(self):
        """Cierra el archivo si está abierto."""
        if not self.file.closed:
            self.file.close()

    def __del__(self):
        """Se asegura de cerrar el archivo al destruir el objeto."""
        self.close()

    def __enter__(self):
        """
        Permite usar FileManager en un bloque 'with'.

        :return: La instancia actual de FileManager.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Cierra el archivo automáticamente al salir del bloque 'with'.
        """
        self.close()
