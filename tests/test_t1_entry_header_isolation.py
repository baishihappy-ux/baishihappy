import unittest
from urllib.parse import parse_qs, urlparse

from python.engine.runner import EngineRunner
from python.engine.t_entry_plan import TEntryPlanner
from python.providers.do_provider import DoProvider
from python.queue.tasks import Task, TaskStage


class FirstChoiceRng:
    def choices(self, population, weights, k):
        return [population[0]]


class FakeScheduler:
    def __init__(self):
        self.tasks = []

    def submit(self, task):
        self.tasks.append(task)


class T1EntryHeaderIsolationTests(unittest.TestCase):
    def config(self):
        return {
            "provider": {"primary_provider": {"token": "test", "params": {"super": True}}},
            "processing": {"max_depth": 2, "smart_session_t_entry_removal_weight_pct": 10,
                           "smart_session_cooldown_result_parent_min_ms": 0,
                           "smart_session_cooldown_result_parent_max_ms": 0},
            "sources": {"source_t": {"encoded_key": "T"}},
        }

    def test_entry_uses_one_pool_referer_and_only_sd_referer_is_forwarded(self):
        config = self.config()
        plan = TEntryPlanner(config, rng=FirstChoiceRng()).choose()
        task = Task(phone="", stage=TaskStage.ENTRY, target_source="T", url=plan.entry_url,
                    session_id=123, referer=plan.referer,
                    entry_referer_key=plan.referer_key, entry_kind=plan.entry_kind)
        response = DoProvider(config, enable_network=False).fetch(task)

        query = parse_qs(urlparse(response.metadata["provider_url"]).query)
        self.assertEqual(["123"], query["sessionId"])
        self.assertEqual(["True"], query["extraHeaders"])
        self.assertEqual({"sd-Referer": plan.referer}, response.metadata["request_headers"])

    def test_entry_pool_identity_does_not_propagate_to_parent_task(self):
        runner = EngineRunner.__new__(EngineRunner)
        runner.config = self.config()
        runner.scheduler = FakeScheduler()
        search = Task(phone="2025550100", stage=TaskStage.RESULTPHONE, target_source="T",
                      url="https://target.invalid/search", referer="https://target.invalid/entry",
                      entry_referer_key="major_search", entry_kind="home",
                      session_id=123, chain_id="chain", reuse_kind="A")

        runner.enqueue_related(search, {"detail_links": ["https://target.invalid/parent"], "related_links": []})

        parent = runner.scheduler.tasks[0]
        self.assertEqual("", parent.entry_referer_key)
        self.assertEqual("", parent.entry_kind)
        self.assertEqual(search.url, parent.referer)


if __name__ == "__main__":
    unittest.main()
