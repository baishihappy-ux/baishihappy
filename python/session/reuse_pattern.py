"""T1 mixed parent-phone reuse pattern.

A is the full search->detail->associate chain; B is search-only.
"""
import random

PATTERNS = ("ABB", "BAB", "BBA")


class SessionReusePattern:
    def __init__(self, pattern=None, chooser=None):
        self.pattern = pattern or (chooser or random.choice)(PATTERNS)
        if self.pattern not in PATTERNS:
            raise ValueError("pattern must be ABB, BAB, or BBA")
        self.index = 0

    @property
    def exhausted(self):
        return self.index >= len(self.pattern)

    @property
    def completed_count(self):
        return self.index

    def next_kind(self):
        if self.exhausted:
            return None
        kind = self.pattern[self.index]
        self.index += 1
        return kind

    def snapshot(self):
        return {"pattern": self.pattern, "index": self.index, "completed_count": self.completed_count,
                "exhausted": self.exhausted}
