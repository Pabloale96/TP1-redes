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
