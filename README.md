# File Transfer 

Sistema de transferencia de archivos con dos modos de envio: **Stop & Wait (SW)** y **Selective Repeat (SR)**.

---

## 1) Iniciar el servidor

```bash
python3 start-server.py [-v | -q] [-H ADDR] [-p PORT] [-s DIRPATH]
```

**Flags:**

* `-v, --verbose`  Aumenta el detalle de la salida.
* `-q, --quiet`    Reduce la salida.
  *(Mutuamente excluyentes con `-v`.)*
* `-H, --addr`     IP de servicio (por defecto `127.0.0.1`).
* `-p, --port`     Puerto de servicio (por defecto `65432`).
* `-s, --dirpath`  Directorio de almacenamiento.

**Ejemplos:**

```bash
python3 start-server.py -v -H 0.0.0.0 -p 65432 -s ./storage
```

---

## 2) Subir un archivo (cliente)

```bash
python3 upload.py [-v | -q] [-H ADDR] [-p PORT] -s FILEPATH [-n FILENAME] [-r {SW|SR}]
```

**Flags:**

* `-v, --verbose`  Aumenta el detalle de la salida.
* `-q, --quiet`    Reduce la salida.
  *(Mutuamente excluyentes con `-v`.)*
* `-H, --addr`     IP del servidor (por defecto `127.0.0.1`).
* `-p, --port`     Puerto del servidor (por defecto `65432`).
* `-s, --filepath` **Ruta del archivo origen** (obligatoria).
* `-n, --filename` Nombre remoto.
* `-r, --protocol` Protocolo de recuperación: `SW` o `SR` (opcional).

**Ejemplos:**

```bash
python3 upload.py -s ./ejemplo.bin
python3 upload.py -v -H 127.0.0.1 -p 65432 -s ./ejemplo.bin -n copia.bin -r SR
```

---

## 3) Descargar un archivo (cliente)

```bash
python3 download.py [-v | -q] [-H ADDR] [-p PORT] -d DST [-n NAME] [-r {SW|SR}]
```

**Flags:**

* `-v, --verbose`  Aumenta el detalle de la salida.
* `-q, --quiet`    Reduce la salida.
  *(Mutuamente excluyentes con `-v`.)*
* `-H, --addr`     IP del servidor (por defecto `127.0.0.1`).
* `-p, --port`     Puerto del servidor (por defecto `65432`).
* `-d, --dst`      **Ruta de destino** (directorio/archivo) (obligatoria).
* `-n, --name`     Nombre remoto a descargar. 
* `-r, --protocol` Protocolo de recuperación: `SW` o `SR` (opcional).

**Ejemplos:**

```bash
python3 download.py -d ./descargas/
python3 download.py -v -H 127.0.0.1 -p 65432 -d ./descargas/ -n copia.bin -r SW
```

---

