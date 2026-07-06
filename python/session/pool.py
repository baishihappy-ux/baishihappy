from dataclasses import dataclass, field
import time
import uuid

from python.session.state import SessionState


@dataclass
class Session:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    chain_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    parent_id: str = ""
    state: SessionState = SessionState.WARMING
    created_at: float = field(default_factory=time.time)
    last_used_at: float = 0.0
    use_count: int = 0
    chain_depth: int = 0
    chain_breaks: int = 0
    recoveries: int = 0
    metadata: dict = field(default_factory=dict)


class SessionPool:
    def __init__(self, pool_size=10, reuse_seconds=3600, enabled=True):
        self.pool_size = int(pool_size or 0)
        self.reuse_seconds = int(reuse_seconds or 0)
        self.enabled = enabled
        self.sessions = []

    def warm(self, target=0):
        if not self.enabled:
            return
        target = min(self.pool_size, int(target or self.pool_size))
        while len(self.sessions) < target:
            session = Session()
            session.state = SessionState.READY
            self.sessions.append(session)

    def acquire(self):
        if not self.enabled:
            return None
        self._retire_expired()
        for session in self.sessions:
            if session.state == SessionState.READY:
                session.state = SessionState.BUSY
                session.last_used_at = time.time()
                session.use_count += 1
                return session
        if len(self.sessions) < self.pool_size:
            session = Session(state=SessionState.BUSY, last_used_at=time.time(), use_count=1)
            self.sessions.append(session)
            return session
        return None

    def release(self, session, ok=True, fatal=False, chain_ok=True):
        if not session:
            return
        if fatal:
            session.state = SessionState.DEAD
        elif not chain_ok:
            self.mark_chain_break(session)
        else:
            session.state = SessionState.READY if ok else SessionState.WARMING

    def propagate_chain(self, session):
        if not session:
            return None
        child = Session(
            chain_id=session.chain_id,
            parent_id=session.id,
            state=SessionState.READY,
            chain_depth=session.chain_depth + 1,
        )
        self.sessions.append(child)
        return child

    def mark_chain_break(self, session):
        session.chain_breaks += 1
        session.state = SessionState.DEAD

    def rebuild_chain(self, limit=1):
        live = [s for s in self.sessions if s.state != SessionState.DEAD and s.chain_depth <= limit]
        if live:
            for session in live:
                if session.state == SessionState.WARMING:
                    session.state = SessionState.READY
                    session.recoveries += 1
            self.sessions = live[: self.pool_size]
            return len(live)
        rebuilt = 0
        while rebuilt < max(1, min(self.pool_size, limit + 1)):
            session = Session(state=SessionState.READY)
            session.recoveries += 1
            self.sessions.append(session)
            rebuilt += 1
        return rebuilt

    def detect_instability(self):
        live = [s for s in self.sessions if s.state != SessionState.DEAD]
        total = max(1, len(self.sessions))
        dead_ratio = (len(self.sessions) - len(live)) / total
        break_count = sum(s.chain_breaks for s in self.sessions)
        return dead_ratio > 0.35 or break_count > max(2, total // 3)

    def snapshot(self):
        counts = {state.value: 0 for state in SessionState}
        chain_breaks = 0
        recoveries = 0
        for session in self.sessions:
            counts[session.state.value] += 1
            chain_breaks += session.chain_breaks
            recoveries += session.recoveries
        total = max(1, len(self.sessions))
        stability = max(0.0, 1.0 - (counts[SessionState.DEAD.value] / total) - min(0.5, chain_breaks / (total * 2)))
        return {
            "size": len(self.sessions),
            "states": counts,
            "chain_breaks": chain_breaks,
            "recoveries": recoveries,
            "stability": stability,
        }

    def _retire_expired(self):
        if not self.reuse_seconds:
            return
        now = time.time()
        for session in self.sessions:
            if session.state != SessionState.DEAD and now - session.created_at > self.reuse_seconds:
                session.state = SessionState.DEAD


