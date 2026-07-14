import unittest

from python.session.reuse_pattern import PATTERNS, SessionReusePattern


class SessionReusePatternTests(unittest.TestCase):
    def test_patterns_are_exactly_the_three_t1_permutations(self):
        self.assertEqual(("ABB", "BAB", "BBA"), PATTERNS)

    def test_consumes_three_parent_numbers_in_order(self):
        pattern = SessionReusePattern("BAB")
        self.assertEqual(["B", "A", "B"], [pattern.next_kind(), pattern.next_kind(), pattern.next_kind()])
        self.assertIsNone(pattern.next_kind())
        self.assertTrue(pattern.exhausted)
        self.assertEqual(3, pattern.completed_count)

    def test_rejects_other_shapes(self):
        with self.assertRaises(ValueError):
            SessionReusePattern("AAA")

