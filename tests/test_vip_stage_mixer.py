import json
import tempfile
import time
import unittest
from pathlib import Path

from python.engine.runtime_control import RuntimeControl
from python.queue.tasks import TaskStage


class VipStageMixerTests(unittest.TestCase):
    def make_control(self, root):
        config = {
            "processing": {
                "smart_session_stage_mixer_entry_per_min": 1,
                "smart_session_stage_mixer_release_jitter_min_ms": 0,
                "smart_session_stage_mixer_release_jitter_max_ms": 0,
                "smart_session_stage_mixer_session_idle_ttl_ms": 300000,
                "smart_session_stage_mixer_session_urgent_remaining_ms": 80000,
            },
            "runtime": {"authorized_concurrency": 32},
        }
        return RuntimeControl(root, root / "state", config, "vip-test")

    def test_urgent_threshold_is_idle_ttl_minus_remaining_window(self):
        with tempfile.TemporaryDirectory() as temp:
            control = self.make_control(Path(temp))
            self.assertEqual(300.0, control.session_idle_ttl_seconds)
            self.assertEqual(80.0, control.session_urgent_remaining_seconds)
            self.assertEqual(220.0, control.session_urgent_idle_seconds)
            control.session_last_request[7] = time.time() - 219.9
            self.assertFalse(control._session_urgent_locked(7))
            control.session_last_request[7] = time.time() - 220.1
            self.assertTrue(control._session_urgent_locked(7))

    def test_urgent_session_bypasses_stage_cap_but_records_event(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            control = self.make_control(root)
            control.stage_releases[TaskStage.ENTRY].append(time.time())
            control.session_last_request[77] = time.time() - 221.0

            self.assertTrue(control.wait_for_release(TaskStage.ENTRY, session_id=77))
            control.release_inflight()

            self.assertEqual(1, control.session_urgent_bypass_count)
            events = (root / "state" / "events.jsonl").read_text(encoding="utf-8").splitlines()
            urgent = [json.loads(line) for line in events if json.loads(line).get("event") == "stage_mixer_urgent_bypass"]
            self.assertEqual(1, len(urgent))
            self.assertEqual("entry", urgent[0]["stage"])
            self.assertEqual(77, urgent[0]["session_id"])
            self.assertEqual(1, urgent[0]["stage_limit_per_min"])


if __name__ == "__main__":
    unittest.main()
