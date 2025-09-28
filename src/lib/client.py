import socket
import struct

TIMEOUT = 0.01

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


class client:
    def __init__(self, addr, port):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addr = addr
        self.port = port
        self.socket.settimeout(TIMEOUT)

    def close(self):
        self.socket.close()

    def upload(self, filepath, filename, protocol):
        print("uploading")
        seq = 0
        self.syn(UPLOAD, protocol, filename)
        if protocol == STOP_AND_WAIT:
            self.stopandwait(seq, filepath, filename)

        self.fin(UPLOAD, protocol, seq)

    def download(self, filepath, filename, protocol):
        print("Downloaded")
        self.syn(DOWNLOAD, protocol, filepath, filename)

    def syn(self, type, protocol, filename):
        syn_pkt = struct.pack(FORMAT, type, protocol, 0, 0, SYN, len(filename)) + filename.encode()  # mando SYN
        while True:
            self.socket.sendto(syn_pkt, (self.addr, self.port))
            try:
                ack, _ = self.socket.recvfrom(HEADER_SIZE)  # ack de recepcion del SYN
                _, _, ack_seq, _, flags, _ = struct.unpack(FORMAT, ack)
                if flags == SYN:
                    print("SYN confirmado")
                    break
            except socket.timeout:
                print("reenviando SYN")

    def fin(self, type, protocol, seq):
        fin_pkt = struct.pack(FORMAT, type, protocol, seq, 0, FIN, 0)  # termine de mandar los chunks envio FIN
        while True:
            self.socket.sendto(fin_pkt, (self.addr, self.port))
            try:
                ack, _ = self.socket.recvfrom(HEADER_SIZE)  # ack de recepcion del FIN
                _, _, ack_seq, _, flags, _ = struct.unpack(FORMAT, ack)
                if flags == ACK and ack_seq == seq:
                    print("FIN confirmado")
                    break
            except socket.timeout:
                print("reenviando FIN")
        self.socket.close()

    def stopandwait(self, seq, filepath, filename):
        with open(filepath + filename, "rb") as f:
            while True:
                chunk = f.read(PAYLOAD_SIZE)
                if not chunk:
                    break

                paquete = struct.pack(FORMAT, UPLOAD,  STOP_AND_WAIT, seq, 0, DATA, len(chunk)) + chunk  # armo paquete header + payload (de a 1024 bytes)
                while True:
                    self.socket.sendto(paquete, (self.addr, self.port))  # lo envio
                    print(f"enviado paquete {seq}, {len(chunk)} bytes")
                    try:
                        ack, _ = self.socket.recvfrom(HEADER_SIZE)  # recibo el ack del paquete enviado
                        _, _, ack_seq, _, flags, _ = struct.unpack(FORMAT, ack)
                        if flags == ACK and ack_seq == seq:  # ack de recepcion del chunk -> incremento seq
                            print(f"ack recibido {ack_seq}")
                            seq += 1
                            break
                    except socket.timeout:
                        print("timeout, reintentando")
