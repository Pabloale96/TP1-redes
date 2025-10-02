import random
import struct
import time

from lib.sockets import Socket

from .logger import logger

from .rto_estimator import RTOEstimator

# --- Definición de Flags para el Encabezado del Protocolo ---
FLAG_SYN = 0b00000001  # Iniciar conexión
FLAG_ACK = 0b00000010  # Acuse de recibo
FLAG_FIN = 0b00000100  # Finalizar conexión
FLAG_PSH = 0b00001000  # Empujar datos (indica que el paquete tiene payload)
FLAG_FNAME = 0b00010000  # Indica que el payload es un nombre de archivo
FLAG_OP = 0b00100000

WINDOW_SIZE = 100
BUFFER_SIZE = 1024  # Tamaño del buffer para recv/send para selective repeat
PAYLOAD_SIZE = 1200
MAX_DGRAM = 2048

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
        self.retransmission_timeout = 1
        self.socket = Socket(local_host, local_port)
        if not client:
            self.socket.bind()

        self.rto_estimator = RTOEstimator()

    def send(self, data: bytes, type=STOP_AND_WAIT) -> int:
        if not self.is_connected:
            raise ConnectionError("Socket no conectado.")

        if self._send_reliable_packet(FLAG_PSH, data, type=type):
            return len(data)

    def recv(self, payload_size: int, type: int) -> bytes:
        # Sumamos el header size al paquete
        if not self.is_connected:
            raise ConnectionError("Socket no conectado.")
        header, data = self._receive_reliable_packet(payload_size=payload_size, expected_flags=FLAG_PSH, type = type) 
        if data:
            #print(f"recv_data: {bytes(data)}")
            return bytes(data)
        else:
            return b""

    def connect(self, server_address, filename: str, fileop=0) -> bool:

        self.peer_address = server_address
        self.filename = filename
        logger.vprint(f"[CLIENT] Iniciando handshake con {server_address}")

        # --- Client ISN and initial numbers ---
        client_isn = self.seq_num            # use existing random ISN
        self.ack_num = 0

        # --- 1) Send SYN reliably (retries + backoff) ---
        attempts = 6
        rto = float(self.retransmission_timeout)
        synack_ok = False

        while attempts > 0 and not synack_ok:
            # Always send SYN with the SAME seq (ISN)
            saved_seq = self.seq_num
            self.seq_num = client_isn
            self._send_packet(FLAG_SYN)
            self.seq_num = saved_seq
            logger.vprint(f"[CLIENT] SYN (ISN={client_isn}) enviado. Esperando SYN-ACK...")

            deadline = time.monotonic() + rto
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                header, _, addr = self._receive_packet(max(0.0, remaining))
                if not header:
                    continue
                # Only enforce same host, not same port (server uses per-connection socket)
                if addr[0] != server_address[0]:
                    logger.vprint(f"[CLIENT] Origen inesperado {addr}, ignorando.")
                    continue
                if (header[2] & FLAG_SYN) and (header[2] & FLAG_ACK):
                    # Validate ACK of our SYN
                    if header[1] != client_isn + 1:
                        logger.vprint(f"[CLIENT] SYN-ACK con ACK inesperado {header[1]} (esp {client_isn+1}). Ignorando.")
                        continue
                    server_isn = header[0]
                    # Set our post-SYN numbers
                    self.peer_address = addr
                    self.seq_num = client_isn + 1
                    self.ack_num = server_isn + 1
                    synack_ok = True
                    logger.vprint(f"[CLIENT] SYN-ACK ok: server_isn={server_isn}.")
                    break
                else:
                    # Ignore anything else during handshake
                    logger.vprint(f"[CLIENT] Paquete no SYN-ACK durante handshake: flags={bin(header[2])}. Ignorando.")

            if not synack_ok:
                attempts -= 1
                rto = min(rto * 2.0, 8.0)  # simple backoff cap
                logger.vprint(f"[CLIENT] Reintentando SYN... intentos restantes={attempts}")

        if not synack_ok:
            logger.vprint("[CLIENT] Handshake fallido: no se recibió SYN-ACK válido.")
            return False

        # --- 2) Send final ACK and LINGER to re-ACK duplicates ---
        # We send the final ACK once, then listen briefly; if a duplicate SYN-ACK arrives,
        # re-send the ACK so the server can transition to ESTABLISHED.
        self._send_packet(FLAG_ACK)
        logger.vprint("[CLIENT] ACK final enviado. Linger para duplicados de SYN-ACK...")

        linger_end = time.monotonic() + 1.0  # short linger window
        while time.monotonic() < linger_end:
            remaining = linger_end - time.monotonic()
            header, _, addr = self._receive_packet(max(0.0, remaining))
            if not header:
                continue
            if addr != self.peer_address:
                continue
            if (header[2] & FLAG_SYN) and (header[2] & FLAG_ACK):
                # Server likely missed our ACK; re-ACK
                self.ack_num = header[0] + 1   # next expected from server
                # Keep seq_num at client_isn+1 (no new data yet)
                self._send_packet(FLAG_ACK)
                logger.vprint("[CLIENT] Re-ACKeando SYN-ACK duplicado.")
            else:
                # Ignore anything else in linger (no state advance yet)
                pass

        logger.vprint(f"[CLIENT] Handshake completado con {self.peer_address}")

        # --- 3) Send OP and FNAME reliably (as you already do) ---
        self.is_connected = True
        chosen_protocol = self.recovery_mode
        payload = bytes([fileop & 0xFF, chosen_protocol & 0xFF])
        if not self._send_reliable_packet(FLAG_PSH | FLAG_OP, payload):
            logger.vprint("[CLIENT] No se pudo confirmar la operación con el servidor.")
            self.is_connected = False
            return False

        logger.vprint(f"[CLIENT] Enviando nombre de archivo: {self.filename}")
        if not self._send_reliable_packet(FLAG_PSH | FLAG_FNAME, self.filename.encode("utf-8")):
            logger.vprint("[CLIENT] No se pudo enviar el nombre de archivo al servidor.")
            self.is_connected = False
            return False

        logger.vprint(f"[CLIENT] Conexión establecida con {self.peer_address}")
        return True

    def accept(self):
        import time

        logger.vprint("[SERVER] Esperando por un SYN...")

        # 1) Wait for a SYN on the listening socket (block)
        while True:
            header, _, address = self._receive_packet(timeout=None)
            logger.vprint(f"[SERVER] Recibido: {header} de {address}")
            if header and (header[2] & FLAG_SYN):
                break
            logger.vprint("[SERVER] Se esperaba SYN. Ignorando paquete.")

        client_isn = header[0]
        client_addr = address

        # 2) Create per-client Protocol (new UDP socket on ephemeral port)
        local_host, _ = self.socket.addr
        client_protocol = Protocol(local_host, 0, client=True)
        client_protocol.socket.bind()

        # Log the actual bound port (not the requested 0)
        try:
            bound_addr = client_protocol.socket.socket.getsockname()
            logger.vprint(f"[SERVER] Socket por-conexión en {bound_addr}")
        except Exception:
            pass

        client_protocol.peer_address = client_addr
        client_protocol.ack_num = client_isn + 1

        # FIX: capture and reuse the same server ISN for all SYN-ACK retransmissions
        server_isn = client_protocol.seq_num

        attempts = 6
        rto = float(self.retransmission_timeout)  # e.g., 2s

        while attempts > 0:
            # 3) Send SYN-ACK with a FIXED server ISN
            saved = client_protocol.seq_num
            client_protocol.seq_num = server_isn
            client_protocol._send_packet(FLAG_SYN | FLAG_ACK)
            client_protocol.seq_num = saved
            logger.vprint(f"[SERVER] SYN-ACK (ISN={server_isn}) enviado a {client_addr}")

            # 4) Wait for final ACK or duplicate SYN; retransmit on timeout
            deadline = time.monotonic() + rto
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                hdr, _, addr = client_protocol._receive_packet(max(0.0, remaining))
                if not hdr:
                    continue
                if addr != client_addr:
                    logger.vprint("[SERVER] Paquete de otro origen durante handshake; ignorando.")
                    continue

                # Duplicate SYN from client (it didn't see our SYN-ACK) -> re-send SYN-ACK
                if (hdr[2] & FLAG_SYN) and not (hdr[2] & FLAG_ACK) and hdr[0] == client_isn:
                    logger.vprint("[SERVER] SYN duplicado; re-enviando SYN-ACK.")
                    saved = client_protocol.seq_num
                    client_protocol.seq_num = server_isn
                    client_protocol._send_packet(FLAG_SYN | FLAG_ACK)
                    client_protocol.seq_num = saved
                    continue

                # Final ACK from client; validate ACK number
                if (hdr[2] & FLAG_ACK) and hdr[1] == server_isn + 1:
                    logger.vprint("[SERVER] ACK final OK. Handshake completado.")
                    client_protocol.seq_num = server_isn + 1
                    client_protocol.is_connected = True
                    # Ready to receive OP/FNAME using the per-client socket
                    # Receive OP
                    hdr, data = client_protocol._receive_reliable_packet(expected_flags=FLAG_OP, payload_size=PAYLOAD_SIZE)
                    print(f"header_fuera: {hdr}")
                    if not hdr or not (hdr[2] & FLAG_OP) or not data:
                        print("Not header FLAHOP data")
                        print(f"header_error:{hdr[2]}")
                        client_protocol.close(); return None
                    if len(data) >= 2:
                        client_protocol.operation = data[0]
                        client_protocol.recovery_mode = data[1]
                    else:
                        client_protocol.operation = data[0]
                        client_protocol.recovery_mode = self.STOP_AND_WAIT

                    # Receive FNAME
                    print(f"client_op: {client_protocol.operation}")
                    print(f"client_rm: {client_protocol.recovery_mode}")
                    hdr, data = client_protocol._receive_reliable_packet(expected_flags=FLAG_FNAME, payload_size=PAYLOAD_SIZE)
                    if not hdr or not (hdr[2] & FLAG_FNAME) or not data:
                        print("Not header FLAG_FNAME or DATA")
                        client_protocol.close(); return None

                    fname = data.decode('utf-8', errors='replace').strip()
                    if not fname:
                        logger.vprint("[SERVER] Nombre de archivo vacío.")
                        print("Not filename")
                        client_protocol.close()
                        return None
                    client_protocol.filename = fname

                    logger.vprint(f"[SERVER] Conexión aceptada de {client_protocol.peer_address}, archivo: {client_protocol.filename}")

                    print("Rtornando protocolo")

                    return client_protocol

                # Anything else during handshake is ignored
                logger.vprint(f"[SERVER] Paquete no esperado durante handshake: flags={bin(hdr[2])}")

            attempts -= 1
            rto = min(rto * 2.0, 8.0)
            logger.vprint(f"[SERVER] Timeout esperando ACK; reintentando SYN-ACK (restan {attempts}).")

        logger.vprint("[SERVER] Handshake fallido tras varios intentos.")
        client_protocol.close()
        return None

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
            packet, address = self.socket.recvfrom(MAX_DGRAM)
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
            sent, offset = self._send_stop_and_wait(flags, data)
            while not sent:
                sent, offset = self._send_stop_and_wait(flags, data[offset::])
            return True
        elif type == self.SELECTIVE_REPEAT:
            return self._send_selective_repeat(data)
        else:
            raise ValueError(f"Tipo de envío desconocido: {type}")

    def _send_stop_and_wait(self, flags, data):
        offset = 0
        n = len(data)
        sent_flag_ACK = False

        while offset < n or (flags & FLAG_ACK and sent_flag_ACK):
            payload = data[offset:offset + PAYLOAD_SIZE]

            attempts = 3                     # ← reset here, per packet
            while attempts > 0:
                send_time = time.time()
                self._send_packet(flags, payload)

                timeout = self.rto_estimator.get_timeout()
                logger.vprint(f"\n[Sender] Timeout {timeout}\n")
                header,_ , _ = self._receive_packet(timeout)

                # len(data) = 2600
                # pack1_off = 0, e_ack 1200, seq 1200
                # pack2_off = 1200, ACK lost,  server_ack = 2400, seq = 1200
                # pack21_off = 1200, ACK lost,  server_ack = 2400, seq = 1200
                # pack3_off = 2400, e_ack = 2400, seq = 2400
                expected_ack = self.seq_num + len(payload)
                print("\n\n\n")
                print(f"peer address: {self.peer_address}")
                print("\n\n\n")
                if header and (header[2] & FLAG_ACK) and header[1] >= expected_ack:
                    #200
                    # ACK correcto → actualizar RTO con la muestra de RTT
                    rtt_sample = time.time() - send_time
                    self.rto_estimator.note_sample(rtt_sample)

                    self.seq_num = header[1]
                    if len(payload) == 0:
                        sent_flag_ACK = True

                    if header[1] == expected_ack:
                        offset += len(payload)
                    else:
                        print("\n\n\n\n")
                        print("El ack enviado por el server es mayor al esperado")
                        print("\n\n\n\n")
                        offset += header[1] - expected_ack

                    logger.vprint(f"\n[Sender] RTT sample={rtt_sample:.4f}s, nuevo RTO={self.rto_estimator.get_timeout():.4f}s\n")
                    break
                else:
                    logger.vprint("Timeout o ACK incorrecto. Retransmitiendo paquete confiable...")
                    self.rto_estimator.backoff()

                    logger.vprint(f"\n[Sender] Backoff aplicado. Nuevo RTO={self.rto_estimator.get_timeout():.4f}s (intentos restantes={attempts})\n")
                    attempts -= 1

            if attempts == 0:
                return False, offset

        return True, None

    def _recv_stop_and_wait(self, buffer_size):
        if not self.is_connected:
            return b""

        expected_seq = self.ack_num
        received_data = bytearray()
        IDLE = 30.0  # seconds without traffic before giving up
        deadline = time.monotonic() + IDLE

        # ack 5

        while True:
            remaining = max(0.0, deadline - time.monotonic())
            header, data, _ = self._receive_packet(timeout=remaining if remaining > 0 else 0)
            if not header:
                # idle timeout?
                if time.monotonic() >= deadline:
                    logger.vprint("Idle timeout en recv Stop&Wait. Cerrando.")
                    self.is_connected = False
                    return None, bytes(received_data)
                # spurious/short packet case: continue waiting
                continue

            # reset idle timer on any valid packet
            deadline = time.monotonic() + IDLE

            seq_num = header[0]
            if header[2] & FLAG_OP or header[2] & FLAG_FNAME:
                if seq_num == expected_seq:
                    received_data.extend(data)
                    expected_seq += len(data)
                    self.ack_num = expected_seq
                    self._send_packet(FLAG_ACK)
                    return header, bytes(received_data)

            if header[2] & FLAG_PSH:
                if seq_num == expected_seq:
                    received_data.extend(data)
                    expected_seq += len(data)
                    self.ack_num = expected_seq
                    self._send_packet(FLAG_ACK)
                    if len(received_data) >= buffer_size:
                        return header, bytes(received_data)
                    continue
                else:
                    logger.vprint(f"SEQ inesperado {seq_num}. Reenviando último ACK.")
                    self._send_packet(FLAG_ACK, b"")

            elif header[2] & FLAG_FIN:
                logger.vprint("Recibido FIN. Cerrando.")
                self.ack_num = header[0] + 1
                self._send_packet(FLAG_ACK | FLAG_FIN, b"")
                self.is_connected = False
                print("Retornando con FLAG_FIN")
                return None, bytes(received_data)

            else:
                logger.vprint(f"Paquete inesperado con SEQ={seq_num}. Ignorando.")

    def _receive_reliable_packet(self, payload_size, expected_flags=0, type=STOP_AND_WAIT):
        buffer_size = payload_size
        # Seleccionar el método de recepción según el tipo solicitado.
        if type == self.STOP_AND_WAIT:
            return self._recv_stop_and_wait(buffer_size)
        elif type == self.SELECTIVE_REPEAT:
            return self._recv_selective_repeat(buffer_size)
        else:
            raise ValueError(f"Tipo de recepción desconocido: {type}")
        #while True:
        #    header, data, _ = self._receive_packet(timeout=None)
        #    if not header:
        #        continue

        #    if expected_flags and not (header[2] & expected_flags):
        #        logger.vprint(
        #            f"Paquete inesperado. Se esperaban flags {bin(expected_flags)}, se recibió {bin(header[2])}"
        #        )
        #        continue

        #    # Si el número de secuencia es el esperado y off-by-one en la numeración
        #    # los paquetes SYN t SYN-ACK de la coneccion no modifican el ack_num
        #    if header[0] == self.ack_num or header[0] == (self.ack_num - 1):

        #        logger.vprint(
        #            "Paquete confiable recibido en orden (o tolerado off-by-one)."
        #        )
        #        self.ack_num = header[0] + len(data)
        #        self.seq_num = header[1]

        #        self._send_packet(FLAG_ACK)
        #        return header, data

        #    else:
        #        logger.vprint(
        #            f"Paquete fuera de orden recibido. Se esperaba SEQ={self.ack_num}, se recibió {header[0]}."
        #        )
        #        self._send_packet(FLAG_ACK)

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
