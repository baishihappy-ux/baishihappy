import time
import threading
from collections import defaultdict

from python.queue.tasks import Task, TaskStage


class StageScheduler:
    def __init__(self, config: dict):
        self.pending = []
        self.config = config
        self.completed = 0
        self.failed = 0
        self.stage_counts = defaultdict(int)
        self.lock = threading.RLock()

    def submit(self, task: Task):
        with self.lock:
            self.pending.append(task)
            self.stage_counts[f"queued_{task.stage.value}"] += 1

    def next_task(self, control_signal=None, timeout=0.2):
        deadline = time.time() + timeout
        while time.time() <= deadline:
            with self.lock:
                has_pending = bool(self.pending)
            if has_pending:
                task = self._pop_best(control_signal)
                if task:
                    return task
            time.sleep(min(0.05, timeout))
        return None

    def _pop_best(self, control_signal=None):
        now = time.time()
        with self.lock:
            eligible = [
                (self.score(task, control_signal), index, task)
                for index, task in enumerate(self.pending)
                if getattr(task, "not_before", 0) <= now
            ]
            if not eligible:
                return None
            eligible.sort(key=lambda item: item[0], reverse=True)
            _, index, task = eligible[0]
            del self.pending[index]
            self.stage_counts[f"dequeued_{task.stage.value}"] += 1
            return task

    def score(self, task: Task, control_signal=None) -> float:
        bias = control_signal.scheduler_bias if control_signal else {}
        q = float(bias.get("queue_pressure", 0.0))
        f = float(bias.get("failure_penalty", 0.0))
        p = float(bias.get("provider_health", 1.0))
        h = float(bias.get("session_stability", 1.0))
        age = min(1.0, (time.time() - task.created_at) / 60.0)
        stage_weight = {
            TaskStage.ENTRY: 0.8,
            TaskStage.RESULTPHONE: 1.0,
            TaskStage.PARENT: 0.9,
            TaskStage.ASSOCIATE: 0.55,
        }.get(task.stage, 0.5)
        if control_signal and control_signal.burst_mode:
            stage_weight += 0.25 if task.stage in {TaskStage.ENTRY, TaskStage.RESULTPHONE} else 0.0
        chain_penalty = max(0, task.depth - (control_signal.chain_length_limit if control_signal else task.depth)) * 0.35
        retry_penalty = task.attempts * (0.2 + f)
        health_score = 0.45 * p + 0.35 * h
        pressure_score = 0.35 * q
        return stage_weight + health_score + pressure_score + age - retry_penalty - chain_penalty

    def has_pending(self):
        with self.lock:
            return bool(self.pending)

    def depth(self):
        with self.lock:
            return len(self.pending)


