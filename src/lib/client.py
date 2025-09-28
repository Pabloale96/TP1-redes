from lib.protocol import Protocol
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


class client:
    def __init__(self, addr, port):
        self.addr = addr
        self.port = port

    def upload(self, filepath, filename, protocol):
        self.filepath = filepath
        self.filename = filename
        self.protocol = protocol
        self.protocolo = Protocol(self.addr, self.port, protocol, UPLOAD, filename, False, True, filepath)
        self.protocolo.send_syn()

        if protocol == STOP_AND_WAIT:
            self.protocolo.stopandwait()
        if protocol == SELECTIVE_REPEAT:
            self.protocolo.selectiverepeat()
        self.protocolo.fin()
        self.socket.close()            
        
    def download(self, filepath, filename, protocol):
        self.filepath = filepath
        self.filename = filename
        self.protocol = protocol
    
        self.protocolo.send_syn()
        if protocol == STOP_AND_WAIT:
            self.protocolo.stopandwait()
        if protocol == SELECTIVE_REPEAT:
            self.protocolo.selectiverepeat()
        self.protocolo.fin()
        self.socket.close()
