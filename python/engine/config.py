import json
from pathlib import Path

from python.utils.paths import config_path, runtime_root


DEFAULT_CONFIG = {
    "app_name": "Workspace App",
    "input_file": "../input.txt",
    "provider": {
        "active": "primary_provider",
        "timeout_seconds": 90,
        "retry_count": 1,
        "headers": {"User-Agent": "WorkspaceClient/1.0"},
        "network": {"proxy": "", "verify_ssl": True},
        "primary_provider": {
            "params": {"super": True, "geoCode": "us", "device": "desktop", "timeout": 60000, "output": "raw"},
            "session_pool": {"enabled": True, "pool_size": 10, "reuse_seconds": 3600},
        },
    },
    "sources": {},
    "processing": {"max_depth": 1, "max_total_records": 0, "queue_poll_seconds": 0.2, "thread_count": 0},
    "output": {
        "formats": ["csv", "txt"],
        "csv_file": "output/results.csv",
        "txt_file": "output/results.txt",
        "failed_file": "output/failed_tasks.txt",
        "final_502_discarded_file": "output/final_502_discarded.txt",
    },
    "license": {"license_file": "license.dat", "valid_days": 30},
    "runtime": {"smart_session_enabled": True, "target_source": "T", "customer_mode": True},
    "logging": {},
}


def deep_merge(base, override):
    result = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(root: Path) -> dict:
    path = config_path(root)
    if not path.exists():
        return DEFAULT_CONFIG
    loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    return deep_merge(DEFAULT_CONFIG, loaded)


def resolve_input_file(root: Path, config: dict, override=None) -> Path:
    if override:
        return Path(override).resolve()
    runtime = config.get("runtime", {})
    if runtime.get("target_source") == "T":
        package_root = runtime_root(root).parent
        for name in ["鍙风爜琛ラ綈鐖剁骇input.txt", "瑁傚彉鍏宠仈浜虹埗绾nput.txt", "input.txt"]:
            candidate = package_root / name
            if candidate.exists() and candidate.stat().st_size > 0:
                return candidate.resolve()
    raw = config.get("input_file") or "../input.txt"
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    resolved = (runtime_root(root) / "config" / candidate).resolve()
    if not resolved.exists():
        package_candidate = runtime_root(root).parent / candidate.name
        if package_candidate.exists():
            return package_candidate.resolve()
    return resolved


