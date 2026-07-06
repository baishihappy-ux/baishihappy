from pathlib import Path

from python.engine.status import run_status
from python.utils.paths import ensure_runtime_dirs
from python.utils.runtime_state import read_json


def analyze_run(root=".") -> dict:
    root = Path(root).resolve()
    paths = ensure_runtime_dirs(root)
    status = read_json(paths["state"] / "status.json", {}) or {}
    output_dir = paths["output"]
    failed = _line_count(output_dir / "failed_tasks.txt")
    final_502 = _line_count(output_dir / "final_502_discarded.txt")
    results = _line_count(output_dir / "results.txt")
    return {
        "ok": True,
        "status": status.get("status", "IDLE"),
        "processed": int(status.get("processed") or 0),
        "saved": int(status.get("saved") or results),
        "results_lines": results,
        "failed_lines": failed,
        "final_502_discarded": final_502,
        "remaining_work": int(status.get("remaining_work") or status.get("remaining") or 0),
        "runtime": run_status(root, log_lines=20),
    }


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len([line for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()])


