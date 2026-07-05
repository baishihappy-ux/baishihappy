import time
from pathlib import Path

from python.engine.status import run_status


def observe(root=".", refresh_seconds=1.0, log_lines=20, once=False):
    root = Path(root).resolve()
    while True:
        payload = run_status(root, log_lines=log_lines)
        status = payload.get("status", {})
        print(
            f"status={status.get('status', 'IDLE')} "
            f"processed={status.get('processed', 0)} "
            f"saved={status.get('saved', 0)} "
            f"remaining={status.get('remaining_work', status.get('remaining', 0))} "
            f"inflight={status.get('scheduler_do_inflight_current', 0)}"
        )
        if once:
            return payload
        time.sleep(float(refresh_seconds or 1.0))
