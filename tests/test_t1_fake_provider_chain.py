import tempfile
import threading
import unittest
from pathlib import Path

from python.engine.runner import EngineRunner
from python.providers.base_provider import ProviderResponse
from python.queue.tasks import Task, TaskStage
from python.session.lane import SessionLaneManager
from python.session.reuse_pattern import SessionReusePattern


class FakeProvider:
    def __init__(self, pages):
        self.pages = pages
        self.requests = []

    def fetch(self, task, session=None):
        self.requests.append((task.stage, task.url, task.session_id, task.chain_id, task.referer, task.reuse_kind))
        return ProviderResponse(ok=True, status_code=200, text=self.pages[task.url], url=task.url)


class FakeRouter:
    def __init__(self, provider):
        self.provider = provider

    def route(self, signal):
        return self.provider, "fake"

    def record_result(self, alias, response):
        return None

    def should_try_fallback(self, alias, response):
        return False


class FakeRuntimeControl:
    def record_request(self, *args, **kwargs):
        return None

    def record_save(self):
        return None


class FakeWriters:
    def __init__(self):
        self.records = []

    def write_result(self, record):
        self.records.append(record)


class FakeScheduler:
    def __init__(self):
        self.tasks = []

    def submit(self, task):
        self.tasks.append(task)

    def pop(self):
        return self.tasks.pop(0)


class FakeInputPool:
    def __init__(self, items):
        self.items = list(items)
        self.progress = []

    def claim_next_item(self):
        return self.items.pop(0) if self.items else None

    def remaining_count(self):
        return len(self.items)

    def mark_progress(self, task, marker):
        self.progress.append((task.phone, marker))


def detail_html(name, associates=()):
    links = "".join(f'<a data-link-to-more="associate" href="{url}">{url}</a>' for url in associates)
    return f'<html><title>{name}</title><h1 id="details-header">{name}</h1><a href="/find/phone/2025550100">phone</a>{links}</html>'


class T1FakeProviderChainTests(unittest.TestCase):
    def test_abb_chain_uses_one_identity_and_human_referer_transitions(self):
        search_a = "https://www.truepeoplesearch.com/resultphone?phoneno=2025550100"
        parent = "https://www.truepeoplesearch.com/find/person/parent"
        associates = [f"https://www.truepeoplesearch.com/find/person/associate-{x}" for x in "abc"]
        search_b1 = "https://www.truepeoplesearch.com/resultphone?phoneno=2025550101"
        search_b2 = "https://www.truepeoplesearch.com/resultphone?phoneno=2025550102"
        pages = {
            search_a: f'<html><a href="{parent}">parent</a></html>',
            parent: detail_html("Parent Person", associates),
            associates[0]: detail_html("Associate A"),
            associates[1]: detail_html("Associate B"),
            associates[2]: detail_html("Associate C"),
            search_b1: "<html><title>Search B1</title></html>",
            search_b2: "<html><title>Search B2</title></html>",
        }
        provider = FakeProvider(pages)
        runner = EngineRunner.__new__(EngineRunner)
        runner.config = {"processing": {"max_depth": 2, "max_related_per_seed": 10,
            "smart_session_cooldown_result_parent_min_ms": 0, "smart_session_cooldown_result_parent_max_ms": 0,
            "smart_session_cooldown_parent_associate_min_ms": 0, "smart_session_cooldown_parent_associate_max_ms": 0,
            "smart_session_cooldown_between_associates_min_ms": 0, "smart_session_cooldown_between_associates_max_ms": 0,
            "smart_session_cooldown_next_parent_min_ms": 0, "smart_session_cooldown_next_parent_max_ms": 0},
            "sources": {"source_t": {"encoded_key": "T"}}}
        runner.provider_router = FakeRouter(provider)
        runner.runtime_control = FakeRuntimeControl()
        runner.writers = FakeWriters()
        runner.scheduler = FakeScheduler()
        runner.input_pool = FakeInputPool([
            {"phone": "2025550101", "line_number": 2, "source": "A", "source_name": "input-a"},
            {"phone": "2025550102", "line_number": 3, "source": "B", "source_name": "input-b"},
        ])
        runner.session_lanes = SessionLaneManager(max_lanes=1)
        lane = runner.session_lanes.create()
        lane.reuse_pattern = SessionReusePattern("ABB")
        self.assertEqual("A", lane.reuse_pattern.next_kind())
        runner.control_lock = threading.RLock()
        runner.session_lock = threading.RLock()
        runner.stats_lock = threading.RLock()
        runner.control_signal = None
        runner.brain = None
        runner.session_pool_enabled = False
        runner.saved = runner.failed = 0
        with tempfile.TemporaryDirectory() as raw:
            runner.paths = {"state": Path(raw)}
            task = Task(phone="2025550100", stage=TaskStage.RESULTPHONE, target_source="T", url=search_a,
                        seed_phone="2025550100", line_number=1, source_bucket="A", source_name="input-a",
                        session_id=lane.session_id, chain_id=lane.chain_id,
                        referer="https://entry.invalid/", reuse_kind="A")
            outcomes = []
            while task:
                outcomes.append(runner.process_task(task))
                task = runner.scheduler.pop() if runner.scheduler.tasks else None

        requests = provider.requests
        self.assertEqual([search_a, parent, *associates, search_b1, search_b2], [row[1] for row in requests])
        self.assertEqual({lane.session_id}, {row[2] for row in requests})
        self.assertEqual({lane.chain_id}, {row[3] for row in requests})
        self.assertEqual(search_a, requests[1][4])
        self.assertEqual([parent, parent, parent], [row[4] for row in requests[2:5]])
        self.assertEqual(associates[-1], requests[5][4])
        self.assertEqual(search_b1, requests[6][4])
        self.assertEqual(["A", "A", "A", "A", "A", "B", "B"], [row[5] for row in requests])
        self.assertEqual("success", outcomes[-1])


if __name__ == "__main__":
    unittest.main()
