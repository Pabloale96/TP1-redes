import socket
import struct
from lib.protocol import Protocol

TIMEOUT = 0.1

# modos
UPLOAD = 1
DOWNLOAD = 2

# tipo de transmicion
STOP_AND_WAIT = 1
SELECTIVE_REPEAT = 2

# FLAGS
DATA = 0
SYN = 1
ACK = 2
FIN = 3

# Formato del header
# Mode (1byte = B) | Type (1byte = B) | Seq_number (2bytes = H) | ACK (2bytes = H) | Flags (1byte = B) | Length (2bytes = H)
FORMAT = '!BBHHBH'
HEADER_SIZE = struct.calcsize(FORMAT)

PAYLOAD_SIZE = 1024  # tamaño recomendado para evitar fragmentacion

PACKET_SIZE = HEADER_SIZE + PAYLOAD_SIZE  # = 1024 + 9 bytes


class server:

    def __init__(self, addr, port, dirpath):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addr = addr
        self.port = port
        self.dirpath = dirpath

    def start(self):
        self.socket.bind((self.addr, self.port))
        received_data = []
        expected_seq = 0
        buffer = {}
        print("server listo")

        while True:
            data, addr = self.socket.recvfrom(PACKET_SIZE)  # size del header + size del bufer = total size
            modo, tipo, seq, _, flags, length = struct.unpack(FORMAT, data[:HEADER_SIZE])  # unpack del header
            payload = data[HEADER_SIZE:HEADER_SIZE+length]  # unpack datos del chunk
            if modo == UPLOAD and tipo == STOP_AND_WAIT:
                if flags == SYN:
                    ack = struct.pack(FORMAT, modo, tipo, seq, 0, SYN, 0)
                    self.socket.sendto(ack, addr)  # ack del SYN
                    filename = payload.decode()
                elif flags == DATA:  # data
                    if seq == expected_seq:
                        received_data.append(payload)
                        print(f"recibido paquete {seq},{length} bytes from:{addr}")
                        ack = struct.pack(FORMAT, modo, tipo, seq, 0, ACK, 0)
                        self.socket.sendto(ack, addr)  # mando ack del segmento recibido
                        expected_seq += 1
                    else:
                        print(f"duplicado {seq}, reenvio ack")
                        ack = struct.pack(FORMAT, modo, tipo, expected_seq - 1, 0, ACK, 0)
                        self.socket.sendto(ack, addr)  # vuelvo a mandar ack (reenviaron algo que ya recibi)
                elif flags == FIN:  # FIN
                    print(f"transferencia terminada del archivo:{filename}")
                    ack = struct.pack(FORMAT, modo, tipo, seq, 0, ACK, 0)
                    self.socket.sendto(ack, addr)  # ack del FIN
                    file = b''.join(received_data)
                    with open(self.dirpath + filename, 'wb') as f:
                        f.write(file)
                    break

            if modo == UPLOAD and tipo == SELECTIVE_REPEAT:
                if flags == SYN:
                    filename = payload.decode()
                    ack = struct.pack(FORMAT, modo, tipo, seq, 0, SYN, 0)
                    self.socket.sendto(ack, addr)

                elif flags == DATA:
                    print(f"DATA recibido seq={seq}, len={len(payload)}")
                    buffer[seq] = payload
                    # mandar ACK
                    ack = struct.pack(FORMAT, modo, tipo, seq, 0, ACK, 0)
                    self.socket.sendto(ack, addr)
                    print(f"ACK enviado seq={seq}")

                    # escribir consecutivos en archivo virtual
                    while expected_seq in buffer:
                        received_data.append(buffer.pop(expected_seq))
                        expected_seq += 1

                elif flags == FIN:
                    print(f"Transferencia terminada archivo={filename}")
                    ack = struct.pack(FORMAT, modo, tipo, seq, 0, ACK, 0)
                    self.socket.sendto(ack, addr)
                    file = b''.join(received_data)
                    with open(self.dirpath + filename, 'wb') as f:
                        f.write(file)
                    break
                
            if modo == DOWNLOAD and tipo == SELECTIVE_REPEAT:
                if flags == SYN:
                    ack = struct.pack(FORMAT, modo, tipo, seq, 0, SYN, 0)
                    self.socket.sendto(ack, addr)  # ack del SYN
                    filename = payload.decode()

            if modo == DOWNLOAD and tipo == STOP_AND_WAIT:
                if flags == SYN:
                    ack = struct.pack(FORMAT, modo, tipo, seq, 0, SYN, 0)
                    self.socket.sendto(ack, addr)  # ack del SYN
                    filename = payload.decode()
        self.socket.close()
