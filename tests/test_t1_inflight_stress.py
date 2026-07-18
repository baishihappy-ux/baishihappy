import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from python.engine.runtime_control import RuntimeControl
from python.queue.tasks import TaskStage
from python.session.lane import SessionLaneManager


def make_control(root):
    config = {
        "processing": {
            "smart_session_stage_mixer_resultphone_per_min": 10000,
            "smart_session_stage_mixer_release_jitter_min_ms": 0,
            "smart_session_stage_mixer_release_jitter_max_ms": 0,
            "smart_session_stage_mixer_session_idle_ttl_ms": 300000,
            "smart_session_stage_mixer_session_urgent_remaining_ms": 80000,
        },
        "runtime": {
            "authorized_concurrency": 32,
            "do_inflight_target": 32,
            "do_inflight_hard_limit": 32,
        },
    }
    return RuntimeControl(root, root / "state", config, "stress-test")


class T1InflightStressTests(unittest.TestCase):
    def test_160_sessions_exist_without_occupying_api_slots(self):
        lanes = SessionLaneManager(max_lanes=160)
        created = [lanes.create() for _ in range(160)]
        self.assertTrue(all(created))
        self.assertIsNone(lanes.create())
        with tempfile.TemporaryDirectory() as raw:
            control = make_control(Path(raw))
            self.assertEqual(0, control.current_inflight())
            self.assertEqual(160, lanes.snapshot()["size"])

    def test_160_competing_sessions_never_exceed_32_inflight(self):
        with tempfile.TemporaryDirectory() as raw:
            control = make_control(Path(raw))
            active = 0
            observed_peak = 0
            lock = threading.Lock()

            def request(session_id):
                nonlocal active, observed_peak
                self.assertTrue(control.wait_for_release(TaskStage.RESULTPHONE, session_id=session_id))
                with lock:
                    active += 1
                    observed_peak = max(observed_peak, active)
                time.sleep(0.01)
                with lock:
                    active -= 1
                control.release_inflight()

            with ThreadPoolExecutor(max_workers=160) as pool:
                list(pool.map(request, range(1, 161)))

            self.assertLessEqual(observed_peak, 32)
            self.assertLessEqual(control.inflight_peak, 32)
            self.assertEqual(0, control.current_inflight())

    def test_urgent_session_still_waits_when_all_32_global_slots_are_full(self):
        with tempfile.TemporaryDirectory() as raw:
            control = make_control(Path(raw))
            for session_id in range(1, 33):
                self.assertTrue(control.wait_for_release(TaskStage.RESULTPHONE, session_id=session_id))
            self.assertEqual(32, control.current_inflight())
            urgent_id = 999
            control.session_last_request[urgent_id] = time.time() - 221
            acquired = threading.Event()

            def urgent_request():
                control.wait_for_release(TaskStage.RESULTPHONE, session_id=urgent_id)
                acquired.set()
                control.release_inflight()

            thread = threading.Thread(target=urgent_request, daemon=True)
            thread.start()
            self.assertFalse(acquired.wait(0.1))
            control.release_inflight()
            self.assertTrue(acquired.wait(1.0))
            thread.join(timeout=1.0)
            for _ in range(31):
                control.release_inflight()
            self.assertEqual(0, control.current_inflight())


if __name__ == "__main__":
    unittest.main()
