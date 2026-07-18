import json
import tempfile
import unittest
from pathlib import Path

from python.engine.input_pool import InputPool
from python.engine.runner import EngineRunner
from python.queue.tasks import Task, TaskStage


class T1502RecycleTests(unittest.TestCase):
    def test_search_page_502_is_persisted_in_dedicated_recycle_state(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / "runtime" / "state"
            state.mkdir(parents=True)
            input_path = root / "input.txt"
            input_path.write_text("2025550101\n", encoding="utf-8")
            pool = InputPool(root, state, {}, input_path, "T").load()
            self.assertTrue(pool.has_claimable_item())
            task = Task(phone="2025550101", stage=TaskStage.RESULTPHONE, target_source="T", source_bucket="T")

            pool.mark_recycled_502(task)

            payload = json.loads((state / "t_recycled_502.json").read_text(encoding="utf-8"))
            self.assertEqual(1, payload["count"])
            self.assertEqual(["2025550101"], payload["phones"])
            self.assertEqual("search_page_final_502_not_consumed", payload["policy"])
            reloaded = InputPool(root, state, {}, input_path, "T").load()
            self.assertEqual({"T:2025550101"}, reloaded.recycled_502)
            self.assertEqual(0, reloaded.remaining_count())
            self.assertFalse(reloaded.has_claimable_item())
            self.assertEqual(1, json.loads((state / "input_cursor.json").read_text(encoding="utf-8"))["cursor"])

    def test_associate_502_uses_discarded_terminal_set_not_recycle_set(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / "runtime" / "state"
            state.mkdir(parents=True)
            input_path = root / "input.txt"
            input_path.write_text("2025550102\n", encoding="utf-8")
            pool = InputPool(root, state, {}, input_path, "T").load()
            task = Task(phone="2025550102", stage=TaskStage.ASSOCIATE, target_source="T", source_bucket="T")

            pool.mark_recovered_502(task)

            self.assertEqual({"T:2025550102"}, pool.recovered_502)
            self.assertEqual(set(), pool.recycled_502)

    def test_parent_detail_502_is_recycled_not_discarded(self):
        task = Task(phone="2025550103", stage=TaskStage.PARENT, target_source="T")
        self.assertEqual("final_502_recycled", EngineRunner._final_502_outcome(task))

    def test_only_associate_502_is_discarded(self):
        task = Task(phone="2025550104", stage=TaskStage.ASSOCIATE, target_source="T")
        self.assertEqual("final_502_recovered", EngineRunner._final_502_outcome(task))


if __name__ == "__main__":
    unittest.main()
