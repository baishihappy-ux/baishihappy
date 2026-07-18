import unittest

from python.engine.runner import EngineRunner
from python.queue.tasks import Task, TaskStage
from python.session.lane import SessionLaneManager
from python.session.reuse_pattern import SessionReusePattern


class FakeInputPool:
    def __init__(self, items):
        self.items = list(items)
        self.claim_count = 0
        self.claimed_tasks = []

    def claim_next_item(self):
        self.claim_count += 1
        return self.items.pop(0) if self.items else None

    def remaining_count(self):
        return len(self.items)

    def has_claimable_item(self):
        return bool(self.items)

    def mark_claimed(self, task):
        self.claimed_tasks.append(task)


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
    def test_associate_siblings_keep_depth_identity_and_parent_referer(self):
        runner = EngineRunner.__new__(EngineRunner)
        runner.config = {"processing": {"max_depth": 2, "max_related_per_seed": 10,
            "smart_session_cooldown_parent_associate_min_ms": 0,
            "smart_session_cooldown_parent_associate_max_ms": 0,
            "smart_session_cooldown_between_associates_min_ms": 0,
            "smart_session_cooldown_between_associates_max_ms": 0}}
        runner.scheduler = FakeScheduler()
        parent = Task(phone="2025550100", stage=TaskStage.PARENT, target_source="T", depth=1,
                      url="https://target.invalid/parent", seed_phone="2025550100",
                      line_number=7, source_bucket="A", source_name="input-a",
                      session_id=123, chain_id="chain", reuse_kind="A")
        links = {"detail_links": [], "related_links": [
            "https://target.invalid/a", "https://target.invalid/b", "https://target.invalid/c"]}

        self.assertEqual(1, runner.enqueue_related(parent, links))
        first = runner.scheduler.tasks.pop()
        self.assertEqual(2, first.depth)
        self.assertEqual("A", first.source_bucket)
        self.assertEqual(7, first.line_number)
        self.assertEqual("https://target.invalid/parent", first.referer)
        self.assertEqual(2, len(first.remaining_associate_urls))

        self.assertEqual(1, runner.enqueue_related(first, {"detail_links": [], "related_links": []}))
        second = runner.scheduler.tasks.pop()
        self.assertEqual(2, second.depth)
        self.assertEqual("A", second.source_bucket)
        self.assertEqual(7, second.line_number)
        self.assertEqual("https://target.invalid/parent", second.referer)
        self.assertEqual(["https://target.invalid/c"], second.remaining_associate_urls)

    def test_parent_without_associates_uses_parent_url_for_next_pattern_slot(self):
        item = {"phone": "2025550112", "line_number": 12, "source": "B", "source_name": "input-b"}
        runner, lane = make_runner("ABB", [item])
        lane.reuse_pattern.next_kind()  # current A
        parent = Task(phone="2025550111", stage=TaskStage.PARENT, target_source="T", depth=1,
                      url="https://target.invalid/parent/no-associates", session_id=lane.session_id,
                      chain_id=lane.chain_id, reuse_kind="A")

        self.assertEqual(0, runner.enqueue_related(parent, {"detail_links": [], "related_links": []}))
        self.assertTrue(runner._schedule_next_lane_phone(parent, parent.url))
        next_task = runner.scheduler.tasks[0]
        self.assertEqual("B", next_task.reuse_kind)
        self.assertEqual(parent.url, next_task.referer)

    def test_claims_lazily_and_reuses_identity_and_last_success_url(self):
        item = {"phone": "2025550102", "line_number": 2, "source": "A", "source_name": "input-a"}
        runner, lane = make_runner("ABB", [item])
        lane.reuse_pattern.next_kind()  # current A slot was claimed with the first phone
        current = Task(phone="2025550101", stage=TaskStage.ASSOCIATE, target_source="T",
                       session_id=lane.session_id, chain_id=lane.chain_id, reuse_kind="A")

        self.assertTrue(runner._schedule_next_lane_phone(current, "https://target.invalid/associate/c"))
        self.assertEqual(1, runner.input_pool.claim_count)
        self.assertEqual([next_task := runner.scheduler.tasks[0]], runner.input_pool.claimed_tasks)
        self.assertEqual(1, len(runner.scheduler.tasks))
        self.assertEqual("B", next_task.reuse_kind)
        self.assertEqual(lane.session_id, next_task.session_id)
        self.assertEqual(lane.chain_id, next_task.chain_id)
        self.assertEqual("https://target.invalid/associate/c", next_task.referer)

    def test_b_to_a_uses_previous_search_url_as_referer(self):
        item = {"phone": "2025550122", "line_number": 22, "source": "B", "source_name": "input-b"}
        runner, lane = make_runner("BAB", [item])
        self.assertEqual("B", lane.reuse_pattern.next_kind())
        current = Task(phone="2025550121", stage=TaskStage.RESULTPHONE, target_source="T",
                       session_id=lane.session_id, chain_id=lane.chain_id, reuse_kind="B")
        search_url = "https://target.invalid/resultphone/2025550121"

        self.assertTrue(runner._schedule_next_lane_phone(current, search_url))
        next_task = runner.scheduler.tasks[0]
        self.assertEqual("A", next_task.reuse_kind)
        self.assertEqual(search_url, next_task.referer)

    def test_exhausted_pattern_does_not_claim_another_phone(self):
        item = {"phone": "2025550104", "line_number": 4, "source": "A", "source_name": "input-a"}
        runner, lane = make_runner("BBA", [item])
        for _ in range(3):
            lane.reuse_pattern.next_kind()
        current = Task(phone="2025550103", stage=TaskStage.RESULTPHONE, target_source="T",
                       session_id=lane.session_id, chain_id=lane.chain_id, reuse_kind="A")

        self.assertFalse(runner._schedule_next_lane_phone(current, "https://target.invalid/resultphone/last"))
        self.assertEqual(0, runner.input_pool.claim_count)
        self.assertEqual(1, len(runner.scheduler.tasks))
        replacement = runner.scheduler.tasks[0]
        self.assertEqual(TaskStage.ENTRY, replacement.stage)
        self.assertTrue(replacement.is_session_bootstrap)

    def test_no_replacement_entry_when_input_is_empty(self):
        runner, lane = make_runner("ABB", [])
        for _ in range(3):
            lane.reuse_pattern.next_kind()
        current = Task(phone="2025550105", stage=TaskStage.RESULTPHONE, target_source="T",
                       session_id=lane.session_id, chain_id=lane.chain_id, reuse_kind="B")

        self.assertFalse(runner._schedule_next_lane_phone(current, "https://target.invalid/resultphone/last"))
        self.assertEqual([], runner.scheduler.tasks)


if __name__ == "__main__":
    unittest.main()
