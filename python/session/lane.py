import random
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from python.session.reuse_pattern import SessionReusePattern


SESSION_ID_MAX = 1_000_000


class SessionLaneState(str, Enum):
    NEW = "NEW"
    READY = "READY"
    BUSY = "BUSY"
    DEAD = "DEAD"
    EXPIRED = "EXPIRED"


class SessionIdAllocator:
    """T1-compatible numeric allocator: 1..999999, no reuse within a run."""

    def __init__(self, rng=None, max_id=SESSION_ID_MAX):
        self.max_id = int(max_id)
        if self.max_id < 2:
            raise ValueError("max_id must allow at least one positive session ID")
        self.rng = rng or random.SystemRandom()
        self.lock = threading.RLock()
        self.used = set()

    def allocate(self):
        with self.lock:
            if len(self.used) >= self.max_id - 1:
                raise RuntimeError("session ID space exhausted")
            candidate = int(self.rng.randint(1, self.max_id - 1))
            for _ in range(self.max_id - 1):
                if candidate not in self.used:
                    self.used.add(candidate)
                    return candidate
                candidate = candidate + 1 if candidate < self.max_id - 1 else 1
            raise RuntimeError("session ID allocation failed")


@dataclass
class SessionLane:
    session_id: int
    lane_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    state: SessionLaneState = SessionLaneState.NEW
    entry_url: str = ""
    entry_referer: str = ""
    chain_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: float = field(default_factory=time.time)
    last_request_at: float = 0.0
    next_ready_at: float = 0.0
    last_stage: str = ""
    parent_count: int = 0
    reuse_pattern: SessionReusePattern = field(default_factory=SessionReusePattern, repr=False)
    last_success_url: str = ""


class SessionLaneManager:
    def __init__(self, max_lanes=32, idle_ttl_ms=300000, urgent_remaining_ms=80000, allocator=None, clock=None):
        self.max_lanes = max(1, int(max_lanes))
        self.idle_ttl_seconds = max(1.0, int(idle_ttl_ms or 300000) / 1000.0)
        self.urgent_remaining_seconds = max(0.0, int(urgent_remaining_ms or 80000) / 1000.0)
        self.urgent_idle_seconds = max(0.0, self.idle_ttl_seconds - self.urgent_remaining_seconds)
        self.allocator = allocator or SessionIdAllocator()
        self.clock = clock or time.time
        self.lock = threading.RLock()
        self.lanes = {}

    def create(self, entry_url="", entry_referer=""):
        with self.lock:
            self.expire()
            live = sum(1 for lane in self.lanes.values() if lane.state not in {SessionLaneState.DEAD, SessionLaneState.EXPIRED})
            if live >= self.max_lanes:
                return None
            lane = SessionLane(session_id=self.allocator.allocate(), entry_url=entry_url, entry_referer=entry_referer)
            self.lanes[lane.lane_id] = lane
            return lane

    def begin_entry(self, lane):
        with self.lock:
            self._require_live(lane)
            if lane.state not in {SessionLaneState.NEW, SessionLaneState.READY}:
                raise RuntimeError("lane is not available for entry")
            lane.state = SessionLaneState.BUSY
            lane.last_stage = "entry"
            return lane

    def entry_succeeded(self, lane, now=None):
        with self.lock:
            self._require_live(lane)
            lane.state = SessionLaneState.READY
            lane.last_request_at = self.clock() if now is None else float(now)
            lane.last_stage = "entry"
            return lane

    def acquire_ready(self, now=None):
        with self.lock:
            now = self.clock() if now is None else float(now)
            self.expire(now)
            candidates = [
                lane for lane in self.lanes.values()
                if lane.state == SessionLaneState.READY and lane.next_ready_at <= now
            ]
            if not candidates:
                return None
            lane = min(candidates, key=lambda item: (not self.is_urgent(item, now), item.next_ready_at, item.created_at))
            lane.state = SessionLaneState.BUSY
            return lane

    def release(self, lane, stage, next_ready_at=0.0, now=None):
        with self.lock:
            self._require_live(lane)
            lane.state = SessionLaneState.READY
            lane.last_stage = str(stage)
            lane.last_request_at = self.clock() if now is None else float(now)
            lane.next_ready_at = max(0.0, float(next_ready_at or 0.0))
            if stage == "parent":
                lane.parent_count += 1
            return lane

    def mark_dead(self, lane, reason=""):
        with self.lock:
            if lane.lane_id in self.lanes:
                lane.state = SessionLaneState.DEAD
                lane.last_stage = reason or "dead"

    def is_urgent(self, lane, now=None):
        now = self.clock() if now is None else float(now)
        return bool(lane.last_request_at and now - lane.last_request_at >= self.urgent_idle_seconds)

    def expire(self, now=None):
        now = self.clock() if now is None else float(now)
        for lane in self.lanes.values():
            if lane.state == SessionLaneState.READY and lane.last_request_at and now - lane.last_request_at >= self.idle_ttl_seconds:
                lane.state = SessionLaneState.EXPIRED
                lane.last_stage = "idle_ttl"

    def snapshot(self):
        with self.lock:
            self.expire()
            counts = {state.value: 0 for state in SessionLaneState}
            urgent = 0
            now = self.clock()
            for lane in self.lanes.values():
                counts[lane.state.value] += 1
                urgent += int(lane.state == SessionLaneState.READY and self.is_urgent(lane, now))
            return {
                "max_lanes": self.max_lanes,
                "size": len(self.lanes),
                "states": counts,
                "urgent_ready": urgent,
                "urgent_idle_seconds": self.urgent_idle_seconds,
                "idle_ttl_seconds": self.idle_ttl_seconds,
            }

    def _require_live(self, lane):
        if lane is None or lane.lane_id not in self.lanes:
            raise KeyError("unknown session lane")
        if lane.state in {SessionLaneState.DEAD, SessionLaneState.EXPIRED}:
            raise RuntimeError("session lane is no longer live")
