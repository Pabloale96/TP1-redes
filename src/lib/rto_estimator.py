import time

class RTOEstimator:
    def __init__(self, alpha=1/8, beta=1/4, k=4, g=0.001):
        # RFC 6298 parámetros
        self.alpha = alpha
        self.beta = beta
        self.k = k
        self.g = g  # granularidad de clock en segundos

        # Estado
        self.srtt = None
        self.rttvar = None
        self.rto = 1.0  # valor inicial por RFC: 1 segundo

    def note_sample(self, rtt_sample: float):
        """Actualizar estimador con un nuevo RTT medido (en segundos)."""
        if self.srtt is None:
            # Primer RTT
            self.srtt = rtt_sample
            self.rttvar = rtt_sample / 2
        else:
            # Subsigientes
            self.rttvar = (1 - self.beta) * self.rttvar + self.beta * abs(self.srtt - rtt_sample)
            self.srtt = (1 - self.alpha) * self.srtt + self.alpha * rtt_sample

        self.rto = self.srtt + max(self.g, self.k * self.rttvar)
        # Proteger: mínimo 200ms, máximo 60s
        self.rto = min(max(self.rto, 0.2), 60.0)

    def get_timeout(self) -> float:
        """Devolver RTO actual (en segundos)."""
        return self.rto

    def backoff(self):
        """Exponential backoff cuando un timeout expira."""
        self.rto = min(self.rto * 2, 60.0)
