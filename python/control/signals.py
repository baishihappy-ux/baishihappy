from dataclasses import asdict, dataclass


@dataclass
class ControlSignal:
    concurrency_target: int
    retry_delay_seconds: float
    provider_weight_delta: float
    fallback_required: bool
    rebuild_session_chain: bool
    chain_length_limit: int
    burst_mode: bool
    scheduler_bias: dict

    def to_dict(self):
        return asdict(self)
