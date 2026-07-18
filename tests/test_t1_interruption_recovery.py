import tempfile
import unittest
import json
from pathlib import Path

from python.engine.input_pool import InputPool
from python.queue.scheduler import StageScheduler
from python.queue.tasks import Task, TaskStage


class T1InterruptionRecoveryTests(unittest.TestCase):
    def test_restart_classifies_unused_and_used_by_confirmed_business_boundary(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / "runtime" / "state"
            state.mkdir(parents=True)
            input_path = root / "input.txt"
            phones = [f"20255501{number:02d}" for number in range(1, 6)]
            input_path.write_text("\n".join(phones) + "\n", encoding="utf-8")
            pool = InputPool(root, state, {}, input_path, "T").load()

            cases = [
                (phones[0], "B", "CLAIMED"),
                (phones[1], "B", "SEARCH_SUCCEEDED"),
                (phones[2], "A", "PARENT_SUCCEEDED"),
                (phones[3], "A", "FIRST_ASSOCIATE_SUCCEEDED"),
                (phones[4], "A", "NO_ASSOCIATES_COMPLETE"),
            ]
            for line_number, (phone, kind, marker) in enumerate(cases, start=1):
                task = Task(phone=phone, stage=TaskStage.RESULTPHONE, target_source="T",
                            source_bucket="T", line_number=line_number, reuse_kind=kind)
                pool.mark_claimed(task)
                pool.mark_progress(task, marker)

            reloaded = InputPool(root, state, {}, input_path, "T").load()

            self.assertEqual({f"T:{phones[0]}", f"T:{phones[2]}"}, reloaded.interrupted_unused)
            self.assertEqual({f"T:{phones[1]}", f"T:{phones[3]}", f"T:{phones[4]}"}, reloaded.completed)
            self.assertEqual({}, reloaded.claimed)
            txt = (root / "runtime" / "output" / "中断未使用.txt").read_text(encoding="utf-8").splitlines()
            self.assertEqual(sorted([phones[0], phones[2]]), txt)

    def test_interrupted_unused_is_not_reinserted_into_original_input_queue(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / "runtime" / "state"
            state.mkdir(parents=True)
            input_path = root / "input.txt"
            input_path.write_text("2025550199\n", encoding="utf-8")
            pool = InputPool(root, state, {}, input_path, "T").load()
            task = Task(phone="2025550199", stage=TaskStage.RESULTPHONE, target_source="T",
                        source_bucket="T", reuse_kind="A", session_id=456)
            pool.mark_claimed(task)
            pool.mark_progress(task, "PARENT_SUCCEEDED")

            claimed = json.loads((state / "input_claims.json").read_text(encoding="utf-8"))["claimed"]
            self.assertEqual(456, claimed["T:2025550199"]["session_id"])

            reloaded = InputPool(root, state, {}, input_path, "T").load()

            self.assertEqual(0, reloaded.remaining_count())
            self.assertIsNone(reloaded.claim_next_item())

            scheduler = StageScheduler({})
            self.assertEqual(0, reloaded.seed_scheduler(scheduler))
            self.assertEqual(0, scheduler.depth())


if __name__ == "__main__":
    unittest.main()
