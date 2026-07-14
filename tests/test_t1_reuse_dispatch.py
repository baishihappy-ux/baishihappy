import unittest

from python.engine.runner import EngineRunner
from python.queue.tasks import Task, TaskStage
from python.session.lane import SessionLaneManager
from python.session.reuse_pattern import SessionReusePattern


class FakeInputPool:
    def __init__(self, items):
        self.items = list(items)
        self.claim_count = 0

    def claim_next_item(self):
        self.claim_count += 1
        return self.items.pop(0) if self.items else None


class FakeScheduler:
    def __init__(self):
        self.tasks = []

    def submit(self, task):
        self.tasks.append(task)


def make_runner(pattern, items):
    runner = EngineRunner.__new__(EngineRunner)
    runner.config = {"processing": {
        "smart_session_cooldown_next_parent_min_ms": 0,
        "smart_session_cooldown_next_parent_max_ms": 0,
    }, "sources": {"source_t": {"input_url_template": "https://target.invalid/resultphone?phoneno={phone_digits}"}}}
    runner.input_pool = FakeInputPool(items)
    runner.scheduler = FakeScheduler()
    runner.session_lanes = SessionLaneManager(max_lanes=1)
    lane = runner.session_lanes.create()
    lane.reuse_pattern = SessionReusePattern(pattern)
    return runner, lane


class T1ReuseDispatchTests(unittest.TestCase):
    def test_claims_lazily_and_reuses_identity_and_last_success_url(self):
        item = {"phone": "2025550102", "line_number": 2, "source": "A", "source_name": "input-a"}
        runner, lane = make_runner("ABB", [item])
        lane.reuse_pattern.next_kind()  # current A slot was claimed with the first phone
        current = Task(phone="2025550101", stage=TaskStage.ASSOCIATE, target_source="T",
                       session_id=lane.session_id, chain_id=lane.chain_id, reuse_kind="A")

        self.assertTrue(runner._schedule_next_lane_phone(current, "https://target.invalid/associate/c"))
        self.assertEqual(1, runner.input_pool.claim_count)
        self.assertEqual(1, len(runner.scheduler.tasks))
        next_task = runner.scheduler.tasks[0]
        self.assertEqual("B", next_task.reuse_kind)
        self.assertEqual(lane.session_id, next_task.session_id)
        self.assertEqual(lane.chain_id, next_task.chain_id)
        self.assertEqual("https://target.invalid/associate/c", next_task.referer)

    def test_exhausted_pattern_does_not_claim_another_phone(self):
        item = {"phone": "2025550104", "line_number": 4, "source": "A", "source_name": "input-a"}
        runner, lane = make_runner("BBA", [item])
        for _ in range(3):
            lane.reuse_pattern.next_kind()
        current = Task(phone="2025550103", stage=TaskStage.RESULTPHONE, target_source="T",
                       session_id=lane.session_id, chain_id=lane.chain_id, reuse_kind="A")

        self.assertFalse(runner._schedule_next_lane_phone(current, "https://target.invalid/resultphone/last"))
        self.assertEqual(0, runner.input_pool.claim_count)
        self.assertEqual([], runner.scheduler.tasks)


if __name__ == "__main__":
    unittest.main()
