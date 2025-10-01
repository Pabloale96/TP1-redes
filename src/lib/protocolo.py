import random
import struct
import time

from lib.sockets import Socket

from .logger import logger

# --- Definición de Flags para el Encabezado del Protocolo ---
FLAG_SYN = 0b00000001  # Iniciar conexión
FLAG_ACK = 0b00000010  # Acuse de recibo
FLAG_FIN = 0b00000100  # Finalizar conexión
FLAG_PSH = 0b00001000  # Empujar datos (indica que el paquete tiene payload)
FLAG_FNAME = 0b00010000  # Indica que el payload es un nombre de archivo
FLAG_OP = 0b00100000

WINDOW_SIZE = 100
BUFFER_SIZE = 1024  # Tamaño del buffer para recv/send para selective repeat
PAYLOAD_SIZE = 400

# Formato del encabezado:
# ! -> Network Byte Order (big-endian)
# I -> Unsigned Integer (4 bytes) para número de secuencia
# I -> Unsigned Integer (4 bytes) para número de ack
# B -> Unsigned Char (1 byte) para flags
# H -> Unsigned Short (2 bytes) para checksum (no implementado, pero reservado)
HEADER_FORMAT = "!IIBH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)


class Protocol:
    STOP_AND_WAIT = 1
    SELECTIVE_REPEAT = 2
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

    def __init__(self, local_host="127.0.0.1", local_port=0, client=False, recovery_mode=STOP_AND_WAIT):
        self.is_connected = False
        self.socket = None
        self.peer_address = None
        self.seq_num = random.randint(0, 1000)
        self.ack_num = 0
        self.filename = None
        self.operation = None

        # Modo de recuperación elegido (STOP_AND_WAIT o SELECTIVE_REPEAT)
        self.recovery_mode = recovery_mode
        self.retransmission_timeout = 2
        self.socket = Socket(local_host, local_port)
        if not client:
            self.socket.bind()

    def send(self, data: bytes, type=STOP_AND_WAIT) -> int:
        if not self.is_connected:
            raise ConnectionError("Socket no conectado.")

        if self._send_reliable_packet(FLAG_PSH | FLAG_ACK, data, type=type):
            return len(data)

    def recv(self, payload_size: int, type: int) -> bytes:
        # Sumamos el header size al paquete
        buffer_size = payload_size + HEADER_SIZE
        # Seleccionar el método de recepción según el tipo solicitado.
        if type == self.STOP_AND_WAIT:
            return self._recv_stop_and_wait(buffer_size)
        elif type == self.SELECTIVE_REPEAT:
            return self._recv_selective_repeat(buffer_size)
        else:
            raise ValueError(f"Tipo de recepción desconocido: {type}")

    def connect(self, server_address, filename: str, fileop=0) -> bool:

        self.peer_address = server_address
        self.filename = filename
        logger.vprint(f"[CLIENT] Iniciando handshake con {server_address}")

        # 1. Enviar SYN
        self._send_packet(FLAG_SYN)
        self.seq_num += 1

        # 2. Esperar SYN-ACK
        header, _, new_address = self._receive_packet(self.retransmission_timeout)
        logger.vprint(f"[CLIENT] Recibido SYN-ACK: {header} desde {new_address}")
        if not header or not (header[2] & FLAG_SYN and header[2] & FLAG_ACK):
            logger.vprint("Error: Handshake fallido. No se recibió SYN-ACK.")
            return False

        # 3. Actualizar direccion del peer y normalizar seq/ack
        self.peer_address = new_address
        # header[0] es el seq del servidor; el siguiente seq esperado desde el servidor
        # será server_seq + 1 (porque SYN consume un número de secuencia)
        server_seq = header[0]
        client_seq = self.seq_num
        self.ack_num = server_seq + 1
        # El cliente ya incrementó self.seq_num tras enviar SYN; asegurarse de que
        # seq_num representa el próximo número a usar para enviar.
        self.seq_num = client_seq

        # 4. Enviar ACK
        self._send_packet(FLAG_ACK)
        logger.vprint(f"[CLIENT] Handshake completado.")

        # 5. Enviar la operación de forma confiable (incluye el protocolo de recuperación)
        chosen_protocol = self.recovery_mode
        self.recovery_mode = chosen_protocol
        logger.vprint(
            f"[CLIENT] Enviando operacion de archivo: {fileop}, protocolo: {chosen_protocol}"
        )
        payload = bytes([fileop & 0xFF, chosen_protocol & 0xFF])
        if not self._send_reliable_packet(FLAG_OP | FLAG_PSH, payload):
            logger.vprint("[CLIENT] No se pudo confirmar la operación con el servidor.")
            return False

        # 6. Enviar el nombre del archivo de forma confiable
        logger.vprint(f"[CLIENT] Enviando nombre de archivo: {self.filename}")
        if not self._send_reliable_packet(
            FLAG_FNAME | FLAG_PSH, self.filename.encode("utf-8")
        ):
            logger.vprint(
                "[CLIENT] No se pudo enviar el nombre de archivo al servidor."
            )
            return False

        logger.vprint(f"[CLIENT] Conexión establecida con {self.peer_address}")
        self.is_connected = True
        return True

    def accept(self):

        logger.vprint("[SERVER] Esperando por un SYN...")

        # 1. Esperar SYN (bloqueante, descarta paquetes inválidos)
        while True:
            header, _, address = self._receive_packet(timeout=None)
            logger.vprint(f"[SERVER] Recibido: {header} de {address}")
            if header and (header[2] & FLAG_SYN):
                break
            logger.vprint(
                "[SERVER] Paquete inesperado recibido o error, se esperaba SYN. Descartando y esperando de nuevo."
            )

        # 2. Crear una nueva instancia de Protocol para este cliente
        local_host, _ = self.socket.addr
        client_protocol = Protocol(local_host, 0, client=True)
        client_protocol.socket.bind()
        client_protocol.peer_address = address
        client_protocol.ack_num = header[0] + 1

        # 3. Enviar SYN-ACK
        client_protocol._send_packet(FLAG_SYN | FLAG_ACK)
        client_protocol.seq_num += 1
        logger.vprint(f"[SERVER] SYN-ACK enviado a {address}")

        # 4. Esperar ACK final
        header, _, _ = client_protocol._receive_packet(self.retransmission_timeout)
        logger.vprint(f"[SERVER] Recibido ACK final: {header}")
        if not header or not (header[2] & FLAG_ACK):
            logger.vprint(
                "[SERVER] Error: Handshake fallido. No se recibió el ACK final."
            )
            client_protocol.close()
            return None

        # Validacion del ack
        if header[1] != client_protocol.seq_num:
            logger.vprint(
                f"[SERVER] Error: Número de ACK incorrecto. Se esperaba {client_protocol.seq_num}, se recibió {header[1]}"
            )
            client_protocol.close()
            return None

        # Normalizar seq/ack: header[1] es el ACK del cliente indicando el siguiente seq
        # que el cliente usará; por tanto seq_num del servidor (del lado del cliente_protocol)
        # debe reflejar ese valor como próximo número a usar.
        client_protocol.seq_num = header[1]

        # 5. Esperar el paquete con la operación
        logger.vprint("[SERVER] Handshake completo. Esperando operación...")
        header, data = client_protocol._receive_reliable_packet(expected_flags=FLAG_OP)
        if not header or not (header[2] & FLAG_OP):
            logger.vprint("[SERVER] Error: No se recibió el paquete con la operación.")
            client_protocol.close()
            return None

        # Tomamos los dos primeros bytes del payload como operación y protocolo
        if data and len(data) >= 2:
            operacion = data[0]
            proto = data[1]
        elif data and len(data) == 1:
            operacion = data[0]
            proto = self.STOP_AND_WAIT
        else:
            logger.vprint("[SERVER] Error: Payload de operación inválido.")
            client_protocol.close()
            return None

        client_protocol.operation = operacion
        client_protocol.recovery_mode = proto
        logger.vprint(
            f"[SERVER] Operacion recibida: {client_protocol.operation}, protocolo: {client_protocol.recovery_mode}"
        )

        # 6. Esperar el paquete con el nombre del archivo
        logger.vprint("[SERVER] Esperando nombre de archivo...")
        header, data = client_protocol._receive_reliable_packet(
            expected_flags=FLAG_FNAME
        )
        if not header or not (header[2] & FLAG_FNAME):
            logger.vprint(
                "[SERVER] Error: No se recibió el paquete con el nombre del archivo."
            )
            client_protocol.close()
            return None

        client_protocol.filename = data.decode("utf-8")
        logger.vprint(
            f"[SERVER] Nombre de archivo recibido: {client_protocol.filename}"
        )

        logger.vprint(f"[SERVER] Conexión aceptada de {client_protocol.peer_address}")
        client_protocol.is_connected = True
        return client_protocol

    def close(self):
        if self.is_connected:
            self.is_connected = False
            self._send_packet(FLAG_FIN)
            header, _, _ = self._receive_packet(timeout=1.0)
            if header and (header[2] & FLAG_ACK):
                logger.vprint("Cierre de conexión confirmado.")
            else:
                logger.vprint(
                    "No se recibió confirmación de cierre (FIN-ACK). Cerrando de todos modos."
                )

        if self.socket:
            self.socket.close()
            logger.vprint("Socket cerrado.")
        self.is_connected = False

    def _pack_header(self, seq, ack, flags):
        return struct.pack(HEADER_FORMAT, seq, ack, flags, 0)

    def _unpack_header(self, header_bytes):
        return struct.unpack(HEADER_FORMAT, header_bytes)

    def _send_packet(self, flags, data=b""):
        header = self._pack_header(self.seq_num, self.ack_num, flags)
        payload_len = len(data) if data else 0
        logger.vprint(
            f"-> Enviando [SEQ={self.seq_num}, ACK={self.ack_num}, Flags={bin(flags)}, LEN={payload_len}] a {self.peer_address}"
        )
        self.socket.sendto(header + data, self.peer_address)

    def _receive_packet(self, timeout):
        """Espera y recibe un paquete, con un timeout."""
        # Aumentamos el buffer por si los payloads son relativamente grandes
        self.socket.socket.settimeout(timeout)
        try:
            packet, address = self.socket.recvfrom(1024)
            if len(packet) < HEADER_SIZE:
                logger.vprint(
                    f"Paquete recibido demasiado corto ({len(packet)} bytes). Ignorando."
                )
                return None, None, None
            header = self._unpack_header(packet[:HEADER_SIZE])
            data = packet[HEADER_SIZE:]
            logger.vprint(
                f"<- Recibido [SEQ={header[0]}, ACK={header[1]}, Flags={bin(header[2])}, LEN={len(data)}] de {address}"
            )
            return header, data, address
        except Exception:
            # Timeout u otro error; devolvemos None para que el llamador maneje reintentos
            return None, None, None

    def _send_reliable_packet(self, flags, data, type=STOP_AND_WAIT):
        if type == self.STOP_AND_WAIT:
            return self._send_stop_and_wait(flags, data)
        elif type == self.SELECTIVE_REPEAT:
            return self._send_selective_repeat(data)
        else:
            raise ValueError(f"Tipo de envío desconocido: {type}")

    def _send_stop_and_wait(self, flags, data):
        offset = 0
        n = len(data)

        while offset < n:
            payload = data[offset:offset + PAYLOAD_SIZE]

            attempts = 5                     # ← reset here, per packet
            while attempts > 0:
                self._send_packet(flags, payload)
                header,_ , _ = self._receive_packet(self.retransmission_timeout)

                expected_ack = self.seq_num + len(payload)
                if header and (header[2] & FLAG_ACK) and header[1] == expected_ack:
                    self.seq_num = expected_ack
                    offset += len(payload)
                    break
                else:
                    logger.vprint("Timeout o ACK incorrecto. Retransmitiendo paquete confiable...")
                    attempts -= 1

            if attempts == 0:
                return False

        return True

    def _recv_stop_and_wait(self, buffer_size):
            if not self.is_connected:
                return b""

            expected_seq = self.ack_num
            received_data = bytearray()

            while True:
                header, data, _ = self._receive_packet(timeout=None)
                if not header:
                    self.is_connected = False
                    return bytes(received_data)

                seq_num = header[0]

                if header[2] & FLAG_PSH:
                    # Paquete en orden exacto
                    if seq_num == expected_seq:
                        # Entregamos inmediatamente si coincide con lo esperado
                        received_data.extend(data)
                        expected_seq += len(data)
                        self.ack_num = expected_seq
                        self._send_packet(FLAG_ACK)
                        if len(received_data) >= buffer_size:
                            return bytes(received_data)
                        continue

                    else:
                        # Paquete fuera de la ventana, reenviar último ACK
                        logger.vprint(
                            f"Paquete con SEQ ={seq_num} no esperado. Reenviando último ACK."
                        )
                        self._send_packet(FLAG_ACK)

                elif header[2] & FLAG_FIN:
                    logger.vprint("Recibido FIN. La conexión se está cerrando.")
                    self.ack_num = header[0] + 1
                    self._send_packet(FLAG_ACK | FLAG_FIN)
                    self.is_connected = False
                    return bytes(received_data)

                else:
                    logger.vprint(f"Paquete inesperado con SEQ={seq_num} [sin flag PSH]. Ignorando.")

    def _receive_reliable_packet(self, expected_flags=0):
        while True:
            header, data, _ = self._receive_packet(timeout=None)
            if not header:
                continue

            if expected_flags and not (header[2] & expected_flags):
                logger.vprint(
                    f"Paquete inesperado. Se esperaban flags {bin(expected_flags)}, se recibió {bin(header[2])}"
                )
                continue

            # Si el número de secuencia es el esperado y off-by-one en la numeración
            # los paquetes SYN t SYN-ACK de la coneccion no modifican el ack_num
            if header[0] == self.ack_num or header[0] == (self.ack_num - 1):

                logger.vprint(
                    "Paquete confiable recibido en orden (o tolerado off-by-one)."
                )
                self.ack_num = header[0] + len(data)
                self.seq_num = header[1]

                self._send_packet(FLAG_ACK)
                return header, data

            else:
                logger.vprint(
                    f"Paquete fuera de orden recibido. Se esperaba SEQ={self.ack_num}, se recibió {header[0]}."
                )
                self._send_packet(FLAG_ACK)

    def _send_selective_repeat(self, data):
        if not self.is_connected:
            return False

        # Enviar en fragmentos de tamaño buffer_size
        offset = 0
        attempts_limit = 5

        while offset < len(data):
            chunk = data[offset : offset + BUFFER_SIZE]  # Tomar un fragmento

            # Enviar el fragmento con PSH
            current_seq = self.seq_num
            self._send_packet(FLAG_PSH, chunk)

            # Esperar ACK que confirme next byte esperado
            attempts = attempts_limit
            ack_received = False
            while attempts > 0:
                header, _, _ = self._receive_packet(self.retransmission_timeout)
                if header and (header[2] & FLAG_ACK):
                    expected_ack = current_seq + len(chunk)

                    # El receptor pone header[1] como ack_num (siguiente seq esperado)
                    if header[1] == expected_ack:
                        ack_received = True
                        logger.vprint(
                            f"ACK recibido para SEQ={current_seq} (ACK={header[1]})"
                        )
                        self.seq_num = expected_ack
                        self.ack_num = header[0] + 1
                        break
                    else:
                        logger.vprint(
                            f"ACK recibido pero con valor inesperado {header[1]} (se esperaba {expected_ack})."
                        )
                else:
                    logger.vprint("Timeout esperando ACK. Retransmitiendo chunk...")

                self._send_packet(FLAG_PSH, chunk)
                attempts -= 1

            if not ack_received:
                logger.vprint(
                    "No se recibió ACK tras varios intentos. Abortar envío Selective Repeat."
                )
                return False

            offset += len(chunk)

        return True

    def _recv_selective_repeat(self, buffer_size: int) -> bytes:

        if not self.is_connected:
            return b""

        received_data = bytearray()
        expected_seq = self.ack_num
        window_size = 5
        buffer = {}

        while True:
            header, data, _ = self._receive_packet(timeout=None)
            if not header:
                self.is_connected = False
                return bytes(received_data)

            seq_num = header[0]

            if header[2] & FLAG_PSH:
                # Paquete en orden exacto
                if seq_num == expected_seq:
                    # Entregamos inmediatamente si coincide con lo esperado
                    received_data.extend(data)
                    expected_seq += len(data)
                    self.ack_num = expected_seq
                    self._send_packet(FLAG_ACK)
                    if len(received_data) >= buffer_size:
                        return bytes(received_data)
                    continue

                if expected_seq <= seq_num < expected_seq + window_size * buffer_size:
                    # Paquete dentro de la ventana
                    if seq_num not in buffer:
                        buffer[seq_num] = data
                        logger.vprint(
                            f"Paquete con SEQ={seq_num} almacenado en buffer."
                        )

                    # Enviar ACK inmediatamente
                    self._send_packet(FLAG_ACK)

                    # Entregar datos en orden desde el buffer
                    while expected_seq in buffer:
                        chunk = buffer.pop(expected_seq)
                        received_data.extend(chunk)
                        chunk_len = len(chunk)
                        expected_seq += chunk_len
                        self.ack_num = expected_seq

                    # Si hemos recibido suficiente datos, devolvemos lo recibido hasta ahora
                    if len(received_data) >= buffer_size:
                        return bytes(received_data)

                else:
                    # Paquete fuera de la ventana, reenviar último ACK
                    logger.vprint(
                        f"Paquete con SEQ={seq_num} fuera de la ventana. Reenviando último ACK."
                    )
                    self._send_packet(FLAG_ACK)

            elif header[2] & FLAG_FIN:
                logger.vprint("Recibido FIN. La conexión se está cerrando.")
                self.ack_num = header[0] + 1
                self._send_packet(FLAG_ACK | FLAG_FIN)
                self.is_connected = False
                return bytes(received_data)

            else:
                logger.vprint(f"Paquete inesperado con SEQ={seq_num}. Ignorando.")

    def __del__(self):
        self.close()
