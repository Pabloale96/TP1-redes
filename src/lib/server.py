import socket
import struct
from enum import IntEnum


BUFFER_SIZE = 1024  # tamaño recomendado para evitar fragmentacion 
TIMEOUT = 1
SIZE_HEADER = 7


class Flags(IntEnum):
    DATA = 0
    ACK = 1
    FIN = 2


class server:

    def __init__(self, addr, port):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addr = addr
        self.port = port

    def start(self):
        self.socket.bind((self.addr, self.port))
        with open("recibido.bin", "wb") as f:
            expected_seq = 0
            print("server listo")

            while True:
                data, addr = self.socket.recvfrom(SIZE_HEADER + BUFFER_SIZE)  # size del header + size del bufer = total size
                tipo, seq, length = struct.unpack("!B I H", data[:SIZE_HEADER])  # unpack del 0 al 7
                payload = data[SIZE_HEADER:SIZE_HEADER+length]  # unpack del 8 al final del chunk
                if tipo == 0:  # data
                    if seq == expected_seq:
                        f.write(payload)
                        print(f"recibido paquete {seq},{length} bytes")
                        ack = struct.pack("!B I H", Flags.ACK, seq, 0)
                        self.socket.sendto(ack, addr)  # mando ack del segmento recibido
                        expected_seq += 1
                    else:
                        print(f"duplicado {seq}, reenvio ack")
                        ack = struct.pack("!B I H", Flags.ACK, expected_seq - 1, 0)
                        self.socket.sendto(ack, addr)  # vuelvo a mandar ack (reenviaron algo que ya recibi)
                elif tipo == 2:  # FIN
                    print("transferencia terminada")
                    ack = struct.pack("!B I H", Flags.ACK, seq, 0)
                    self.socket.sendto(ack, addr)  # ack del FIN
                    break
        self.socket.close()
