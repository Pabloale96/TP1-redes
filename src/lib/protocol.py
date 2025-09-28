#from lib.file_manager import FileManager
#from lib.sockets import Socket
import struct
import socket
import threading
import time
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

PAYLOAD_SIZE = 1024

PACKET_SIZE = HEADER_SIZE + PAYLOAD_SIZE  # = 1024 + 9 bytes

TIMEOUT = 0.01

WINDOW_SIZE = 100

class Protocol:
    """
        clase que define el protocolo y se encarga de la administración de los paquetes
    """
    def __init__(self, addr, port, type: int = 0, mode: int = 0, filename="", verbose=False, quiet=True, storage_path=""): 
        """
            Constructor de la clase protocol
            - addr: address para establecer la conección
            - port: port para establecer la conección
            - verbose: modo detallado
            - quiet: modo silencioso

            Argumentos para la creación desde cliente:
            - type: tipo de transferencia (stop and wait / selective repeat)
            - mode: tipo de acción que se quiere realizar (upload / download)
            - filename: nombre del archivo que se quiere observar

            Argumentos para la creación desde servidor:
            - storage_path: dirección del almacenamiento del servidors # el cliente usa filepath

            
        """
        self.file_name = filename
        self.storage_path = storage_path
        self.addr = addr
        self.port = port

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(TIMEOUT)

        self.verbose = verbose
        self.quiet = quiet
        self.transmission_type = type
        
        self.seq_number = 0
        self.ack = 0
        self.mode = mode

        self.base = 0
        self.next_seq = 0
        self.acks = {}
        self.lock = threading.Lock()
        self.ack_thread = threading.Thread(target=self.ack_listener)

    def send(self, payload: bytes):
        """
            Función para el cliente UPLOAD.
            Se envía un paquete de datos
        """

        packet = self.make_packet(payload, DATA)        
        self.socket.sendto(packet, self.addr)

    def rcv(self):
        """
            Función para el cliente DOWNLOAD
            Envía un paquete donde el payload es el archivo que se quiere recibir y recibe la data.
        """

        # Se envía el paquete pidiendo la información
        file_packet = self.make_packet(self.file_name.encode(), DATA)
        self.socket.sendto(file_packet, self.addr)

        # Se recibe el paquete con el paquete del archivo indicado
        packet = self.socket.recvfrom(PACKET_SIZE)

        return self.receive_packet(packet)

    def start_conection(self):
        """Función para indicar que tipo de transmición que se quiere utilizar. Más que todo para indicarle al server
            el tipo de transmición (STOP AND WAIT / SELECTIVE REPEAT) a utilizar y en caso de querer hacer una descarga 
            el cliente se envía en el payload el nombre del archivo"""
        
        payload = b""
        starting_packet = self.make_packet(payload, SYN)

        while True:
            #se envía el paquete inicial
            self.socket.sendto(starting_packet, self.addr)

            try:
                # Se recibe la respuesta del paquete inicial para poder cómenzar.
                # se devuelve el paquete con el que se responderá, es decir el primer paquete con información.

                received_packet = self.socket.recvfrom(PACKET_SIZE)
                self.receive_packet(received_packet)
                break

            except self.socket.timeout:
                self.__print_info(string_normal="Timeout, Reintentando...")

    def make_packet(self, payload: bytes, flag: int) -> bytes:
        """
            Función que se encarga de crear el paquete que será enviado
            
            - return: Devuelve el paquete a enviar como un objeto bytes
        """
        lenght = len(payload)

        if flag == SYN:
            header = struct.pack(FORMAT, self.mode, self.transmission_type, self.seq_number, self.ack, flag, lenght)
        else:
            seq_number, ack = self.set_seq_number_and_ack(flag)

            header = struct.pack(FORMAT, self.mode, self.transmission_type, seq_number, ack, flag, lenght)

        return header + payload

    def receive_packet(self, packet: bytes):
        """
            Función que se encarga de ejecutar las operaciones necesarias sobre el paquete recibido
            
            - return: Devuelve el paquete con el que se debe responder junto con la data que se recibió
        """
        mode, transmission_type, seq_number, ack, flag, _length, payload = self.parse_packet(packet)
        
        if flag == SYN:
            return self.respond_syn(mode, transmission_type)
        
        if flag == DATA:
            return self.respond_data(seq_number, transmission_type, payload)
        
        if flag == ACK:
            return self.respond_ack(ack)
        
        if flag == FIN:
            return None

    def respond_syn(self, mode, transmission_type):
        self.mode = mode
        self.transmission_type = transmission_type
        return

    def respond_data(self, seq_number, transmission_type, payload):
        """
            Función que se encarga de evaluar la respuesta en caso de que el paquete contenga data

            - raise: En caso de que estemos ejecutando stop and wait, Si no llega el numero de secuencia esperado se levanta la excepción
            - return: devuelve la información recibida
        """
        if transmission_type == STOP_AND_WAIT:
            if seq_number == self.seq_number + 1:
                return payload
            raise Exception("No se obtuvo el paquete esperado...")
        
        return payload
                
    def respond_ack(self, ack):
        """
            Función que se encarga de evaluar los paquetes que tienen el flag ack
            - raise: en caso de que se ejecute stop and wait. Si no llega el ack del paquete esperado se levanta una excepción
            - return: devuelve un entero que simboliza el ack recibido, esto para poder hacer uso del buffer
        """

        if self.transmission_type == STOP_AND_WAIT:
            if ack == self.ack+1:
                self.ack += 1
                return ack
            raise Exception("No se recibió el paquete esperado...")
        return ack

    def parse_packet(self, packet):
        header = packet[:HEADER_SIZE]
        payload = packet[HEADER_SIZE:]

        return struct.unpack(FORMAT, header), payload

    def next_seq_number(self):
        self.seq_number += 1

    def set_seq_number_and_ack(self, flag: int):        
        self.next_seq_number()

        if flag == ACK:
            return 0, self.seq_number
        
        return self.seq_number, 0

    def get_transmission_type(self):
        return self.transmission_type
    
    def get_mode(self):
        return self.mode
    
    def close(self):
        self.socket.close()
    
    def send_syn(self):
        syn_pkt = struct.pack(FORMAT, self.mode, self.transmission_type, 0, 0, SYN, len(self.file_name)) + self.file_name.encode()  # mando SYN
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

    def stopandwait(self):
        with open(self.file_name, "rb") as f:
            while True:
                chunk = f.read(PAYLOAD_SIZE)
                if not chunk:
                    break

                paquete = struct.pack(FORMAT, UPLOAD,  STOP_AND_WAIT, self.seq_number, 0, DATA, len(chunk)) + chunk  # armo paquete header + payload (de a 1024 bytes)
                while True:
                    self.socket.sendto(paquete, (self.addr, self.port))  # lo envio
                    print(f"enviado paquete {self.seq_number}, {len(chunk)} bytes")
                    try:
                        ack, _ = self.socket.recvfrom(HEADER_SIZE)  # recibo el ack del paquete enviado
                        _, _, ack_seq, _, flags, _ = struct.unpack(FORMAT, ack)
                        if flags == ACK and ack_seq == self.seq_number:  # ack de recepcion del chunk -> incremento seq
                            print(f"ack recibido {ack_seq}")
                            self.seq_number += 1
                            break
                    except socket.timeout:
                        print("timeout, reintentando")
        self.fin()

    def fin(self):
        if self.transmission_type == SELECTIVE_REPEAT:
            last_seq = 0  # self.base - 1 
        else:
            last_seq = self.seq_number -1

        fin_pkt = struct.pack(FORMAT, self.mode, self.transmission_type, last_seq, 0, FIN, 0)  # termine de mandar los chunks envio FIN
        while True:
            self.socket.sendto(fin_pkt, (self.addr, self.port))
            try:
                ack, _ = self.socket.recvfrom(HEADER_SIZE)  # ack de recepcion del FIN
                _, _, ack_seq, _, flags, _ = struct.unpack(FORMAT, ack)
                if flags == ACK and ack_seq == last_seq:
                    print("FIN confirmado")
                    break
           # except socket.timeout:
            #    print("reenviando FIN")
            except OSError:
                break  # socket cerrado  
 
    def ack_listener(self):
        while self.running:
            try:
                data, _ = self.socket.recvfrom(HEADER_SIZE)
                modo, tipo, seq, ack, flags, length = struct.unpack(FORMAT, data)
                if flags == ACK:
                    with self.lock:
                        self.acks[seq] = True
                        while self.base in self.acks and self.acks[self.base]:  # si la base de la ventana se confirmo, se mueve la ventana
                            self.base += 1
            except socket.timeout:
                continue

    def selectiverepeat(self):
        # Dividir archivo en chunks
        with open(self.file_name, "rb") as f:
            chunks = []
            while True:
                data = f.read(PAYLOAD_SIZE)
                if not data:
                    break
                chunks.append(data)

        total_chunks = len(chunks)

        # Lanzar hilo ACK listener
        self.running = True
        self.ack_thread.start()

        while self.base < total_chunks:
            # enviar mientras haya espacio en ventana
            while self.next_seq < self.base + WINDOW_SIZE and self.next_seq < total_chunks:
                payload = chunks[self.next_seq]
                paquete = struct.pack(FORMAT, UPLOAD, SELECTIVE_REPEAT, self.next_seq, 0, DATA, len(payload)) + payload
                self.socket.sendto(paquete, (self.addr, self.port))
                print(f"Enviado paquete seq={self.next_seq}, len={len(payload)}")
                self.next_seq += 1

            # retransmitir si no se recibe ACK
            time.sleep(TIMEOUT)
            with self.lock:
                for seq in range(self.base, self.next_seq):
                    if seq not in self.acks:
                        paquete = struct.pack(FORMAT, UPLOAD, SELECTIVE_REPEAT, seq, 0, DATA, len(chunks[seq])) + chunks[seq]
                        self.socket.sendto(paquete, (self.addr, self.port))
                        print(f"Retransmitido paquete seq={seq}")

        self.running = False   
        if self.ack_thread.is_alive():
            self.ack_thread.join() 


