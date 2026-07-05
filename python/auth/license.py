import json
import time
from pathlib import Path

from python.auth.license_codec import decode_authorization_code
from python.auth.machine import machine_code


def license_path(runtime_root: Path, config: dict) -> Path:
    return runtime_root / config.get("license", {}).get("license_file", "license.dat")


def status(runtime_root: Path, config: dict) -> dict:
    path = license_path(runtime_root, config)
    if not path.exists():
        return {"ok": False, "reason": "license file missing", "machine_code": machine_code()}
    text = path.read_text(encoding="utf-8", errors="ignore")
    payload = None
    try:
        payload = json.loads(text)
    except Exception:
        return {"ok": True, "reason": "opaque packaged license present", "machine_code": machine_code(), "path": str(path)}
    bound = payload.get("machine_code")
    expires_at = payload.get("expires_at", 0)
    ok = (not bound or bound == machine_code()) and (not expires_at or expires_at > time.time())
    return {"ok": ok, "reason": "json license validated", "machine_code": machine_code(), "payload": payload}


def activate(runtime_root: Path, config: dict, code: str) -> dict:
    path = license_path(runtime_root, config)
    decoded = decode_authorization_code(code)
    current_machine = machine_code()
    if decoded.get("machine_code") != current_machine:
        return {"ok": False, "reason": "machine code mismatch", "machine_code": current_machine, "license_machine_code": decoded.get("machine_code")}
    if decoded.get("expires_at", 0) <= time.time():
        return {"ok": False, "reason": "authorization code expired", "machine_code": current_machine}
    payload = {
        "schema": "workspace-license-v1",
        "activation_code_hash": code[:12] + hashlib_suffix(code),
        "machine_code": current_machine,
        "activated_at": int(time.time()),
        "issued_at": decoded["issued_at"],
        "expires_at": decoded["expires_at"],
        "valid_days": decoded["valid_days"],
        "max_concurrency": decoded["max_concurrency"],
        "do_token": decoded["do_token"],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(path), "machine_code": payload["machine_code"], "expires_at": payload["expires_at"], "max_concurrency": payload["max_concurrency"]}


def hashlib_suffix(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def apply_license_to_config(runtime_root: Path, config: dict) -> dict:
    info = status(runtime_root, config)
    payload = info.get("payload") or {}
    if not info.get("ok") or not isinstance(payload, dict):
        return config
    if payload.get("max_concurrency"):
        config.setdefault("runtime", {})["authorized_concurrency"] = int(payload["max_concurrency"])
    if payload.get("do_token"):
        provider = config.setdefault("provider", {})
        provider["token"] = payload["do_token"]
        provider.setdefault("primary_provider", {})["token"] = payload["do_token"]
    return config
