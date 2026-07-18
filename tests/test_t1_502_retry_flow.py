import tempfile
import threading
import unittest
from pathlib import Path

from python.engine.runner import EngineRunner
from python.queue.tasks import Task, TaskStage
from python.session.lane import SessionLaneManager, SessionLaneState
from python.session.reuse_pattern import SessionReusePattern


class FakeScheduler:
    def __init__(self):
        self.tasks = []

    def submit(self, task):
        self.tasks.append(task)


class FakeWriters:
    def __init__(self):
        self.retries = []
        self.failures = []

    def write_retry_failure(self, task, reason, attempt):
        self.retries.append((task.stage, attempt, reason))

    def write_failure(self, task, reason, final_502=False):
        self.failures.append((task.stage, reason, final_502))


class FakeInputPool:
    def __init__(self, remaining):
        self.remaining = remaining
        self.recycled = []
        self.discarded = []

    def remaining_count(self):
        return self.remaining

    def has_claimable_item(self):
        return self.remaining > 0

    def mark_recycled_502(self, task):
        self.recycled.append(task.phone)
        self.remaining = max(0, self.remaining - 1)

    def mark_recovered_502(self, task):
        self.discarded.append(task.phone)
        self.remaining = max(0, self.remaining - 1)

    def mark_completed(self, task):
        self.remaining = max(0, self.remaining - 1)

    def mark_failed(self, task):
        self.remaining = max(0, self.remaining - 1)


def make_runner(remaining=1):
    runner = EngineRunner.__new__(EngineRunner)
    runner.config = {"processing": {"smart_session_502_retry_count": 2}}
    runner.scheduler = FakeScheduler()
    runner.writers = FakeWriters()
    runner.input_pool = FakeInputPool(remaining)
    runner.session_lanes = SessionLaneManager(max_lanes=1)
    lane = runner.session_lanes.create()
    lane.reuse_pattern = SessionReusePattern("ABB")
    lane.reuse_pattern.next_kind()
    runner.control_signal = None
    runner.stats_lock = threading.RLock()
    runner.failed = 0
    return runner, lane


class T1502RetryFlowTests(unittest.TestCase):
    def _exhaust(self, stage, remaining=1):
        runner, lane = make_runner(remaining)
        task = Task(phone="2025550199", stage=stage, target_source="T",
                    session_id=lane.session_id, chain_id=lane.chain_id, reuse_kind="A")
        with tempfile.TemporaryDirectory() as raw:
            runner.paths = {"state": Path(raw)}
            self.assertEqual("retry", runner.handle_failure(task, "502", True))
            runner.scheduler.tasks.clear()
            self.assertEqual("retry", runner.handle_failure(task, "502", True))
            runner.scheduler.tasks.clear()
            outcome = runner.handle_failure(task, "502", True)
        return runner, lane, task, outcome

    def test_original_request_plus_two_retries_then_search_recycles(self):
        runner, lane, task, outcome = self._exhaust(TaskStage.RESULTPHONE)
        self.assertEqual(2, task.attempts)
        self.assertEqual([1, 2], [row[1] for row in runner.writers.retries])
        self.assertEqual("final_502_recycled", outcome)
        self.assertEqual(SessionLaneState.DEAD, lane.state)
        self.assertEqual(1, lane.reuse_pattern.completed_count)
        runner._finalize_input_outcome(task, outcome)
        self.assertEqual([task.phone], runner.input_pool.recycled)
        self.assertEqual([], runner.scheduler.tasks)

    def test_parent_recycles_and_queues_replacement_only_after_terminal_state(self):
        runner, lane, task, outcome = self._exhaust(TaskStage.PARENT, remaining=2)
        self.assertEqual("final_502_recycled", outcome)
        self.assertEqual([], runner.scheduler.tasks)
        runner._finalize_input_outcome(task, outcome)
        self.assertEqual(1, len(runner.scheduler.tasks))
        replacement = runner.scheduler.tasks[0]
        self.assertEqual(TaskStage.ENTRY, replacement.stage)
        self.assertTrue(replacement.is_session_bootstrap)

    def test_associate_discards_and_does_not_consume_next_pattern_slot(self):
        runner, lane, task, outcome = self._exhaust(TaskStage.ASSOCIATE)
        self.assertEqual("final_502_recovered", outcome)
        self.assertEqual(1, lane.reuse_pattern.completed_count)
        runner._finalize_input_outcome(task, outcome)
        self.assertEqual([task.phone], runner.input_pool.discarded)
        self.assertEqual([], runner.scheduler.tasks)


if __name__ == "__main__":
    unittest.main()
