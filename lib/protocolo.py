import time
import struct
import random
from lib.sockets import Socket

# --- Definición de Flags para el Encabezado del Protocolo ---
FLAG_SYN = 0b00000001  # Iniciar conexión
FLAG_ACK = 0b00000010  # Acuse de recibo
FLAG_FIN = 0b00000100  # Finalizar conexión
FLAG_PSH = 0b00001000  # Empujar datos (indica que el paquete tiene payload)
FLAG_FNAME = 0b00010000 # Indica que el payload es un nombre de archivo
FLAG_OP = 0b00100000

# Formato del encabezado:
# ! -> Network Byte Order (big-endian)
# I -> Unsigned Integer (4 bytes) para número de secuencia
# I -> Unsigned Integer (4 bytes) para número de ack
# B -> Unsigned Char (1 byte) para flags
# H -> Unsigned Short (2 bytes) para checksum (no implementado, pero reservado)
HEADER_FORMAT = '!IIBH'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

class Protocol:
    """
    Implementa un protocolo de transferencia de datos confiable sobre UDP.
    Simula un handshake, números de secuencia, ACKs y retransmisiones (Stop-and-Wait).
    """

    def __init__(self, local_host='127.0.0.1', local_port=0, fileop = 0, client=False):
        """
        Inicializa el socket UDP.
        :param local_host: Dirección IP local.
        :param local_port: Puerto local. Si es 0, el SO elegirá uno efímero.
        """
        # Inicializar atributos de estado primero para un manejo de errores seguro en __del__
        self.is_connected = False
        self.socket = None
        self.peer_address = None
        self.seq_num = random.randint(0, 1000)
        self.ack_num = 0
        self.filename = None
        self.retransmission_timeout = 2 
        self.fileop = fileop
        self.socket = Socket(local_host, local_port)
        if not client:
            self.socket.bind()

    def __del__(self):
        self.close()

    def _pack_header(self, seq, ack, flags):
        """Empaqueta el encabezado del protocolo."""
        return struct.pack(HEADER_FORMAT, seq, ack, flags, 0)

    def _unpack_header(self, header_bytes):
        """Desempaqueta el encabezado del protocolo."""
        return struct.unpack(HEADER_FORMAT, header_bytes)

    def _send_packet(self, flags, data=b''):
        """Construye y envía un paquete (encabezado + datos)."""
        header = self._pack_header(self.seq_num, self.ack_num, flags)
        print(f"-> Enviando [SEQ={self.seq_num}, ACK={self.ack_num}, Flags={bin(flags)}] a {self.peer_address}")
        self.socket.sendto(header + data, self.peer_address)

    def _receive_packet(self, timeout):
        """Espera y recibe un paquete, con un timeout."""
        self.socket.socket.settimeout(timeout)
        try:
            packet, address = self.socket.recvfrom(1024 + HEADER_SIZE)
            header = self._unpack_header(packet[:HEADER_SIZE])
            data = packet[HEADER_SIZE:]
            print(f"<- Recibido [SEQ={header[0]}, ACK={header[1]}, Flags={bin(header[2])}] de {address}")
            return header, data, address
        except Exception: 
            return None, None, None

    def connect(self, server_address, filename: str):
        """
        Realiza un handshake de 3 vías para establecer una "conexión".
        Luego, envía el nombre del archivo.
        """
        self.peer_address = server_address
        self.filename = filename
        print(f"[CLIENT] Iniciando handshake con {server_address}")
        # 1. Enviar SYN
        self._send_packet(FLAG_SYN)
        self.seq_num += 1

        # 2. Esperar SYN-ACK
        header, _, new_address = self._receive_packet(self.retransmission_timeout)
        print(f"[CLIENT] Recibido SYN-ACK: {header} desde {new_address}")
        if not header or not (header[2] & FLAG_SYN and header[2] & FLAG_ACK):
            print("Error: Handshake fallido. No se recibió SYN-ACK.")
            return False

        # ¡Importante! Actualizar la dirección del par a la que el servidor usará para la conexión.
        self.peer_address = new_address
        print(f"[CLIENT] Handshake redirigido por el servidor a {self.peer_address}")
        self.ack_num = header[0] + 1  # El ACK es el SEQ recibido + 1

        # 3. Enviar ACK
        self._send_packet(FLAG_ACK)
        print(f"[CLIENT] ACK enviado, esperando para enviar nombre de archivo...")

        # 4. Enviar el nombre del archivo de forma confiable
        print(f"[CLIENT] Enviando nombre de archivo: {self.filename}")
        self._send_reliable_packet(FLAG_FNAME | FLAG_PSH | FLAG_ACK | FLAG_OP, self.filename.encode('utf-8'))

        print(f"[CLIENT] Conexión establecida con {self.peer_address}")
        self.is_connected = True
        return True

    def accept(self):
        """
        (Lado del servidor) Acepta una conexión entrante, recibe el nombre del archivo
        y devuelve una nueva instancia de Protocol para manejar a ese cliente.
        """
        print("[SERVER] Esperando por un SYN...")
        # 1. Esperar SYN (bloqueante, descarta paquetes inválidos)
        while True:
            header, _, address = self._receive_packet(timeout=None)
            print(f"[SERVER] Recibido: {header} de {address}")
            if header and (header[2] & FLAG_SYN):
                break
            print("[SERVER] Paquete inesperado recibido o error, se esperaba SYN. Descartando y esperando de nuevo.")

        # Crear un nuevo protocolo para este cliente específico en un puerto efímero (puerto 0)
        client_protocol = Protocol(address[0], address[1], client=True)
        client_protocol.peer_address = address
        client_protocol.ack_num = header[0] + 1

        # 2. Enviar SYN-ACK
        client_protocol._send_packet(FLAG_SYN | FLAG_ACK)
        client_protocol.seq_num += 1
        print(f"[SERVER] SYN-ACK enviado a {address}")

        # 3. Esperar ACK final
        header, _, _ = client_protocol._receive_packet(self.retransmission_timeout)
        print(f"[SERVER] Recibido ACK final: {header}")
        if not header or not (header[2] & FLAG_ACK):
            print("[SERVER] Error: Handshake fallido. No se recibió el ACK final.")
            client_protocol.close()
            return None

        # Validar que el ACK sea el correcto
        if header[1] != client_protocol.seq_num:
            print(f"[SERVER] Error: Número de ACK incorrecto. Se esperaba {client_protocol.seq_num}, se recibió {header[1]}")
            client_protocol.close()
            return None

        # 4. Esperar el paquete con el nombre del archivo
        print("[SERVER] Handshake completo. Esperando nombre de archivo...")
        header, data = client_protocol._receive_reliable_packet(expected_flags=FLAG_FNAME)
        if not header:
            print("[SERVER] Error: No se recibió el paquete con el nombre del archivo.")
            client_protocol.close()
            return None

        client_protocol.filename = data.decode('utf-8')
        print(f"[SERVER] Nombre de archivo recibido: {client_protocol.filename}")

        print(f"[SERVER] Conexión aceptada de {client_protocol.peer_address}")
        client_protocol.is_connected = True
        return client_protocol

    def _send_reliable_packet(self, flags, data):
        """Envía un paquete y espera su ACK, con reintentos."""
        attempts = 3
        while attempts > 0:
            self._send_packet(flags, data)
            
            header, _, _ = self._receive_packet(self.retransmission_timeout)
            
            # Si se recibe un ACK válido para nuestros datos
            if header and (header[2] & FLAG_ACK) and header[1] == (self.seq_num + len(data)):
                print("ACK para paquete confiable recibido correctamente.")
                self.seq_num += len(data)
                self.ack_num = header[0] + 1
                return True

            print("Timeout o ACK incorrecto. Retransmitiendo paquete confiable...")
            attempts -= 1

        raise ConnectionError("Fallo al enviar paquete confiable. No se recibió ACK.")

    def send(self, data: bytes) -> int:
        """
        Envía datos de forma confiable usando Stop-and-Wait.
        """
        if not self.is_connected:
            raise ConnectionError("Socket no conectado.")

        self._send_packet(FLAG_PSH | FLAG_ACK, data)
        if self._send_reliable_packet(FLAG_PSH | FLAG_ACK, data):
            return len(data)

    def _receive_reliable_packet(self, expected_flags=0):
        """Recibe un paquete de datos, lo confirma con ACK y lo devuelve."""
        while True:
            header, data, _ = self._receive_packet(timeout=None)
            if not header:
                continue

            # Verificamos si tiene los flags esperados (si se especificaron)
            if expected_flags and not (header[2] & expected_flags):
                print(f"Paquete inesperado. Se esperaban flags {bin(expected_flags)}, se recibió {bin(header[2])}")
                continue

            # Si el número de secuencia es el esperado
            if header[0] == self.ack_num:
                print("Paquete confiable recibido en orden.")
                self.ack_num = header[0] + len(data)
                self.seq_num = header[1]
                
                # Enviar ACK para los datos recibidos
                self._send_packet(FLAG_ACK)
                return header, data
            else:
                # Paquete duplicado o fuera de orden, reenviar el último ACK
                print(f"Paquete fuera de orden recibido. Se esperaba SEQ={self.ack_num}, se recibió {header[0]}.")
                self._send_packet(FLAG_ACK) # Reenviar el ACK de lo que sí esperamos

    def recv(self, buffer_size: int) -> bytes:
        """
        Recibe datos de forma confiable.
        """
        if not self.is_connected:
            raise ConnectionError("Socket no conectado.")

        while True:
            header, data, _ = self._receive_packet(timeout=None)
            if not header:
                continue

            # Si es un paquete de datos (PSH) pero no de FNAME
            if header[2] & FLAG_PSH and not (header[2] & FLAG_FNAME):
                return self._receive_reliable_packet()[1]
            elif header[2] & FLAG_FIN: # Manejar cierre de conexión
                print("Recibido FIN. La conexión se está cerrando.")
                self.ack_num = header[0] + 1
                self._send_packet(FLAG_ACK | FLAG_FIN)
                self.is_connected = False
                return b'' # Indicar fin de la conexión

    def close(self):
        """
        Cierra la conexión de forma ordenada.
        """
        if self.is_connected:
            self._send_packet(FLAG_FIN)
            # Esperar ACK o FIN-ACK
            header, _, _ = self._receive_packet(self.retransmission_timeout)
            if header and (header[2] & FLAG_ACK):
                print("Cierre de conexión confirmado.")
        
        if self.socket:
            self.socket.close()
            print("Socket cerrado.")
        self.is_connected = False
