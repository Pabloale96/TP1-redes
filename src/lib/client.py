import socket
import struct
from enum import IntEnum


class Flags(IntEnum):
    DATA = 0
    ACK = 1
    FIN = 2


BUFFER_SIZE = 1024  # tamaño recomendado para evitar fragmentacion 
TIMEOUT = 1
SIZE_HEADER = 7


class client:
    def __init__(self, addr, port):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addr = addr
        self.port = port
        self.socket.settimeout(TIMEOUT)

    def close(self):
        self.socket.close()

    def upload(self, filepath, filename):
        print("uploading")
        seq = 0
        filename = "archivo.bin"
        with open(filename, "rb") as f:
            while True:
                chunk = f.read(BUFFER_SIZE)
                if not chunk:
                    break
    # header: tipo de paquete [ data = 0, ack = 1, fin = 2 ], numero de secuencia, longitud del paquete  
                paquete = struct.pack("!B I H", Flags.DATA, seq, len(chunk)) + chunk  # armo paquete header + payload (de a 1024 bytes)
                while True:
                    self.socket.sendto(paquete, (self.addr, self.port))  # lo envio
                    print(f"enviado paquete {seq}, {len(chunk)} bytes")
                    try:
                        ack, _ = self.socket.recvfrom(SIZE_HEADER)  # recibo el ack del paquete enviado
                        tipo, ack_seq, _ = struct.unpack("!B I H", ack)
                        if tipo == 1 and ack_seq == seq:  # ack de recepcion del chunk -> incremento seq
                            print(f"ack recibido {ack_seq}")
                            seq += 1
                            break
                    except socket.timeout:
                        print("timeout, reintentando")

        fin_pkt = struct.pack("!B I H", Flags.FIN, seq, 0)  # termine de mandar los chunks envio FIN
        while True:
            self.socket.sendto(fin_pkt, (self.addr, self.port))
            try:
                ack, _ = self.socket.recvfrom(SIZE_HEADER)  # ack de recepcion del FIN
                tipo, ack_seq, _ = struct.unpack("!B I H", ack)
                if tipo == 1 and ack_seq == seq:
                    print("FIN confirmado")
                    break
            except socket.timeout:
                print("reenviando FIN")
        self.socket.close()

    def download(self, filepath, filename):
        print("Downloaded")
