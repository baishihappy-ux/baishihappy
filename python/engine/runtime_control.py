import os
import random
import threading
import time
from collections import deque
from pathlib import Path

from python.queue.tasks import TaskStage
from python.utils.runtime_state import append_event, read_json, update_status, write_json


class RunLock:
    def __init__(self, runtime_root: Path, instance_id: str = ""):
        self.instance_id = instance_id or f"runner-{os.getpid()}"
        self.path = runtime_root / "temp" / "run.lock"
        self.acquired = False

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing = read_json(self.path, None)
        recovered = False
        if existing and self._pid_alive(existing.get("pid")):
            return {"ok": False, "active": True, "pid": existing.get("pid"), "path": str(self.path), "reason": "another run is active"}
        if existing:
            recovered = True
        write_json(self.path, {
            "pid": os.getpid(),
            "instance_id": self.instance_id,
            "started_at": time.time(),
            "updated_at": time.time(),
            "recovered_stale_lock": recovered,
        })
        self.acquired = True
        return {"ok": True, "active": False, "recovered_stale_lock": recovered, "path": str(self.path)}

    def heartbeat(self, **fields):
        if not self.acquired:
            return
        payload = read_json(self.path, {}) or {}
        payload.update({"pid": os.getpid(), "instance_id": self.instance_id, "updated_at": time.time(), **fields})
        write_json(self.path, payload)

    def release(self):
        if not self.acquired:
            return
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
        self.acquired = False

    @staticmethod
    def _pid_alive(pid):
        try:
            parsed = int(pid or 0)
        except (TypeError, ValueError):
            return False
        if parsed <= 0:
            return False
        try:
            os.kill(parsed, 0)
            return True
        except OSError:
            return False


