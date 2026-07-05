from enum import Enum


class SessionState(str, Enum):
    READY = "READY"
    BUSY = "BUSY"
    DEAD = "DEAD"
    WARMING = "WARMING"
