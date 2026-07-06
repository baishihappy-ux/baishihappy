from dataclasses import asdict, dataclass
import time


def clamp(value, low, high):
    return max(low, min(high, value))


@dataclass
class SystemStateVector:
    queue_pressure: float = 0.0
    failure_density: float = 0.0
    provider_health: float = 1.0
    concurrency_load: float = 1.0
    session_stability: float = 1.0
    throughput_rate: float = 0.0
    retry_delay_seconds: float = 0.2
    chain_length_limit: int = 1
    provider_weight: float = 1.0
    last_updated_at: float = 0.0

    def normalize(self):
        self.queue_pressure = clamp(self.queue_pressure, 0.0, 1.0)
        self.failure_density = clamp(self.failure_density, 0.0, 1.0)
        self.provider_health = clamp(self.provider_health, 0.0, 1.0)
        self.concurrency_load = clamp(self.concurrency_load, 1.0, 128.0)
        self.session_stability = clamp(self.session_stability, 0.0, 1.0)
        self.throughput_rate = max(0.0, self.throughput_rate)
        self.retry_delay_seconds = clamp(self.retry_delay_seconds, 0.0, 120.0)
        self.chain_length_limit = int(clamp(self.chain_length_limit, 0, 16))
        self.provider_weight = clamp(self.provider_weight, 0.01, 1.0)
        self.last_updated_at = time.time()
        return self

    def effective_rate(self) -> float:
        # Required T1 equation: R(t) = C(t) * P(t) * H(t)
        return self.concurrency_load * self.provider_health * self.session_stability

    def to_dict(self):
        return asdict(self)


