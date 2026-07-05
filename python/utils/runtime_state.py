import json
import time
from pathlib import Path


def write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def append_event(state_dir: Path, event: str, **fields):
    payload = {"ts": time.time(), "event": event, **fields}
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / "events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def update_status(state_dir: Path, **fields):
    current = read_json(state_dir / "status.json", {}) or {}
    current.update({"updated_at": time.time(), **fields})
    write_json(state_dir / "status.json", current)
    return current
