import time
import threading
from pathlib import Path

from python.control.brain import FeedbackLoopEngine
from python.auth.license import apply_license_to_config
from python.engine.config import load_config, resolve_input_file
from python.engine.input_pool import InputPool
from python.engine.runtime_control import RuntimeControl
from python.export.writers import ResultWriters
from python.parser.html_parser import extract_links, extract_record
from python.parser.source_profiles import PROFILES
from python.providers.provider_manager import ProviderManager
from python.queue.scheduler import StageScheduler
from python.queue.tasks import Task, TaskStage
from python.session.pool import SessionPool
from python.utils.paths import ensure_runtime_dirs, runtime_root
from python.utils.runtime_state import append_event, update_status, write_json


class EngineRunner:
    def __init__(self, root: Path, args):
        self.root = root
        self.args = args
        self.paths = ensure_runtime_dirs(root)
        self.config = apply_license_to_config(runtime_root(root), load_config(root))
        if getattr(args, "target_source", None):
            self.config.setdefault("runtime", {})["target_source"] = args.target_source
        self.scheduler = StageScheduler(self.config)
        self.provider_alias_override = getattr(args, "provider", None)
        self.provider_router = ProviderManager(self.config, enable_network=getattr(args, "enable_network", False))
        if self.provider_alias_override:
            self.provider_router.active_alias = self.provider_alias_override
        self.control_enabled = self.provider_router.uses_control_brain()
        self.session_pool_enabled = self.provider_router.uses_session_pool()
        pool_cfg = self.config.get("provider", {}).get("primary_provider", {}).get("session_pool", {})
        self.pool = SessionPool(pool_cfg.get("pool_size", 10), pool_cfg.get("reuse_seconds", 3600), pool_cfg.get("enabled", True))
        self.writers = ResultWriters(runtime_root(root), self.config)
        self.brain = FeedbackLoopEngine(self.config) if self.control_enabled else None
        self.control_signal = self.brain.generate_signal() if self.brain else None
        self.static_concurrency = int(self.config.get("processing", {}).get("thread_count") or self.config.get("runtime", {}).get("authorized_concurrency", 32) or 32)
        self.runtime_control = RuntimeControl(runtime_root(root), self.paths["state"], self.config, getattr(args, "instance_id", "") or "")
        self.saved = 0
        self.failed = 0
        self.processed = 0
        self.started_count = 0
        self.active_workers = 0
        self.stats_lock = threading.RLock()
        self.control_lock = threading.RLock()
        self.session_lock = threading.RLock()
        self.stop_event = threading.Event()
        configured_workers = int(self.config.get("runtime", {}).get("scheduler_worker_max") or self.config.get("processing", {}).get("scheduler_worker_max") or 0)
        self.worker_count = max(1, configured_workers or self.static_concurrency * 5)
        self.input_pool = None

    def seed_input(self):
        input_path = resolve_input_file(self.root, self.config, getattr(self.args, "input_file", None))
        target = self.config.get("runtime", {}).get("target_source", "T")
        self.input_pool = InputPool(self.root, self.paths["state"], self.config, input_path, target).load()
        return self.input_pool.seed_scheduler(self.scheduler)

    def run(self):
        lock = self.runtime_control.acquire_lock()
        if not lock.get("ok"):
            return lock
        if self.session_pool_enabled:
            self.pool.warm(self.config.get("provider", {}).get("primary_provider", {}).get("session_pool", {}).get("pool_size", 10))
        seeded = self.seed_input()
        total = len(self.input_pool.phones) if self.input_pool else seeded
        self.refresh_control(active_workers=0)
        update_status(
            self.paths["state"],
            status="RUNNING",
            run_lock=lock,
            total_input=total,
            **self.status_fields(alive_workers=0),
            **self.runtime_control.metrics(),
            pool=self.pool_snapshot(),
            control_brain=self.brain.snapshot() if self.brain else None,
            provider=self.provider_router.snapshot(),
        )
        append_event(self.paths["state"], "run_started", total_input=total, seeded=seeded)
        max_total = int(getattr(self.args, "max_total_records", None) or self.config.get("processing", {}).get("max_total_records", 0) or 0)
        workers = []
        try:
            for index in range(self.worker_count):
                thread = threading.Thread(target=self.worker_loop, args=(index + 1, max_total), name=f"t1-worker-{index + 1}", daemon=True)
                workers.append(thread)
                thread.start()
            while any(thread.is_alive() for thread in workers):
                stats = self.stats_snapshot()
                self.runtime_control.heartbeat(processed=stats["processed"], remaining_work=self.remaining_input_count(), active_workers=stats["active_workers"])
                self.runtime_control.update_ramp()
                if self.runtime_control.circuit_open:
                    self.stop_event.set()
                if not self.scheduler.has_pending() and stats["active_workers"] == 0:
                    self.stop_event.set()
                self.refresh_control(active_workers=self.runtime_control.current_inflight())
                update_status(
                    self.paths["state"],
                    status="RUNNING",
                    **self.status_fields(stats=stats, alive_workers=sum(1 for thread in workers if thread.is_alive())),
                    pool=self.pool_snapshot(),
                    control_brain=self.brain.snapshot() if self.brain else None,
                    provider=self.provider_router.snapshot(),
                    **self.runtime_control.metrics(),
                )
                time.sleep(1.0)
            for thread in workers:
                thread.join(timeout=2.0)
            stats = self.stats_snapshot()
            final_status = "CIRCUIT_BREAKER" if self.runtime_control.circuit_open else "FINISHED"
            update_status(
                self.paths["state"],
                status=final_status,
                **self.status_fields(stats=stats, alive_workers=0),
                pool=self.pool_snapshot(),
                control_brain=self.brain.snapshot() if self.brain else None,
                provider=self.provider_router.snapshot(),
                **self.runtime_control.metrics(),
            )
            append_event(self.paths["state"], "run_finished", processed=stats["processed"], status=final_status)
            return {"ok": not self.runtime_control.circuit_open, "processed": stats["processed"], "total_input": total, "seeded": seeded, "status": final_status, "workers": self.worker_count}
        finally:
            self.stop_event.set()
            self.runtime_control.release_lock()

    def worker_loop(self, worker_id: int, max_total: int):
        poll_seconds = self.config.get("processing", {}).get("queue_poll_seconds", 0.2)
        while not self.stop_event.is_set():
            if self.runtime_control.circuit_open:
                self.stop_event.set()
                return
            self.runtime_control.wait_if_paused()
            if not self.reserve_work(max_total):
                return
            with self.control_lock:
                control_signal = self.control_signal if self.control_enabled else None
            task = self.scheduler.next_task(control_signal, poll_seconds)
            if not task:
                self.unreserve_work(max_total)
                if not self.scheduler.has_pending():
                    return
                time.sleep(poll_seconds)
                continue
            if self.input_pool:
                self.input_pool.mark_claimed(task)
            if not self.runtime_control.wait_for_release(task.stage):
                self.unreserve_work(max_total)
                return
            self.mark_worker_active(1)
            try:
                outcome = self.process_task(task)
                if outcome in {"success", "failed", "final_502_recovered"}:
                    self.complete_work()
                if self.input_pool and outcome == "success":
                    self.input_pool.mark_completed(task)
                elif self.input_pool and outcome == "final_502_recovered":
                    self.input_pool.mark_recovered_502(task)
                elif self.input_pool and outcome == "failed":
                    self.input_pool.mark_failed(task)
            finally:
                self.mark_worker_active(-1)
                self.runtime_control.release_inflight()

    def reserve_work(self, max_total: int):
        if not max_total:
            return True
        with self.stats_lock:
            if self.started_count >= max_total:
                return False
            self.started_count += 1
            return True

    def unreserve_work(self, max_total: int):
        if not max_total:
            return
        with self.stats_lock:
            self.started_count = max(0, self.started_count - 1)

    def complete_work(self):
        with self.stats_lock:
            self.processed += 1

    def mark_worker_active(self, delta: int):
        with self.stats_lock:
            self.active_workers = max(0, self.active_workers + delta)

    def stats_snapshot(self):
        with self.stats_lock:
            return {
                "processed": self.processed,
                "saved": self.saved,
                "failed": self.failed,
                "active_workers": self.active_workers,
                "started_count": self.started_count,
            }

    def status_fields(self, stats=None, alive_workers=0):
        stats = stats or self.stats_snapshot()
        remaining = self.remaining_input_count()
        active = stats["active_workers"]
        completed = self.completed_input_count()
        recovered_502 = self.recovered_502_input_count()
        total = len(self.input_pool.items) if self.input_pool else 0
        return {
            "input_total": total,
            "started": stats["started_count"],
            "processed": stats["processed"],
            "saved": stats["saved"],
            "failed": stats["failed"],
            "invalid_seeds": 0,
            "requeued_seeds": 0,
            "visited": 0,
            "completed_seeds": completed,
            "failed_502_discarded_seeds": recovered_502,
            "customer_completed_seeds": completed + recovered_502 + self.failed_input_count(),
            "customer_recovered_502_seeds": recovered_502,
            "active_seeds": active,
            "remaining": remaining,
            "remaining_work": remaining + active,
            "queue_depth": self.scheduler.depth(),
            "authorized_concurrency": self.runtime_control.authorized_concurrency,
            "current_concurrency": self.worker_count,
            "scheduler_started_workers": self.worker_count,
            "scheduler_alive_workers": alive_workers,
            "scheduler_active_workers": active,
            "scheduler_max_workers": self.worker_count,
            "scheduler_ramp_worker_target": self.worker_count,
            "scheduler_dynamic_start_count": 0,
            "scheduler_do_inflight_target": self.runtime_control.do_target,
            "scheduler_do_inflight_current": self.runtime_control.current_inflight(),
            "worker_state_counts": {"active": active, "idle_or_waiting": max(0, alive_workers - active)},
        }

    def pool_snapshot(self):
        if not self.session_pool_enabled:
            return None
        with self.session_lock:
            return self.pool.snapshot()

    def completed_input_count(self):
        return len(self.input_pool.completed) if self.input_pool else self.processed

    def recovered_502_input_count(self):
        return len(self.input_pool.recovered_502) if self.input_pool else 0

    def failed_input_count(self):
        return len(self.input_pool.failed) if self.input_pool else 0

    def remaining_input_count(self):
        if not self.input_pool:
            return self.scheduler.depth()
        return self.input_pool.remaining_count()

    def process_task(self, task: Task):
        with self.control_lock:
            control_signal = self.control_signal
        if control_signal and task.depth > control_signal.chain_length_limit:
            with self.control_lock:
                self.brain.record("session_chain_break", phone=task.phone, task_id=task.id, reason="chain length limited")
                self.brain.record("task_failure", status_code=0, reason="chain length limited by control brain", phone=task.phone)
            return self.handle_failure(task, "chain length limited by control brain", False)
        with self.session_lock:
            session = self.pool.acquire() if self.session_pool_enabled else None
            if control_signal and (control_signal.rebuild_session_chain or self.pool.detect_instability()):
                rebuilt = self.pool.rebuild_chain(control_signal.chain_length_limit)
                with self.control_lock:
                    self.brain.record("session_recovered", rebuilt=rebuilt)
                append_event(self.paths["state"], "session_chain_rebuilt", rebuilt=rebuilt)
                session = self.pool.acquire()
        provider, provider_alias = self.provider_router.route(control_signal)
        try:
            fetch_started = time.time()
            response = provider.fetch(task, session=session)
            fetch_elapsed_ms = int((time.time() - fetch_started) * 1000)
            self.provider_router.record_result(provider_alias, response)
            self.runtime_control.record_request(response.status_code, response.ok, fetch_elapsed_ms)
            if not response.ok:
                if self.brain:
                    with self.control_lock:
                        self.brain.record("task_failure", status_code=response.status_code, reason=response.error, provider=provider_alias, phone=task.phone)
                if self.provider_router.should_try_fallback(provider_alias, response):
                    fallback_alias = self.provider_router.fallback_alias(provider_alias)
                    if fallback_alias != provider_alias:
                        fallback = self.provider_router.get(fallback_alias)
                        fallback_response = fallback.fetch(task, session=None)
                        self.provider_router.record_result(fallback_alias, fallback_response)
                        if fallback_response.ok:
                            response = fallback_response
                            provider_alias = fallback_alias
                        else:
                            response = fallback_response
                if not response.ok:
                    outcome = self.handle_failure(task, response.error or str(response.status_code), response.status_code == 502)
                    chain_ok = response.status_code not in {0, 502, 504}
                    if self.brain and not chain_ok:
                        with self.control_lock:
                            self.brain.record("session_chain_break", task_id=task.id, phone=task.phone, status_code=response.status_code)
                    if self.session_pool_enabled:
                        with self.session_lock:
                            self.pool.release(session, ok=False, fatal=response.status_code in {401, 403}, chain_ok=chain_ok)
                    return outcome
            profile = PROFILES.get(task.target_source)
            source_cfg = profile.from_config(self.config) if profile else {}
            links = extract_links(response.text, source_cfg.get("detail_url_base", response.url), source_cfg)
            record = extract_record(response.text, task.target_source, task.stage.value, seed_phone=task.seed_phone or task.phone, parent_phone=task.phone)
            record.update({
                "phone": task.phone,
                "stage": task.stage.value,
                "source": task.target_source,
                "url": task.url or "",
                "detail_links": len(links["detail_links"]),
                "related_links": len(links["related_links"]),
                "provider": provider_alias,
                "session_id": session.id if session else "",
                "chain_id": session.chain_id if session else "",
                "ts": int(time.time()),
            })
            self.writers.write_result(record)
            with self.stats_lock:
                self.saved += 1
            self.runtime_control.record_save()
            self.enqueue_related(task, links)
            if self.brain:
                with self.control_lock:
                    self.brain.record("task_success", provider=provider_alias, phone=task.phone)
            if session and control_signal and links["related_links"] and task.depth < control_signal.chain_length_limit:
                with self.session_lock:
                    self.pool.propagate_chain(session)
            if self.session_pool_enabled:
                with self.session_lock:
                    self.pool.release(session, ok=True, chain_ok=True)
            return "success"
        except Exception as exc:
            self.provider_router.record_result(provider_alias, type("Response", (), {"ok": False, "status_code": 0})())
            self.runtime_control.record_request(0, False)
            if self.brain:
                with self.control_lock:
                    self.brain.record("task_failure", status_code=0, reason=str(exc), provider=provider_alias, phone=task.phone)
                    self.brain.record("session_chain_break", task_id=task.id, phone=task.phone, reason=str(exc))
            outcome = self.handle_failure(task, str(exc), False)
            if self.session_pool_enabled:
                with self.session_lock:
                    self.pool.release(session, ok=False, chain_ok=False)
            return outcome

    def enqueue_related(self, task: Task, links: dict):
        max_depth = int(self.config.get("processing", {}).get("max_depth", 1))
        if task.depth >= max_depth:
            return
        for url in links["detail_links"][:1]:
            self.scheduler.submit(Task(phone=task.phone, stage=TaskStage.PARENT, target_source=task.target_source, url=url, depth=task.depth + 1, seed_phone=task.seed_phone))
        max_related = int(self.config.get("processing", {}).get("max_related_per_seed", 100))
        for url in links["related_links"][:max_related]:
            self.scheduler.submit(Task(phone=task.phone, stage=TaskStage.ASSOCIATE, target_source=task.target_source, url=url, depth=task.depth + 1, seed_phone=task.seed_phone))

    def handle_failure(self, task, reason: str, final_502: bool):
        retry_count = self.provider_router.retry_count()
        if task.attempts < retry_count:
            task.attempts += 1
            self.writers.write_retry_failure(task, reason, task.attempts)
            if self.control_signal and self.control_signal.retry_delay_seconds:
                task.not_before = time.time() + self.control_signal.retry_delay_seconds
            self.scheduler.submit(task)
            append_event(self.paths["state"], "task_retried", task_id=task.id, phone=task.phone, reason=reason, status="502" if final_502 else "")
            return "retry"
        else:
            with self.stats_lock:
                self.failed += 1
            self.writers.write_failure(task, reason, final_502=final_502)
            event_name = "task_final_502_recovered" if final_502 else "task_failed"
            append_event(self.paths["state"], event_name, task_id=task.id, phone=task.phone, reason=reason)
            return "final_502_recovered" if final_502 else "failed"

    def refresh_control(self, active_workers=0):
        with self.control_lock:
            if not self.brain:
                stale = self.paths["state"] / "control_brain.json"
                if stale.exists():
                    stale.unlink()
                return None
            with self.session_lock:
                session_snapshot = self.pool.snapshot()
            self.control_signal = self.brain.update_metrics(
                queue_depth=self.scheduler.depth(),
                active_workers=active_workers,
                provider_snapshot=self.provider_router.snapshot(),
                session_snapshot=session_snapshot,
            )
            self.provider_router.apply_control_signal(self.control_signal)
            write_json(self.paths["state"] / "control_brain.json", self.brain.snapshot())
            return self.control_signal
