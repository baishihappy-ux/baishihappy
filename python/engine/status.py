import json
import time
from datetime import datetime, timezone
from pathlib import Path

from python.utils.paths import ensure_runtime_dirs
from python.utils.runtime_state import append_event, read_json, update_status, write_json


def runtime_info(root: Path):
    paths = ensure_runtime_dirs(root)
    return {key: str(value) for key, value in paths.items()}


def run_status(root: Path, log_lines=20):
    paths = ensure_runtime_dirs(root)
    status = read_json(paths["state"] / "status.json", {"status": "IDLE"})
    log_path = paths["logs"] / "runtime.log"
    logs = []
    if log_path.exists():
        logs = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-int(log_lines or 20):]
    return {"status": status, "logs": logs}


def pause(root: Path, reason="manual"):
    paths = ensure_runtime_dirs(root)
    now = _iso_now()
    payload = {
        "paused": True,
        "pause_requested": True,
        "stop_new_seed_requested": True,
        "reason": reason,
        "requested_at": time.time(),
        "updated_at": time.time(),
    }
    write_json(paths["state"] / "control.json", payload)
    write_json(paths["state"] / "pause_control.json", {
        "pause_requested": True,
        "stop_new_seed_requested": True,
        "updated_at": now,
        "pause_source": "client",
        "pause_requested_at": now,
        "pause_reason": reason or "user_pause_stop_new_seed_keep_active_running",
    })
    append_event(paths["state"], "pause_requested", reason=reason)
    status = update_status(paths["state"], pause_requested=True, pause_reason=reason)
    remaining = int(status.get("remaining_work") or status.get("remaining") or 0)
    active = int(status.get("scheduler_active_workers") or status.get("do_inflight_current") or 0)
    write_json(paths["state"] / "phone_pool_state.json", {
        "total_available": remaining,
        "total_consumed": int(status.get("customer_completed_seeds") or status.get("completed_seeds") or 0),
        "total_warm_reserved": 0,
        "total_paused_by_user": remaining,
        "phones": [],
        "pause_requested": True,
        "stop_new_seed_requested": True,
        "resume_requested_at": status.get("started_at", ""),
        "resume_source": status.get("resume_source", "run_start"),
        "updated_at": now,
        "last_resume_resumed_now": 0,
        "pause_requested_at": now,
        "pause_reason": reason or "user_pause_stop_new_seed_keep_active_running",
        "pause_source": "client",
    })
    return {
        "ok": True,
        "paused": True,
        "pauseVerified": True,
        "pause_requested": True,
        "reason": reason,
        "pauseState": {
            "root": str(paths["runtime"]),
            "totalAvailable": remaining,
            "totalPausedByUser": remaining,
            "activeWork": active,
            "pauseRequested": True,
        },
        "status": status,
    }


def resume(root: Path):
    paths = ensure_runtime_dirs(root)
    now = _iso_now()
    payload = {"paused": False, "pause_requested": False, "resumed_at": time.time(), "updated_at": time.time()}
    write_json(paths["state"] / "control.json", payload)
    write_json(paths["state"] / "pause_control.json", {
        "pause_requested": False,
        "stop_new_seed_requested": False,
        "updated_at": now,
        "resume_source": "client",
        "resume_requested_at": now,
    })
    pool = read_json(paths["state"] / "phone_pool_state.json", {}) or {}
    pool.update({
        "pause_requested": False,
        "stop_new_seed_requested": False,
        "resume_requested_at": now,
        "resume_source": "client",
        "updated_at": now,
        "last_resume_resumed_now": int(pool.get("total_paused_by_user") or 0),
        "total_paused_by_user": 0,
    })
    write_json(paths["state"] / "phone_pool_state.json", pool)
    append_event(paths["state"], "resume_requested")
    current = read_json(paths["state"] / "status.json", {}) or {}
    status_value = current.get("status")
    fields = {"pause_requested": False, "pause_reason": ""}
    if str(status_value).upper() in {"PAUSED", "PAUSING"}:
        fields["status"] = "RUNNING"
    status = update_status(paths["state"], **fields)
    return {"ok": True, "paused": False, "resumed": True, "pauseVerified": True, "pause_requested": False, "status": status}


def _iso_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
