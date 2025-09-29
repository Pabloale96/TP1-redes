# Programa para generar un archivo de 3MB llamado 'archivo.txt' con datos aleatorios
import os



def generar_archivo(nombre, tamano_bytes):
	linea = b"Este es un contenido adicional al final del archivo.\n"
	with open(nombre, 'wb') as f:
		bytes_escritos = 0
		while bytes_escritos + len(linea) <= tamano_bytes:
			f.write(linea)
			bytes_escritos += len(linea)
		# Si falta completar hasta el tamaño exacto, escribir solo los bytes necesarios
		if bytes_escritos < tamano_bytes:
			f.write(linea[:tamano_bytes - bytes_escritos])

if __name__ == "__main__":
	TAMANO_MB = 3
	TAMANO_BYTES = TAMANO_MB * 1024 * 1024
	generar_archivo("archivo2.txt", TAMANO_BYTES)
