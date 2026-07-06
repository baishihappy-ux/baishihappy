import time
from datetime import datetime, timezone
from pathlib import Path

from python.parser.source_profiles import build_entry_url
from python.queue.tasks import Task, TaskStage
from python.utils.phone import normalize_phone
from python.utils.runtime_state import read_json, write_json


SOURCE_A_NAME = "鍙风爜琛ラ綈鐖剁骇input"
SOURCE_B_NAME = "瑁傚彉鍏宠仈浜虹埗绾nput"


class InputPool:
    def __init__(self, root: Path, state_dir: Path, config: dict, input_path: Path, target_source: str):
        self.root = root
        self.state_dir = state_dir
        self.config = config
        self.input_path = input_path
        self.target_source = target_source
        self.cursor_path = state_dir / "input_cursor.json"
        self.claim_path = state_dir / "input_claims.json"
        self.distribution_path = state_dir / "input_distribution.json"
        self.dual_cursor_path = state_dir / "t_dual_input_cursor.json"
        self.dual_pending_path = state_dir / "t_dual_input_pending.json"
        self.dual_summary_path = state_dir / "t_dual_input_summary.json"
        self.items = []
        self.phones = []
        self.claimed = {}
        self.completed = set()
        self.recovered_502 = set()
        self.failed = set()
        self.cursor_by_source = {"A": 0, "B": 0, self.target_source: 0}
        self.sources = []

    def load(self):
        self.sources = self._discover_sources()
        self.items = []
        for source in self.sources:
            self.items.extend(self._read_source_items(source))
        self.phones = [item["phone"] for item in self.items]
        self._load_terminal_state()
        self._load_claims()
        self._refresh_cursors()
        self.write_all_state()
        return self

    def seed_scheduler(self, scheduler):
        count = 0
        for item in self.items:
            if item["key"] in self.terminal_keys():
                continue
            scheduler.submit(self.build_task(item))
            count += 1
        self.write_all_state()
        return count

    def build_task(self, item):
        phone = item["phone"]
        url = build_entry_url(self.config, self.target_source, phone)
        return Task(
            phone=phone,
            stage=TaskStage.RESULTPHONE,
            target_source=self.target_source,
            url=url,
            seed_phone=phone,
            line_number=item["line_number"],
            source_bucket=item["source"],
            source_name=item["source_name"],
        )

    def mark_claimed(self, task):
        key = self.task_key(task)
        if key not in self.item_keys():
            return
        self.claimed[key] = {
            "phone": task.phone,
            "source": task.source_bucket or self.target_source,
            "source_name": task.source_name or "",
            "line_number": int(task.line_number or 0),
            "session_id": 0,
            "worker_id": 0,
            "claimed_at": _iso_now(),
            "run_id": self.config.get("runtime", {}).get("run_id", ""),
        }
        self.write_claims()
        self.write_dual_pending()

    def mark_completed(self, task):
        self._mark_terminal(task, self.completed, remove_from=(self.recovered_502, self.failed))

    def mark_recovered_502(self, task):
        self._mark_terminal(task, self.recovered_502, remove_from=(self.failed,))

    def mark_failed(self, task):
        self._mark_terminal(task, self.failed)

    def task_key(self, task):
        source = task.source_bucket or self.target_source
        return f"{source}:{task.phone}"

    def item_keys(self):
        return {item["key"] for item in self.items}

    def terminal_keys(self):
        return self.completed | self.recovered_502 | self.failed

    def terminal_count(self):
        return len(self.terminal_keys())

    def remaining_count(self):
        return max(0, len(self.items) - self.terminal_count())

    def completed_count(self):
        return len(self.completed)

    def recovered_502_count(self):
        return len(self.recovered_502)

    def failed_count(self):
        return len(self.failed)

    def write_all_state(self):
        self.write_cursor()
        self.write_claims()
        self.write_distribution()
        self.write_dual_cursor()
        self.write_dual_pending()
        self.write_dual_summary()

    def write_cursor(self):
        write_json(self.cursor_path, {
            "cursor": min(self.cursor_by_source.values()) if self.cursor_by_source else 0,
            "total_unique_input": len(self.items),
            "completed_count": len(self.completed),
            "completed_phones": sorted(self._phones_for_keys(self.completed)),
            "completed_keys": sorted(self.completed),
            "recovered_502_count": len(self.recovered_502),
            "recovered_502_phones": sorted(self._phones_for_keys(self.recovered_502)),
            "recovered_502_keys": sorted(self.recovered_502),
            "failed_count": len(self.failed),
            "failed_phones": sorted(self._phones_for_keys(self.failed)),
            "failed_keys": sorted(self.failed),
            "input_file": str(self.input_path),
            "updated_at": time.time(),
        })

    def write_claims(self):
        write_json(self.claim_path, {"claimed": self.claimed, "updated_at": time.time()})

    def write_distribution(self):
        write_json(self.distribution_path, {
            "input_file": str(self.input_path),
            "total_rows": len(self.items),
            "imported_rows": len(self.items),
            "cursor": min(self.cursor_by_source.values()) if self.cursor_by_source else 0,
            "completed_count": len(self.completed),
            "recovered_502_count": len(self.recovered_502),
            "failed_count": len(self.failed),
            "claimed_unfinished": len(self.claimed),
            "terminal_count": self.terminal_count(),
            "remaining_rows": self.remaining_count(),
            "sources": self._source_counts(),
            "updated_at": time.time(),
        })

    def write_dual_cursor(self):
        a = self._source_meta("A")
        b = self._source_meta("B")
        write_json(self.dual_cursor_path, {
            "updated_at": _iso_now(local=False),
            "a_input_file": str(a["path"]) if a else "",
            "b_input_file": str(b["path"]) if b else "",
            "a_cursor": self.cursor_by_source.get("A", 0),
            "b_cursor": self.cursor_by_source.get("B", 0),
            "a_total": self._source_total("A"),
            "b_total": self._source_total("B"),
            "a_remaining": self._source_remaining("A"),
            "b_remaining": self._source_remaining("B"),
        })

    def write_dual_pending(self):
        write_json(self.dual_pending_path, {
            "updated_at": _iso_now(local=False),
            "a_input_file": str(self._source_path("A")),
            "b_input_file": str(self._source_path("B")),
            "items": self.claimed,
        })

    def write_dual_summary(self):
        a_total = self._source_total("A")
        b_total = self._source_total("B")
        a_cursor = self.cursor_by_source.get("A", 0)
        b_cursor = self.cursor_by_source.get("B", 0)
        write_json(self.dual_summary_path, {
            "updated_at": _iso_now(local=False),
            "mode": "t_dual_input_cursor" if len(self.sources) > 1 else "single_input_cursor",
            "a_input_file": str(self._source_path("A")),
            "b_input_file": str(self._source_path("B")),
            "a_total": a_total,
            "b_total": b_total,
            "a_cursor": a_cursor,
            "b_cursor": b_cursor,
            "a_remaining": self._source_remaining("A"),
            "b_remaining": self._source_remaining("B"),
            "total_available": self.remaining_count(),
            "last_finished": self._last_finished_phone(),
        })

    def _discover_sources(self):
        a_path = self.root / "鍙风爜琛ラ綈鐖剁骇input.txt"
        b_path = self.root / "瑁傚彉鍏宠仈浜虹埗绾nput.txt"
        if self.target_source == "T" and (a_path.exists() or b_path.exists()):
            sources = []
            if a_path.exists():
                sources.append({"source": "A", "source_name": SOURCE_A_NAME, "path": a_path})
            if b_path.exists():
                sources.append({"source": "B", "source_name": SOURCE_B_NAME, "path": b_path})
            return sources
        return [{"source": self.target_source, "source_name": self.input_path.stem, "path": self.input_path}]

    def _read_source_items(self, source):
        path = source["path"]
        rows = path.read_text(encoding="utf-8", errors="ignore").splitlines() if path.exists() else []
        items = []
        seen = set()
        for line_number, row in enumerate(rows, start=1):
            phone = normalize_phone(row)
            if not phone or phone in seen:
                continue
            seen.add(phone)
            key = f"{source['source']}:{phone}"
            items.append({
                "key": key,
                "phone": phone,
                "source": source["source"],
                "source_name": source["source_name"],
                "line_number": line_number,
                "path": str(path),
            })
        return items

    def _load_terminal_state(self):
        state = read_json(self.cursor_path, {}) or {}
        old_input = str(state.get("input_file") or "")
        same_input = old_input in {"", str(self.input_path)} or len(self.sources) > 1
        if not same_input:
            return
        self.completed = self._keys_from_state(state, "completed")
        self.recovered_502 = self._keys_from_state(state, "recovered_502")
        self.failed = self._keys_from_state(state, "failed")

    def _load_claims(self):
        claims = read_json(self.claim_path, {}) or {}
        pending = read_json(self.dual_pending_path, {}) or {}
        raw = {}
        raw.update(claims.get("claimed") or {})
        raw.update(pending.get("items") or {})
        valid_keys = self.item_keys()
        self.claimed = {
            key: payload for key, payload in raw.items()
            if key in valid_keys and key not in self.terminal_keys()
        }

    def _keys_from_state(self, state, prefix):
        keys = set(state.get(f"{prefix}_keys", []) or [])
        phones = set(state.get(f"{prefix}_phones", []) or [])
        if phones and not keys:
            keys = {item["key"] for item in self.items if item["phone"] in phones}
        return keys & self.item_keys()

    def _mark_terminal(self, task, target_set, remove_from=()):
        key = self.task_key(task)
        if key not in self.item_keys():
            return
        target_set.add(key)
        for other in remove_from:
            other.discard(key)
        self.claimed.pop(key, None)
        self._refresh_cursors()
        self.write_all_state()

    def _refresh_cursors(self):
        terminal = self.terminal_keys()
        for source in {item["source"] for item in self.items} | {"A", "B", self.target_source}:
            source_items = [item for item in self.items if item["source"] == source]
            cursor = 0
            while cursor < len(source_items) and source_items[cursor]["key"] in terminal:
                cursor += 1
            self.cursor_by_source[source] = cursor

    def _source_counts(self):
        return {
            source: {
                "total": self._source_total(source),
                "cursor": self.cursor_by_source.get(source, 0),
                "remaining": self._source_remaining(source),
            }
            for source in sorted({item["source"] for item in self.items})
        }

    def _source_meta(self, source):
        return next((item for item in self.sources if item["source"] == source), None)

    def _source_path(self, source):
        meta = self._source_meta(source)
        return meta["path"] if meta else ""

    def _source_total(self, source):
        return sum(1 for item in self.items if item["source"] == source)

    def _source_remaining(self, source):
        terminal = self.terminal_keys()
        return sum(1 for item in self.items if item["source"] == source and item["key"] not in terminal)

    def _phones_for_keys(self, keys):
        by_key = {item["key"]: item["phone"] for item in self.items}
        return [by_key[key] for key in keys if key in by_key]

    def _last_finished_phone(self):
        terminal = self.terminal_keys()
        for item in reversed(self.items):
            if item["key"] in terminal:
                return item["phone"]
        return ""


def _iso_now(local=True):
    dt = datetime.now() if local else datetime.now(timezone.utc)
    value = dt.replace(microsecond=0).isoformat()
    return value.replace("+00:00", "Z")


