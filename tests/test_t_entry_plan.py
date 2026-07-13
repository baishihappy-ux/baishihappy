import json
import math
import random
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from python.engine.config import DEFAULT_CONFIG
from python.engine.t_entry_plan import TEntryPlanner, build_t_entry_referers


def config_with_removal_weight(value):
    return {
        "sources": {"source_t": {"encoded_key": "T"}},
        "processing": {"smart_session_t_entry_removal_weight_pct": value},
    }


class RecordingRng:
    def __init__(self):
        self.population = []
        self.weights = []

    def choices(self, population, weights, k):
        self.population = list(population)
        self.weights = list(weights)
        return [self.population[0]]


class TEntryPlannerTests(unittest.TestCase):
    def test_runtime_config_uses_confirmed_ten_percent_plan(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / "runtime" / "config" / "app_config.json").read_text(encoding="utf-8"))
        referers = {item.key: item for item in build_t_entry_referers(config)}

        self.assertEqual(16, len(referers))
        self.assertAlmostEqual(100.0, sum(item.weight for item in referers.values()))
        self.assertAlmostEqual(50.0, referers["major_search"].weight)
        self.assertAlmostEqual(10.0, referers["social"].weight)
        self.assertAlmostEqual(5.0, referers["removal_01"].weight)
        self.assertAlmostEqual(5.0, referers["removal_02"].weight)
        self.assertEqual(12, sum(1 for key in referers if key.startswith("other_")))
        self.assertTrue(all(math.isclose(referers[f"other_{index:02d}"].weight, 2.5) for index in range(1, 13)))

    def test_code_default_preserves_t1_five_percent_baseline(self):
        referers = build_t_entry_referers(DEFAULT_CONFIG)
        removal = [item for item in referers if item.entry_kind == "removal"]

        self.assertEqual(2, len(removal))
        self.assertAlmostEqual(5.0, sum(item.weight for item in removal))
        self.assertAlmostEqual(55.0, next(item.weight for item in referers if item.key == "major_search"))

    def test_only_two_sources_map_to_removal_page(self):
        planner = TEntryPlanner(config_with_removal_weight(10.0), rng=random.Random(17))
        removal_keys = {item.key for item in planner.referers if item.entry_kind == "removal"}

        self.assertEqual({"removal_01", "removal_02"}, removal_keys)
        for _ in range(2000):
            plan = planner.choose()
            expected_url = planner.removal_url if plan.referer_key in removal_keys else planner.home_url
            self.assertEqual(expected_url, plan.entry_url)

    def test_process_global_sequence_never_repeats_immediately(self):
        planner = TEntryPlanner(config_with_removal_weight(10.0), rng=random.Random(91))
        plans = [planner.choose() for _ in range(5000)]

        self.assertTrue(all(left.referer_key != right.referer_key for left, right in zip(plans, plans[1:])))
        self.assertEqual(list(range(1, 5001)), [plan.sequence_no for plan in plans])

    def test_last_referer_is_removed_before_exact_weights_are_passed_to_rng(self):
        rng = RecordingRng()
        planner = TEntryPlanner(config_with_removal_weight(10.0), rng=rng)
        planner.last_referer_key = "major_search"

        planner.choose()

        observed = {item.key: weight for item, weight in zip(rng.population, rng.weights)}
        self.assertNotIn("major_search", observed)
        self.assertAlmostEqual(10.0, observed["social"])
        self.assertAlmostEqual(5.0, observed["removal_01"])
        self.assertAlmostEqual(5.0, observed["removal_02"])
        self.assertTrue(all(math.isclose(observed[f"other_{index:02d}"], 2.5) for index in range(1, 13)))

    def test_concurrent_selection_is_atomic_and_globally_non_repeating(self):
        planner = TEntryPlanner(config_with_removal_weight(10.0), rng=random.Random(101))
        collected = []
        collected_lock = threading.Lock()

        def select_many(count):
            local = [planner.choose() for _ in range(count)]
            with collected_lock:
                collected.extend(local)

        with ThreadPoolExecutor(max_workers=32) as pool:
            futures = [pool.submit(select_many, 80) for _ in range(32)]
            for future in futures:
                future.result()

        ordered = sorted(collected, key=lambda plan: plan.sequence_no)
        self.assertEqual(2560, len(ordered))
        self.assertEqual(list(range(1, 2561)), [plan.sequence_no for plan in ordered])
        self.assertTrue(all(left.referer_key != right.referer_key for left, right in zip(ordered, ordered[1:])))

    def test_snapshot_reports_exact_expected_long_run_rate(self):
        planner = TEntryPlanner(config_with_removal_weight(10.0), rng=random.Random(1))
        snapshot = planner.snapshot()

        self.assertAlmostEqual(10.0, snapshot["nominal_removal_weight_pct"])
        self.assertAlmostEqual(13.058419243986255, snapshot["expected_long_run_removal_pct"])
        self.assertEqual(0, snapshot["selection_count"])
        planner.choose()
        self.assertEqual(1, planner.snapshot()["selection_count"])

    def test_seeded_long_run_selection_tracks_stationary_rate(self):
        planner = TEntryPlanner(config_with_removal_weight(10.0), rng=random.Random(24680))
        removal_count = sum(1 for _ in range(200000) if planner.choose().entry_kind == "removal")

        self.assertAlmostEqual(13.058419243986255, removal_count / 200000 * 100.0, delta=0.3)

    def test_valid_zero_and_sixty_percent_endpoints(self):
        zero = TEntryPlanner(config_with_removal_weight(0.0), rng=random.Random(3))
        self.assertAlmostEqual(0.0, zero.snapshot()["expected_long_run_removal_pct"])
        self.assertTrue(all(zero.choose().entry_kind == "home" for _ in range(1000)))

        sixty = TEntryPlanner(config_with_removal_weight(60.0), rng=random.Random(5))
        self.assertAlmostEqual(0.0, next(item.weight for item in sixty.referers if item.key == "major_search"))
        self.assertTrue(all(sixty.choose().referer_key != "major_search" for _ in range(1000)))

    def test_home_and_removal_urls_must_be_different(self):
        config = config_with_removal_weight(10.0)
        config["sources"]["source_t"].update({"entry_home_url": "https://example.invalid/", "entry_removal_url": "https://example.invalid/"})

        with self.assertRaises(ValueError):
            TEntryPlanner(config)

    def test_invalid_removal_weights_fail_closed(self):
        for value in (-0.01, 60.01, float("nan"), float("inf"), float("-inf"), "", "invalid", None, True, False):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    TEntryPlanner(config_with_removal_weight(value))


if __name__ == "__main__":
    unittest.main()
