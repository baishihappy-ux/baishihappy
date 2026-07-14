from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time
import uuid


class TaskStage(str, Enum):
    ENTRY = "entry"
    RESULTPHONE = "resultphone"
    PARENT = "parent"
    ASSOCIATE = "associate"


@dataclass
class Task:
    phone: str
    stage: TaskStage = TaskStage.ENTRY
    target_source: str = "T"
    url: Optional[str] = None
    depth: int = 0
    seed_phone: Optional[str] = None
    line_number: int = 0
    source_bucket: str = ""
    source_name: str = ""
    session_id: int = 0
    chain_id: str = ""
    referer: str = ""
    entry_referer_key: str = ""
    entry_kind: str = ""
    remaining_associate_urls: list = field(default_factory=list)
    is_session_bootstrap: bool = False
    terminal_on_success: bool = True
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    attempts: int = 0
    not_before: float = 0.0
    created_at: float = field(default_factory=time.time)
