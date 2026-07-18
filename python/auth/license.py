import hashlib
import time
from pathlib import Path

from python.auth.license_codec import decode_authorization_code
from python.auth.machine import machine_code


def license_path(runtime_root: Path, config: dict) -> Path:
    return runtime_root / config.get("license", {}).get("license_file", "license.dat")


def status(runtime_root: Path, config: dict) -> dict:
    result = _verified_license(runtime_root, config)
    payload = result.pop("_payload", None)
    result.pop("_code", None)
    if not result.get("ok") or not payload:
        return result
    return {
        **result,
        "valid": True,
        "license_machine_code": payload["machine_code"],
        "valid_days": payload["valid_days"],
        "issued_at": payload["issued_at"],
        "expires_at": payload["expires_at"],
        "max_concurrency": payload["max_concurrency"],
        "max_instances": payload["max_concurrency"],
        "key_id": payload["key_id"],
        "license_id": result["license_fingerprint"][:24],
    }


def activate(runtime_root: Path, config: dict, code: str) -> dict:
    current_machine = machine_code()
    try:
        decoded = decode_authorization_code(code)
    except Exception as exc:
        return {"ok": False, "valid": False, "reason": str(exc), "machine_code": current_machine}
    if decoded.get("machine_code") != current_machine:
        return {
            "ok": False,
            "valid": False,
            "reason": "machine code mismatch",
            "machine_code": current_machine,
            "license_machine_code": decoded.get("machine_code"),
        }
    if int(decoded.get("expires_at") or 0) <= time.time():
        return {"ok": False, "valid": False, "reason": "authorization code expired", "machine_code": current_machine}
    path = license_path(runtime_root, config)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(str(code).strip() + "\n", encoding="utf-8")
    temporary.replace(path)
    return status(runtime_root, config)


def apply_license_to_config(runtime_root: Path, config: dict) -> dict:
    verified = _verified_license(runtime_root, config)
    payload = verified.get("_payload") or {}
    if not verified.get("ok") or not payload:
        return config
    config.setdefault("runtime", {})["authorized_concurrency"] = int(payload["max_concurrency"])
    provider = config.setdefault("provider", {})
    provider["token"] = payload["do_token"]
    provider.setdefault("primary_provider", {})["token"] = payload["do_token"]
    return config


def _verified_license(runtime_root: Path, config: dict) -> dict:
    path = license_path(runtime_root, config)
    current_machine = machine_code()
    if not path.exists():
        return {"ok": False, "valid": False, "reason": "license file missing", "machine_code": current_machine}
    try:
        code = path.read_text(encoding="utf-8", errors="strict").strip()
    except Exception:
        return {"ok": False, "valid": False, "reason": "license file cannot be read", "machine_code": current_machine, "path": str(path)}
    try:
        payload = decode_authorization_code(code)
    except Exception as exc:
        return {"ok": False, "valid": False, "reason": str(exc), "machine_code": current_machine, "path": str(path)}
    if payload.get("machine_code") != current_machine:
        return {
            "ok": False,
            "valid": False,
            "reason": "machine code mismatch",
            "machine_code": current_machine,
            "license_machine_code": payload.get("machine_code"),
            "path": str(path),
        }
    if int(payload.get("expires_at") or 0) <= time.time():
        return {"ok": False, "valid": False, "reason": "authorization code expired", "machine_code": current_machine, "path": str(path)}
    return {
        "ok": True,
        "valid": True,
        "reason": "authorization signature validated",
        "machine_code": current_machine,
        "path": str(path),
        "license_fingerprint": hashlib.sha256(code.encode("utf-8")).hexdigest(),
        "_payload": payload,
        "_code": code,
    }
