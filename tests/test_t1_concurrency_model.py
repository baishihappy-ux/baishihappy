import json
import unittest
from pathlib import Path

from python.engine.config import DEFAULT_CONFIG


class T1ConcurrencyModelTests(unittest.TestCase):
    def test_default_session_capacity_is_separate_from_api_inflight_limit(self):
        self.assertEqual(160, DEFAULT_CONFIG["processing"]["smart_session_session_lane_max"])
        self.assertEqual(32, DEFAULT_CONFIG["runtime"]["do_inflight_target"])
        self.assertEqual(32, DEFAULT_CONFIG["runtime"]["do_inflight_hard_limit"])

    def test_runtime_config_keeps_160_sessions_and_32_api_slots(self):
        path = Path(__file__).parents[1] / "runtime" / "config" / "app_config.json"
        config = json.loads(path.read_text(encoding="utf-8-sig"))
        self.assertEqual(160, config["processing"]["smart_session_session_lane_max"])
        self.assertEqual(32, config["runtime"]["do_inflight_target"])
        self.assertEqual(32, config["runtime"]["do_inflight_hard_limit"])


if __name__ == "__main__":
    unittest.main()
