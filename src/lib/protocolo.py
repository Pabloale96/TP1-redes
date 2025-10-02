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

WINDOW_SIZE = 25
BUFFER_SIZE = 1024  # Tamaño del buffer para recv/send para selective repeat
PAYLOAD_SIZE = 1024
MAX_DGRAM = 2048
IDLE_TIME = 30.0
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

        self.recovery_mode = recovery_mode
        self.retransmission_timeout = 1
        self.socket = Socket(local_host, local_port)
        if not client:
            self.socket.bind()

        self.rto_estimator = RTOEstimator()

    def send(self, data: bytes, type=STOP_AND_WAIT) -> int:
        if not self.is_connected:
            raise ConnectionError("Socket could not be connected")

        if self._send_reliable_packet(FLAG_PSH, data, type=type):
            return len(data)

    def recv(self, payload_size: int, type: int) -> bytes:
        if not self.is_connected:
            raise ConnectionError("Socket could not be connected.")
        header, data = self._receive_reliable_packet(payload_size=payload_size, expected_flags=FLAG_PSH, type = type) 
        if data:
            return bytes(data)
        else:
            return b""

    def connect(self, server_address, filename: str, fileop=0) -> bool:

        self.peer_address = server_address
        self.filename = filename
        logger.vprint(f"[CLIENT] Initializating handshake with peer {server_address}")

        client_isn = self.seq_num 
        self.ack_num = 0

        attempts = 6
        rto = float(self.retransmission_timeout)
        synack_ok = False

        while attempts > 0 and not synack_ok:
            saved_seq = self.seq_num
            self.seq_num = client_isn
            self._send_packet(FLAG_SYN)
            self.seq_num = saved_seq
            logger.vprint(f"[CLIENT] SYN (ISN={client_isn}) sent. Waiting SYN-ACK...")

            deadline = time.monotonic() + rto
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                header, _, addr = self._receive_packet(max(0.0, remaining))
                if not header:
                    continue
                if addr[0] != server_address[0]:
                    logger.vprint(f"[CLIENT] Unexpected source {addr}, ignoring.")
                    continue
                if (header[2] & FLAG_SYN) and (header[2] & FLAG_ACK):
                    if header[1] != client_isn + 1:
                        logger.vprint(f"[CLIENT] SYN-ACK with unexpected ACK number{header[1]} (expected: {client_isn+1}). Ignoring.")
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
                    logger.vprint(f"[CLIENT] No SYN-ACK packet during handshake: flags={bin(header[2])}. Ignoring.")

            if not synack_ok:
                attempts -= 1
                rto = min(rto * 2.0, 8.0)  # simple backoff cap
                logger.vprint(f"[CLIENT] Sending again SYN... Remaining attempts={attempts}")

        if not synack_ok:
            logger.vprint("[CLIENT] Failed handshake: no SYN-ACK valid was received.")
            return False

        # --- 2) Send final ACK and LINGER to re-ACK duplicates ---
        # We send the final ACK once, then listen briefly; if a duplicate SYN-ACK arrives,
        # re-send the ACK so the server can transition to ESTABLISHED.
        self._send_packet(FLAG_ACK)
        logger.vprint("[CLIENT] final ACK sent. Linger for SYN-ACK duplicates ...")

        linger_end = time.monotonic() + 2.0  # short linger window
        while time.monotonic() < linger_end:
            logger.vprint("[CLIENT] ")
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
                logger.vprint("[CLIENT] Re-ACKing SYN-ACK duplicates.")
            else:
                # Ignore anything else in linger (no state advance yet)
                pass

        logger.vprint(f"[CLIENT] Complete handshake with peer: {self.peer_address}")

        # --- 3) Send OP and FNAME reliably (as you already do) ---
        self.is_connected = True
        chosen_protocol = self.recovery_mode
        payload = bytes([fileop & 0xFF, chosen_protocol & 0xFF])
        if not self._send_reliable_packet(FLAG_PSH | FLAG_OP, payload):
            logger.vprint("[CLIENT] Operation could not be confirmed with the server.")
            self.is_connected = False
            return False

        logger.vprint(f"[CLIENT] Sending filename: {self.filename}")
        if not self._send_reliable_packet(FLAG_PSH | FLAG_FNAME, self.filename.encode("utf-8")):
            logger.vprint("[CLIENT] Filename could not be sent to the server.")
            self.is_connected = False
            return False

        logger.vprint(f"[CLIENT] Connection stablished with peer: {self.peer_address}")
        return True

    def accept(self):

        logger.vprint("[SERVER] Waiting for an SYN...")

        # 1) Wait for a SYN on the listening socket (block)
        while True:
            header, _, address = self._receive_packet(timeout=None)
            logger.vprint(f"[SERVER] Received: {header} from {address}")
            if header and (header[2] & FLAG_SYN):
                break
            logger.vprint("[SERVER] SYN expected. Ignoring packet.")

        client_isn = header[0]
        client_addr = address

        # 2) Create per-client Protocol (new UDP socket on ephemeral port)
        local_host, _ = self.socket.addr
        client_protocol = Protocol(local_host, 0, client=True)
        client_protocol.socket.bind()

        # Log the actual bound port (not the requested 0)
        try:
            bound_addr = client_protocol.socket.socket.getsockname()
            logger.vprint(f"[SERVER] Per-connection socket in {bound_addr}")
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
                    logger.vprint("[SERVER] Packet from another origin during handshake; ignoring.")
                    continue

                # Duplicate SYN from client (it didn't see our SYN-ACK) -> re-send SYN-ACK
                if (hdr[2] & FLAG_SYN) and not (hdr[2] & FLAG_ACK) and hdr[0] == client_isn:
                    logger.vprint("[SERVER] duplicate SYN; re-sending SYN-ACK.")
                    saved = client_protocol.seq_num
                    client_protocol.seq_num = server_isn
                    client_protocol._send_packet(FLAG_SYN | FLAG_ACK)
                    client_protocol.seq_num = saved
                    continue

                # Final ACK from client; validate ACK number
                if (hdr[2] & FLAG_ACK) and hdr[1] == server_isn + 1:
                    logger.vprint("[SERVER] final ACK OK. Completed handshake.")
                    client_protocol.seq_num = server_isn + 1
                    client_protocol.is_connected = True
                    # Ready to receive OP/FNAME using the per-client socket
                    # Receive OP
                    hdr, data = client_protocol._receive_reliable_packet(expected_flags=FLAG_OP, payload_size=PAYLOAD_SIZE)
                    if not hdr or not (hdr[2] & FLAG_OP) or not data:
                        client_protocol.close(); return None
                    if len(data) >= 2:
                        client_protocol.operation = data[0]
                        client_protocol.recovery_mode = data[1]
                    else:
                        client_protocol.operation = data[0]
                        client_protocol.recovery_mode = self.STOP_AND_WAIT

                    # Receive FNAME
                    hdr, data = client_protocol._receive_reliable_packet(expected_flags=FLAG_FNAME, payload_size=PAYLOAD_SIZE)
                    if not hdr or not (hdr[2] & FLAG_FNAME) or not data:
                        client_protocol.close(); return None

                    fname = data.decode('utf-8', errors='replace').strip()
                    if not fname:
                        logger.vprint("[SERVER] Empty filename.")
                        client_protocol.close()
                        return None
                    client_protocol.filename = fname

                    logger.vprint(f"[SERVER] Accepted connection from peer:{client_protocol.peer_address}, filename: {client_protocol.filename}")

                    return client_protocol

                # Anything else during handshake is ignored
                logger.vprint(f"[SERVER] Unexpected packet during handshake: flags={bin(hdr[2])}")

            attempts -= 1
            rto = min(rto * 2.0, 8.0)
            logger.vprint(f"[SERVER] Timeout occured waiting for ACK; Retrying SYN-ACK (remaining attempts: {attempts}).")

        logger.vprint("[SERVER] Failed handshake after several tries. Closing connection.")
        client_protocol.close()
        return None


    def close(self, attempts: int = 6, linger: float = None):
        """
        Reliable half/whole close:
          1) Send FIN reliably (retransmit with RTO/backoff) until ACKed.
          2) ACK the peer's FIN (whenever it arrives; possibly together with our ACK).
          3) TIME-WAIT: linger briefly to re-ACK duplicate FINs.
        """
        if not self.socket:
            return

        try:
            if not self.is_connected:
                # Best-effort TIME-WAIT anyway
                self.socket.close()
                logger.vprint("Socket has been closed.")
                return

            fin_seq = self.seq_num
            fin_acked = False
            peer_fin_seen = False

            rto = max(0.3, float(self.rto_estimator.get_timeout()))
            tries = attempts

            # 1) Send FIN reliably
            while tries > 0 and not fin_acked:
                t0 = time.time()
                self._send_packet(FLAG_FIN)

                deadline = time.monotonic() + rto
                while time.monotonic() < deadline:
                    header, _, addr = self._receive_packet(deadline - time.monotonic())
                    if not header or addr != self.peer_address:
                        continue

                    flags = header[2]

                    # ACK for our FIN?
                    if (flags & FLAG_ACK) and header[1] >= fin_seq + 1:
                        fin_acked = True
                        self.rto_estimator.note_sample(time.time() - t0)
                        self.seq_num = header[1]  # keep seq in sync
                        break

                    # Peer FIN (maybe together with ACK)
                    if flags & FLAG_FIN:
                        self.ack_num = header[0] + 1
                        self._send_packet(FLAG_ACK)
                        peer_fin_seen = True
                        # keep waiting in this window; we still need our FIN ACK

                if not fin_acked:
                    self.rto_estimator.backoff()
                    rto = min(8.0, self.rto_estimator.get_timeout())
                    tries -= 1

            # 2) If we haven't seen peer FIN yet, wait a bit for it and ACK it
            wait_for_fin = (linger if linger is not None
                            else max(1.0, 2.0 * self.rto_estimator.get_timeout()))
            end = time.monotonic() + wait_for_fin
            while time.monotonic() < end:
                header, _, addr = self._receive_packet(end - time.monotonic())
                if header and addr == self.peer_address and (header[2] & FLAG_FIN):
                    self.ack_num = header[0] + 1
                    self._send_packet(FLAG_ACK)
                    peer_fin_seen = True
                    # Keep looping: this doubles as TIME-WAIT too

            # 3) Short TIME-WAIT to re-ACK duplicate FINs
            tw = max(0.5, self.rto_estimator.get_timeout())
            tw_end = time.monotonic() + tw
            while time.monotonic() < tw_end:
                header, _, addr = self._receive_packet(tw_end - time.monotonic())
                if header and addr == self.peer_address and (header[2] & FLAG_FIN):
                    self.ack_num = header[0] + 1
                    self._send_packet(FLAG_ACK)

            logger.vprint(
                "Connection closure"
                + ("(FIN ACKed) confirmed" if fin_acked else "best-effort (FIN not confirmed)")
                + (", FIN from peer was received" if peer_fin_seen else ", FIN was not received")
                + "."
            )

        finally:
            self.is_connected = False
            self.socket.close()
            logger.vprint("Socket has been closed.")

    def _pack_header(self, seq, ack, flags):
        return struct.pack(HEADER_FORMAT, seq, ack, flags, 0)

    def _unpack_header(self, header_bytes):
        return struct.unpack(HEADER_FORMAT, header_bytes)

    def _send_packet(self, flags, data=b""):
        header = self._pack_header(self.seq_num, self.ack_num, flags)
        payload_len = len(data) if data else 0
        logger.vprint(
            f"-> Sending [SEQ={self.seq_num}, ACK={self.ack_num}, Flags={bin(flags)}, LEN={payload_len}] a {self.peer_address}"
        )
        self.socket.sendto(header + data, self.peer_address)

    def _receive_packet(self, timeout):
        self.socket.socket.settimeout(timeout)
        try:
            packet, address = self.socket.recvfrom(MAX_DGRAM)
            if len(packet) < HEADER_SIZE:
                logger.vprint(
                    f"Received packet too short ({len(packet)} bytes). Ignoring."
                )
                return None, None, None
            header = self._unpack_header(packet[:HEADER_SIZE])
            data = packet[HEADER_SIZE:]
            logger.vprint(
                f"<- Received [SEQ={header[0]}, ACK={header[1]}, Flags={bin(header[2])}, LEN={len(data)}] from addr: {address}"
            )
            return header, data, address
        except Exception:
            return None, None, None

    def _send_reliable_packet(self, flags, data, type=STOP_AND_WAIT):
        if type == self.STOP_AND_WAIT:
            sent, offset = self._send_stop_and_wait(flags, data)
            i = 0
            while i < 3 and not sent:
                data = data[offset::]
                sent, offset = self._send_stop_and_wait(flags, data)
                i+=1
            if not sent:
                logger.vprint("ERROR: Connection error")
                raise Exception("ERROR: Connection error")
            return sent
        elif type == self.SELECTIVE_REPEAT:
            return self._send_selective_repeat(data)
        else:
            raise ValueError(f"Unknown sent type: {type}")

    def _send_stop_and_wait(self, flags, data):
        offset = 0
        n = len(data)
        sent_flag = False

        while offset < n or ((flags & (FLAG_ACK | FLAG_FIN)) != 0 and not sent_flag):
            payload = data[offset:offset + PAYLOAD_SIZE]

            attempts = 3                     # ← reset here, per packet
            while attempts > 0:
                send_time = time.time()
                self._send_packet(flags, payload)

                timeout = self.rto_estimator.get_timeout()
                logger.vprint(f"\n[Sender] Timeout: {timeout}\n")
                header,_ , _ = self._receive_packet(timeout)
                expected_ack = self.seq_num + len(payload)
                if header and (header[2] & FLAG_ACK) and header[1] >= expected_ack:
                    rtt_sample = time.time() - send_time
                    self.rto_estimator.note_sample(rtt_sample)

                    self.seq_num = header[1]
                    if len(payload) == 0:
                        sent_flag = True

                    if header[1] == expected_ack:
                        offset += len(payload)
                    else:
                        offset += header[1] - expected_ack

                    logger.vprint(f"\n[Sender] RTT sample={rtt_sample:.4f}s, new RTO={self.rto_estimator.get_timeout():.4f}s\n")
                    break
                else:
                    logger.vprint("Timeout o incorrect ACK. Retransmitting packet reliably...")
                    self.rto_estimator.backoff()

                    logger.vprint(f"\n[Sender] Backoff applied. New RTO={self.rto_estimator.get_timeout():.4f}s (remaining attempts={attempts})\n")
                    attempts -= 1

            if attempts == 0:
                return False, offset

        return True, None

    def _recv_stop_and_wait(self, buffer_size):
        if not self.is_connected:
            return b""

        expected_seq = self.ack_num
        received_data = bytearray()
        deadline = time.monotonic() + IDLE_TIME

        # ack 5

        while True:
            remaining = max(0.0, deadline - time.monotonic())
            header, data, _ = self._receive_packet(timeout=remaining if remaining > 0 else 0)
            if not header:
                # idle timeout?
                if time.monotonic() >= deadline:
                    logger.vprint("Idle timeout in recv Stop&Wait. Closing.")
                    self.is_connected = False
                    return None, bytes(received_data)
                # spurious/short packet case: continue waiting
                continue

            # reset idle timer on any valid packet
            deadline = time.monotonic() + IDLE_TIME

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
                    logger.vprint(f"Unexpected SEQ {seq_num}. Resending last ACK.")
                    self._send_packet(FLAG_ACK, b"")

            elif header[2] & FLAG_FIN:
                logger.vprint("Recibido FIN. Cerrando.")
                self.ack_num = header[0] + 1
                return None, bytes(received_data)

            else:
                logger.vprint(f"Unexpected packet with SEQ={seq_num}. Ignoring.")

    def _receive_reliable_packet(self, payload_size, expected_flags=0, type=STOP_AND_WAIT):
        buffer_size = payload_size
        # Seleccionar el método de recepción según el tipo solicitado.
        if type == self.STOP_AND_WAIT:
            return self._recv_stop_and_wait(buffer_size)
        elif type == self.SELECTIVE_REPEAT:
            return self._recv_selective_repeat(buffer_size)
        else:
            raise ValueError(f"Unknown type of reception: {type}")


    def _send_selective_repeat(self, data: bytes):
        if not self.is_connected:
            return False

        window_bytes = WINDOW_SIZE * PAYLOAD_SIZE

        data_len = len(data)
        data_end_seq = self.seq_num + data_len

        send_base = self.seq_num           # lowest unacked absolute seq
        next_seq  = self.seq_num           # next absolute seq to send

        # in_flight: seq -> { "data": bytes, "sent": float, "attempts": int }
        in_flight = {}

        attempts_limit = 10  # per-segment cap to avoid infinite retries

        while send_base < data_end_seq or in_flight:
            # 1. Fill the window
            while next_seq < data_end_seq and next_seq < send_base + window_bytes:
                off = next_seq - self.seq_num
                chunk = data[off : off + PAYLOAD_SIZE]
                if not chunk:
                    break

                self._send_packet(FLAG_PSH, chunk)
                in_flight[next_seq] = {
                    "data": chunk,
                    "sent": time.time(),
                    "attempts": 1,
                }
                logger.vprint(f"[SR] Sent chunk SEQ={next_seq} LEN={len(chunk)}")
                next_seq += len(chunk)

            # 2.Compute the nearest timer expiry for blocking receive
            if in_flight:
                now = time.time()
                rto = self.rto_estimator.get_timeout()
                # time left for each in-flight seg
                min_left = min(max(0.0, (seg["sent"] + rto) - now) for seg in in_flight.values())
            else:
                # Nothing in flight, but still have data to send (rare). Don't block long.
                min_left = 0.05

            # 3x. Wait for an ACK up to the nearest timeout
            header, _, _ = self._receive_packet(timeout=min_left)

            if header and (header[2] & FLAG_ACK):
                ack_val = header[1]  # cumulative next expected by receiver
                # Only process forward progress
                if ack_val > send_base:
                    # Use the oldest newly-acked segment to compute RTT
                    now = time.time()
                    # Collect acks to remove (seq < ack_val)
                    acked_seqs = sorted([seq for seq in in_flight.keys() if seq < ack_val])
                    if acked_seqs:
                        oldest_seq = acked_seqs[0]
                        # RTT sample from that segment
                        rtt_sample = now - in_flight[oldest_seq]["sent"]
                        self.rto_estimator.note_sample(rtt_sample)
                        logger.vprint(f"[SR] ACK advanced to {ack_val}, RTT={rtt_sample:.4f}, RTO={self.rto_estimator.get_timeout():.4f}")

                    # Drop all fully acked segments
                    for seq in acked_seqs:
                        in_flight.pop(seq, None)

                    # Slide the window
                    send_base = ack_val
                    self.seq_num = ack_val  # keep sender seq in sync with peer’s cumulative ACK
                else:
                    # Duplicate/old ACK -> ignore (optionally count for fast retransmit)
                    logger.vprint(f"[SR] Dup/old ACK={ack_val} (base={send_base})")
            else:
                # 4. Timeout path: retransmit any expired segments (oldest first to be gentle)
                if in_flight:
                    now = time.time()
                    rto = self.rto_estimator.get_timeout()

                    # Find expired segments
                    expired = sorted(
                        (seq for seq, seg in in_flight.items() if now - seg["sent"] >= rto)
                    )
                    if expired:
                        # Retransmit the earliest expired one first (avoid burst)
                        seq = expired[0]
                        seg = in_flight[seq]
                        if seg["attempts"] >= attempts_limit:
                            logger.vprint(f"[SR] Attempts exceeded for SEQ={seq}. Aborting.")
                            return False

                        self._send_packet(FLAG_PSH, seg["data"])
                        seg["sent"] = time.time()
                        seg["attempts"] += 1
                        # Apply backoff once per expiry event
                        self.rto_estimator.backoff()
                        logger.vprint(f"[SR] Retransmit SEQ={seq} (attempt {seg['attempts']}), new RTO={self.rto_estimator.get_timeout():.4f}")
                    # else: no expired (race with receive timeout); loop again
                # else: nothing in flight; loop will refill window

    def _recv_selective_repeat(self, buffer_size: int):
        if not self.is_connected:
            return None, b""

        expected_seq_from_client = self.ack_num           # next in-order byte we want
        received_data = bytearray()
        buffer = {}                           # seq -> bytes (out-of-order)
        window_bytes = WINDOW_SIZE * PAYLOAD_SIZE

        deadline = time.monotonic() + IDLE_TIME

        while True:
            remaining = max(0.0, deadline - time.monotonic())
            header, data, _ = self._receive_packet(timeout=remaining if remaining > 0 else 0)
            if not header:
                if time.monotonic() >= deadline:
                    logger.vprint("Idle timeout in recv SR. Closing.")
                    self.is_connected = False
                    return None, bytes(received_data)
                continue

            # reset idle timer on any valid packet
            deadline = time.monotonic() + IDLE_TIME

            seq = header[0]
            flags = header[2]

            # Control messages used in the handshake payload path 
            if (flags & FLAG_OP) or (flags & FLAG_FNAME):
                if seq == expected_seq_from_client:
                    received_data.extend(data)
                    expected_seq_from_client += len(data)
                    self.ack_num = expected_seq_from_client
                    self._send_packet(FLAG_ACK)
                    return header, bytes(received_data)
                else:
                    # Out-of-order control payload → buffer and ACK cumulative expected
                    if expected_seq_from_client <= seq < expected_seq_from_client + window_bytes and seq not in buffer:
                        buffer[seq] = data
                    self.ack_num = expected_seq_from_client
                    self._send_packet(FLAG_ACK)
                    # keep waiting until we can deliver in order
                    continue

            # Data path (PSH) 
            if flags & FLAG_PSH:
                if seq == expected_seq_from_client:
                    # in-order: deliver and drain any contiguous buffered chunks
                    received_data.extend(data)
                    expected_seq_from_client += len(data)

                    # promote buffered contiguous data
                    while expected_seq_from_client in buffer:
                        chunk = buffer.pop(expected_seq_from_client)
                        received_data.extend(chunk)
                        expected_seq_from_client += len(chunk)

                    self.ack_num = expected_seq_from_client
                    self._send_packet(FLAG_ACK)

                    if len(received_data) >= buffer_size:
                        return header, bytes(received_data)
                    continue

                # Out-of-order but inside window → buffer, ACK cumulative
                if expected_seq_from_client <= seq < expected_seq_from_client + window_bytes:
                    if seq not in buffer:
                        buffer[seq] = data
                        logger.vprint(f"[SR] Buffered out-of-order SEQ={seq} LEN={len(data)}")
                    # Even if we got further data, cumulative ACK remains the left edge
                    self.ack_num = expected_seq_from_client
                    self._send_packet(FLAG_ACK)
                    continue

                # Too old or outside window → just re-ACK current expected
                logger.vprint(f"[SR] SEQ={seq} out of window (expected={expected_seq_from_client}). Re-ACKing.")
                self.ack_num = expected_seq_from_client
                self._send_packet(FLAG_ACK)
                continue

            # Connection teardown
            if flags & FLAG_FIN:
                logger.vprint("FIN received (SR). Closing.")
                self.ack_num = seq + 1
                self._send_packet(FLAG_ACK | FLAG_FIN)
                self.is_connected = False
                return None, bytes(received_data)

            # Anything else
            logger.vprint(f"[SR] Unexpected packet flags={bin(flags)} SEQ={seq}. Ignoring (ACK last).")
            self.ack_num = expected_seq_from_client
            self._send_packet(FLAG_ACK)
    def __del__(self):
        self.close()
