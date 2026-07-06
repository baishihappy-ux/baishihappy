import json
import time
from pathlib import Path
from threading import RLock


_JSON_LOCKS = {}
_JSON_LOCKS_GUARD = RLock()


def _path_lock(path: Path):
    key = str(path.resolve())
    with _JSON_LOCKS_GUARD:
        lock = _JSON_LOCKS.get(key)
        if lock is None:
            lock = RLock()
            _JSON_LOCKS[key] = lock
        return lock


def write_json(path: Path, payload: dict):
    lock = _path_lock(path)
    with lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f"{path.name}.tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)


def read_json(path: Path, default=None):
    lock = _path_lock(path)
    with lock:
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
    path = state_dir / "status.json"
    lock = _path_lock(path)
    with lock:
        current = read_json(path, {}) or {}
        current.update({"updated_at": time.time(), **fields})
        write_json(path, current)
        return current


