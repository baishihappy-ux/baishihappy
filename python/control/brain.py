from collections import deque
import time

from python.control.signals import ControlSignal
from python.control.state_vector import SystemStateVector, clamp


class FeedbackLoopEngine:
    def __init__(self, config: dict):
        processing = config.get("processing", {})
        base_concurrency = int(processing.get("thread_count") or processing.get("smart_session_stage_mixer_entry_per_min", 12) / 6 or 2)
        max_depth = int(processing.get("max_depth", 1))
        self.state = SystemStateVector(concurrency_load=max(1, base_concurrency), chain_length_limit=max_depth)
        self.events = deque(maxlen=256)
        self.k1 = float(processing.get("control_k1", 0.35))
        self.k2 = float(processing.get("control_k2", 0.25))
        self.k3 = float(processing.get("control_k3", 0.35))
        self.k4 = float(processing.get("control_k4", 0.18))
        self.max_concurrency = int(processing.get("control_max_concurrency", processing.get("thread_count") or 16) or 16)
        self.min_concurrency = int(processing.get("control_min_concurrency", 1))
        self.window_seconds = float(processing.get("smart_session_stage_mixer_window_ms", 60000)) / 1000.0
        self.last_signal = None

    def record(self, event_type: str, **fields):
        self.events.append({"ts": time.time(), "type": event_type, **fields})

    def update_metrics(self, queue_depth: int, active_workers: int, provider_snapshot: dict, session_snapshot: dict):
        now = time.time()
        window_start = now - max(1.0, self.window_seconds)
        recent = [e for e in self.events if e["ts"] >= window_start]
        completed = sum(1 for e in recent if e["type"] == "task_success")
        failed = [e for e in recent if e["type"] == "task_failure"]
        timeouts_or_502 = [e for e in failed if e.get("status_code") in {0, 502, 504} or "timeout" in (e.get("reason") or "").lower()]
        chain_breaks = [e for e in recent if e["type"] == "session_chain_break"]
        recoveries = [e for e in recent if e["type"] == "session_recovered"]
        total = max(1, completed + len(failed))

        self.state.queue_pressure = queue_depth / max(1.0, queue_depth + active_workers + 1.0)
        self.state.failure_density = len(failed) / total
        self.state.provider_health = float(provider_snapshot.get("active_health", self.state.provider_health))
        self.state.session_stability = float(session_snapshot.get("stability", self.state.session_stability))
        self.state.throughput_rate = completed / max(1.0, self.window_seconds)

        failure_spike = len(timeouts_or_502) / total
        chain_break = len(chain_breaks) / total
        recovery = len(recoveries) / total
        effective_r = self.state.effective_rate()

        # Required T1 equations:
        # C(t+1) = C(t) + k1*(R - F)
        self.state.concurrency_load = self.state.concurrency_load + self.k1 * (effective_r - self.state.failure_density)
        # P(t+1) = P(t) - k2*failure_spike
        self.state.provider_health = self.state.provider_health - self.k2 * failure_spike
        # H(t+1) = H(t) - k3*chain_break + k4*recovery
        self.state.session_stability = self.state.session_stability - self.k3 * chain_break + self.k4 * recovery

        # Failure-driven control.
        if self.state.failure_density > 0.15:
            self.state.concurrency_load -= self.k1 * (1.0 + self.state.failure_density)
            self.state.retry_delay_seconds = max(self.state.retry_delay_seconds * 1.5, 1.0)
            self.state.provider_weight -= self.k2 * self.state.failure_density
        else:
            self.state.retry_delay_seconds *= 0.9
            self.state.provider_weight += 0.03

        # Throughput feedback burst mode.
        if self.state.throughput_rate > self.state.failure_density and self.state.queue_pressure > 0.1:
            self.state.concurrency_load += self.k1 * (1.0 + self.state.throughput_rate)

        # Provider health control.
        if failure_spike > 0.2:
            self.state.provider_weight -= self.k2 * (1.0 + failure_spike)

        # Session stability control.
        if chain_break > 0:
            self.state.chain_length_limit = max(0, self.state.chain_length_limit - 1)
        elif recovery > 0 and self.state.session_stability > 0.75:
            self.state.chain_length_limit += 1

        self.state.concurrency_load = clamp(self.state.concurrency_load, self.min_concurrency, self.max_concurrency)
        self.state.normalize()
        self.last_signal = self.generate_signal(failure_spike, chain_break)
        return self.last_signal

    def generate_signal(self, failure_spike=0.0, chain_break=0.0) -> ControlSignal:
        burst = self.state.throughput_rate > self.state.failure_density and self.state.queue_pressure > 0.25
        fallback = self.state.provider_health < 0.45 or failure_spike > 0.2
        rebuild = self.state.session_stability < 0.65 or chain_break > 0
        bias = {
            "queue_pressure": self.state.queue_pressure,
            "failure_penalty": self.state.failure_density,
            "provider_health": self.state.provider_health,
            "session_stability": self.state.session_stability,
        }
        return ControlSignal(
            concurrency_target=int(round(self.state.concurrency_load)),
            retry_delay_seconds=self.state.retry_delay_seconds,
            provider_weight_delta=self.state.provider_weight - 1.0,
            fallback_required=fallback,
            rebuild_session_chain=rebuild,
            chain_length_limit=self.state.chain_length_limit,
            burst_mode=burst,
            scheduler_bias=bias,
        )

    def snapshot(self):
        return {
            "state_vector": self.state.to_dict(),
            "signal": self.last_signal.to_dict() if self.last_signal else None,
            "equations": {
                "R(t)": "C(t) * P(t) * H(t)",
                "C(t+1)": "C(t) + k1*(R - F)",
                "P(t+1)": "P(t) - k2*failure_spike",
                "H(t+1)": "H(t) - k3*chain_break + k4*recovery",
            },
        }
