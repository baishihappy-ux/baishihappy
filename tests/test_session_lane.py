import unittest

from python.session.lane import SessionIdAllocator, SessionLaneManager, SessionLaneState


class FixedRng:
    def __init__(self, value):
        self.value = value

    def randint(self, _low, _high):
        return self.value


class SessionLaneTests(unittest.TestCase):
    def test_allocator_returns_unique_positive_t1_range_ids(self):
        allocator = SessionIdAllocator(rng=FixedRng(7), max_id=100)
        ids = [allocator.allocate() for _ in range(4)]
        self.assertEqual([7, 8, 9, 10], ids)
        self.assertTrue(all(1 <= value <= 99 for value in ids))

    def test_lane_reuses_session_after_entry_and_respects_next_ready(self):
        now = [1000.0]
        manager = SessionLaneManager(max_lanes=1, clock=lambda: now[0])
        lane = manager.create("home", "external")
        self.assertEqual(SessionLaneState.NEW, lane.state)
        manager.begin_entry(lane)
        manager.entry_succeeded(lane)
        manager.release(lane, "associate", next_ready_at=1010.0)
        self.assertIsNone(manager.acquire_ready())
        now[0] = 1010.0
        reused = manager.acquire_ready()
        self.assertIs(reused, lane)
        self.assertEqual(lane.session_id, reused.session_id)

    def test_urgent_ready_lane_is_preferred(self):
        now = [1000.0]
        manager = SessionLaneManager(max_lanes=2, clock=lambda: now[0])
        first = manager.create()
        second = manager.create()
        manager.entry_succeeded(first, now=780.0)
        manager.entry_succeeded(second, now=900.0)
        chosen = manager.acquire_ready(now=1000.0)
        self.assertIs(first, chosen)

    def test_idle_ttl_expires_ready_lane(self):
        now = [1000.0]
        manager = SessionLaneManager(max_lanes=1, clock=lambda: now[0])
        lane = manager.create()
        manager.entry_succeeded(lane, now=700.0)
        now[0] = 1000.0
        self.assertEqual(SessionLaneState.EXPIRED, lane.state if manager.snapshot() else lane.state)
        self.assertIsNone(manager.acquire_ready())

    def test_lane_limit_is_hard_and_dead_lane_does_not_block_replacement(self):
        manager = SessionLaneManager(max_lanes=1)
        lane = manager.create()
        self.assertIsNone(manager.create())
        manager.mark_dead(lane, "entry_failed")
        replacement = manager.create()
        self.assertIsNotNone(replacement)
        self.assertNotEqual(lane.session_id, replacement.session_id)


if __name__ == "__main__":
    unittest.main()