class RuntimeControl:
    def __init__(self, runtime_root: Path, state_dir: Path, config: dict, instance_id: str = ""):
        self.runtime_root = runtime_root
        self.state_dir = state_dir
        self.config = config
        self.processing = config.get("processing", {})
        self.runtime = config.get("runtime", {})
        self.control_path = state_dir / "control.json"
        self.pause_control_path = state_dir / "pause_control.json"
        self.circuit_path = state_dir / "circuit_breaker.json"
        self.lock = RunLock(runtime_root, instance_id)
        self.started_at = time.time()
        self.stage_releases = {stage: deque() for stage in TaskStage}
        self.request_window = deque()
        self.save_window = deque()
        self.status_window = deque()
        self.elapsed_window = deque()
        self.status_elapsed_window = deque()
        self.stage_wait_window = deque()
        self.do_wait_window = deque()
        self.consecutive_502 = 0
        self.inflight_current = 0
        self.inflight_peak = 0
        self.do_wait_count = 0
        self.do_wait_ms = 0
        self.request_count_total = 0
        self.error_502_count = 0
        self.timeout_count = 0
        self.target_site_429_count = 0
        self.do_concurrency_429_count = 0
        self.unknown_429_count = 0
        self.last_retry_after_ms = 0
        self.gear = "STARTUP"
        self.authorized_concurrency = int(self.runtime.get("authorized_concurrency") or self.processing.get("thread_count") or 32)
        self.do_target = max(1, min(self.authorized_concurrency, int(self.runtime.get("do_inflight_target") or self.authorized_concurrency)))
        self.do_hard_limit = max(self.do_target, int(self.runtime.get("do_inflight_hard_limit") or self.authorized_concurrency))
        self.ramp_next_at = time.time() + 8.0
        self.brake_until = 0.0
        self.circuit_open = False
        self.mutex = threading.RLock()
        self.gate_changed = threading.Condition(self.mutex)

    def acquire_lock(self):
        result = self.lock.acquire()
        if result.get("ok") and result.get("recovered_stale_lock"):
            append_event(self.state_dir, "stale_run_lock_recovered", lock_path=result.get("path"))
        return result

    def release_lock(self):
        self.lock.release()

    def heartbeat(self, **fields):
        self.lock.heartbeat(**fields)

    def control_state(self):
        return read_json(self.control_path, {}) or {}

    def pause_requested(self):
        control = self.control_state()
        pause_control = read_json(self.pause_control_path, {}) or {}
        return bool(control.get("paused") or pause_control.get("pause_requested") or pause_control.get("stop_new_seed_requested"))

    def current_inflight(self):
        with self.mutex:
            return self.inflight_current

    def wait_if_paused(self):
        if not self.pause_requested():
            return False
        update_status(self.state_dir, status="PAUSED", pause_requested=True, do_inflight_current=self.current_inflight())
        append_event(self.state_dir, "pause_stop_new_seed_waiting")
        while self.pause_requested():
            time.sleep(0.5)
            self.heartbeat(paused=True)
        update_status(self.state_dir, status="RUNNING", pause_requested=False)
        append_event(self.state_dir, "run_resumed")
        return True

    def wait_for_release(self, stage: TaskStage):
        self.wait_if_paused()
        started_wait = time.time()
        while True:
            with self.gate_changed:
                if self.circuit_open:
                    return False
                self._trim_windows_locked()
                delay = max(self._stage_delay_locked(stage), self._inflight_delay_locked())
                if delay <= 0:
                    self.stage_releases[stage].append(time.time())
                    self.inflight_current += 1
                    self.inflight_peak = max(self.inflight_peak, self.inflight_current)
                    self._write_gate_status_locked(stage)
                    break
                self.gate_changed.wait(timeout=min(delay, 0.5))
            self.wait_if_paused()
        self._sleep_release_jitter()
        with self.mutex:
            elapsed = max(0.0, time.time() - started_wait)
            self.stage_wait_window.append(elapsed)
            if elapsed > 0.01:
                self.do_wait_count += 1
                self.do_wait_ms += int(elapsed * 1000)
                self.do_wait_window.append(elapsed)
        return True

    def release_inflight(self):
        with self.gate_changed:
            self.inflight_current = max(0, self.inflight_current - 1)
            self.gate_changed.notify_all()

    def record_request(self, status_code: int, ok: bool, elapsed_ms: int = 0):
        with self.gate_changed:
            now = time.time()
            code = int(status_code or 0)
            self.request_count_total += 1
            self.request_window.append(now)
            self.status_window.append((now, code, bool(ok)))
            if elapsed_ms:
                self.elapsed_window.append((now, int(elapsed_ms)))
                if code in {200, 404, 502, 503}:
                    self.status_elapsed_window.append((now, code, int(elapsed_ms)))
            if code == 502:
                self.error_502_count += 1
                self.consecutive_502 += 1
            if code == 0 and not ok:
                self.timeout_count += 1
            if code == 429:
                self.target_site_429_count += 1
            elif ok or code in {200, 404}:
                self.consecutive_502 = 0
            self._apply_brake_and_circuit_locked()
            self.gate_changed.notify_all()

    def record_save(self):
        with self.mutex:
            self.save_window.append(time.time())

    def metrics(self):
        with self.mutex:
            self._trim_windows_locked()
            now = time.time()
            recent_status = list(self.status_window)
            elapsed_values = [value for ts, value in self.elapsed_window if now - ts <= 60]
            elapsed_200_404 = [value for ts, code, value in self.status_elapsed_window if now - ts <= 60 and code in {200, 404}]
            elapsed_502_503 = [value for ts, code, value in self.status_elapsed_window if now - ts <= 60 and code in {502, 503}]
            stage_wait_values = [value for value in self.stage_wait_window]
            do_wait_values = [value for value in self.do_wait_window]
            req_30 = sum(1 for ts, _code, _ok in recent_status if now - ts <= 30)
            err_502_30 = sum(1 for ts, code, _ok in recent_status if code == 502 and now - ts <= 30)
            return {
                "provider_request_rate_per_minute": len(self.request_window),
                "provider_request_count": self.request_count_total,
                "rate_per_minute": len(self.save_window),
                "provider_request_30s_count": req_30,
                "provider_502_30s_count": err_502_30,
                "provider_502_rate_30s": err_502_30 / max(1, req_30),
                "provider_timing_window_count": len(elapsed_values),
                "do_inflight_current": self.inflight_current,
                "do_inflight_target": self.do_target,
                "do_inflight_base_target": self.authorized_concurrency,
                "do_inflight_hard_limit": self.do_hard_limit,
                "do_inflight_peak": self.inflight_peak,
                "do_inflight_wait_count": self.do_wait_count,
                "do_inflight_wait_ms": self.do_wait_ms,
                "do_concurrency_429_count": self.do_concurrency_429_count,
                "target_site_429_count": self.target_site_429_count,
                "unknown_429_count": self.unknown_429_count,
                "last_retry_after_ms": self.last_retry_after_ms,
                "do_inflight_target_recovery_ms": 0,
                "provider_pressure_pause_remaining_ms": 0,
                "scheduler_gear": self.gear,
                "provider_failure_density_brake_active": now < self.brake_until,
                "provider_failure_density_brake_level": 1 if now < self.brake_until else 0,
                "provider_failure_density_brake_remaining_ms": max(0, int((self.brake_until - now) * 1000)),
                "provider_failure_density_requests": len(recent_status),
                "provider_failure_density_failures": sum(1 for _ts, code, ok in recent_status if (not ok) or code in {0, 502, 503, 504}),
                "provider_failure_density_rate": sum(1 for _ts, code, ok in recent_status if (not ok) or code in {0, 502, 503, 504}) / max(1, len(recent_status)),
                "provider_502_consecutive": self.consecutive_502,
                "circuit_breaker_open": self.circuit_open,
                "started_at": self.started_at,
                "provider_elapsed_avg_ms": _avg(elapsed_values),
                "provider_elapsed_p95_ms": _p95(elapsed_values),
                "provider_stage_wait_avg_ms": int(_avg(stage_wait_values) * 1000),
                "provider_do_wait_avg_ms": int(_avg(do_wait_values) * 1000),
                "provider_outbound_elapsed_avg_ms": _avg(elapsed_values),
                "provider_warmup_elapsed_avg_ms": 0,
                "provider_resultphone_elapsed_avg_ms": _avg(elapsed_values),
                "provider_200_404_elapsed_avg_ms": _avg(elapsed_200_404),
                "provider_502_503_elapsed_avg_ms": _avg(elapsed_502_503),
                "error_502_count": self.error_502_count,
                "timeout_count": self.timeout_count,
            }

    def update_ramp(self):
        with self.gate_changed:
            now = time.time()
            if now < self.ramp_next_at or self.circuit_open or now < self.brake_until:
                return
            if self.do_target < self.do_hard_limit:
                self.do_target = min(self.do_hard_limit, self.do_target + max(1, self.authorized_concurrency // 8))
                self.gear = "RAMP_UP"
                append_event(self.state_dir, "scheduler_ramp_up", do_inflight_target=self.do_target)
            else:
                self.gear = "CRUISE"
            self.ramp_next_at = now + 10.0
            self.gate_changed.notify_all()

    def open_circuit(self, reason: str):
        with self.gate_changed:
            self._open_circuit_locked(reason)
            self.gate_changed.notify_all()

    def _open_circuit_locked(self, reason: str):
        if self.circuit_open:
            return
        self.circuit_open = True
        self.gear = "CIRCUIT_BREAKER"
        write_json(self.circuit_path, {"open": True, "reason": reason, "opened_at": time.time(), "consecutive_502": self.consecutive_502})
        write_json(self.control_path, {"paused": True, "reason": reason, "circuit_breaker": True, "updated_at": time.time()})
        append_event(self.state_dir, "provider_502_circuit_breaker", reason=reason)

    def _apply_brake_and_circuit_locked(self):
        now = time.time()
        recent = [(ts, code, ok) for ts, code, ok in self.status_window if now - ts <= 30]
        if self.consecutive_502 >= 12:
            self._open_circuit_locked("连续502触发熔断")
            return
        if not recent:
            return
        failures = sum(1 for _ts, code, ok in recent if (not ok) or code in {0, 502, 503, 504})
        density = failures / max(1, len(recent))
        if density >= 0.35 and len(recent) >= 6:
            old_target = self.do_target
            self.do_target = max(1, int(self.do_target * 0.72))
            self.brake_until = now + 20.0
            self.gear = "BRAKE"
            append_event(self.state_dir, "scheduler_brake", failure_density=density, old_target=old_target, do_inflight_target=self.do_target)

    def _stage_delay_locked(self, stage: TaskStage):
        per_min = self._stage_per_min(stage)
        if per_min <= 0:
            return 0.0
        window = self.stage_releases[stage]
        now = time.time()
        while window and now - window[0] >= 60.0:
            window.popleft()
        if len(window) < per_min:
            return 0.0
        return max(0.0, 60.0 - (now - window[0]))

    def _sleep_release_jitter(self):
        jitter_min = int(self.processing.get("smart_session_stage_mixer_release_jitter_min_ms", 0) or 0)
        jitter_max = int(self.processing.get("smart_session_stage_mixer_release_jitter_max_ms", jitter_min) or jitter_min)
        if jitter_max > 0:
            time.sleep(random.uniform(jitter_min, max(jitter_min, jitter_max)) / 1000.0)

    def _stage_per_min(self, stage: TaskStage):
        key = {
            TaskStage.ENTRY: "smart_session_stage_mixer_entry_per_min",
            TaskStage.RESULTPHONE: "smart_session_stage_mixer_resultphone_per_min",
            TaskStage.PARENT: "smart_session_stage_mixer_parent_per_min",
            TaskStage.ASSOCIATE: "smart_session_stage_mixer_associate_per_min",
        }.get(stage)
        return int(self.processing.get(key, 0) or 0)

    def _inflight_delay_locked(self):
        if self.inflight_current < self.do_target and self.inflight_current < self.do_hard_limit:
            return 0.0
        return 0.2

    def _trim_windows_locked(self):
        now = time.time()
        for window in self.stage_releases.values():
            while window and now - window[0] >= 60.0:
                window.popleft()
        while self.request_window and now - self.request_window[0] >= 60.0:
            self.request_window.popleft()
        while self.save_window and now - self.save_window[0] >= 60.0:
            self.save_window.popleft()
        while self.status_window and now - self.status_window[0][0] >= 60.0:
            self.status_window.popleft()
        while self.elapsed_window and now - self.elapsed_window[0][0] >= 60.0:
            self.elapsed_window.popleft()
        while self.status_elapsed_window and now - self.status_elapsed_window[0][0] >= 60.0:
            self.status_elapsed_window.popleft()
        while len(self.stage_wait_window) > 200:
            self.stage_wait_window.popleft()
        while len(self.do_wait_window) > 200:
            self.do_wait_window.popleft()

    def _write_gate_status_locked(self, stage):
        counts = {f"stage_release_{name.value}_60s": len(window) for name, window in self.stage_releases.items()}
        update_status(self.state_dir, status="RUNNING", scheduler_last_released_stage=stage.value, **counts, **self.metrics())


def _avg(values):
    return int(sum(values) / len(values)) if values else 0


def _p95(values):
    if not values:
        return 0
    ordered = sorted(values)
    return int(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))])
