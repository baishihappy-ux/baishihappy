import json
import os
import sys
import time
import uuid
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from python.auth.license_codec import LICENSE_PREFIX, LICENSE_VERSION, b64decode, b64encode, canonical, key_id_from_public_bytes
from python.auth.license_public_keys import ACTIVE_KEY_ID, PUBLIC_KEYS
from python.auth.windows_dpapi import unprotect_current_user


PRIVATE_KEY_ENV = "DINGFENG_LICENSE_PRIVATE_KEY_FILE"


def generate_authorization_code(machine_code: str, valid_days: int, max_concurrency: int, do_token: str) -> str:
    private_key, key_id = load_issuer_private_key()
    return generate_with_private_key(
        machine_code, valid_days, max_concurrency, do_token,
        private_key=private_key, key_id=key_id,
    )


def generate_with_private_key(machine_code: str, valid_days: int, max_concurrency: int, do_token: str,
                              private_key: Ed25519PrivateKey, key_id: str, issued_at=None) -> str:
    machine = str(machine_code or "").strip().upper()
    days = int(valid_days)
    concurrency = int(max_concurrency)
    token = str(do_token or "").strip()
    if days <= 0:
        raise ValueError("Valid Days must be positive")
    if concurrency <= 0:
        raise ValueError("Max Windows must be positive")
    if not token:
        raise ValueError("Provider Token is required")
    now = int(time.time()) if issued_at is None else int(issued_at)
    payload = {
        "v": LICENSE_VERSION,
        "key_id": key_id,
        "machine_code": machine,
        "valid_days": days,
        "max_concurrency": concurrency,
        "do_token": token,
        "issued_at": now,
        "expires_at": now + days * 86400,
        "nonce": uuid.uuid4().hex,
    }
    payload_bytes = canonical(payload)
    envelope = {
        "v": LICENSE_VERSION,
        "kid": key_id,
        "p": b64encode(payload_bytes),
        "s": b64encode(private_key.sign(payload_bytes)),
    }
    return LICENSE_PREFIX + b64encode(canonical(envelope))


def load_issuer_private_key(path=None):
    private_path = Path(path).resolve() if path else resolve_private_key_path()
    try:
        record = json.loads(private_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"issuer private key is missing: {private_path}") from exc
    except Exception as exc:
        raise RuntimeError("issuer private key record is invalid") from exc
    key_id = str(record.get("key_id") or "")
    if not key_id or key_id != ACTIVE_KEY_ID or key_id not in PUBLIC_KEYS:
        raise RuntimeError("issuer private key does not match the active customer public key")
    raw_private = unprotect_current_user(b64decode(str(record.get("protected_private_key") or "")))
    private_key = Ed25519PrivateKey.from_private_bytes(raw_private)
    public_raw = private_key.public_key().public_bytes_raw()
    if key_id_from_public_bytes(public_raw) != key_id or b64encode(public_raw) != PUBLIC_KEYS[key_id]:
        raise RuntimeError("issuer private key fingerprint mismatch")
    return private_key, key_id


def resolve_private_key_path():
    configured = str(os.environ.get(PRIVATE_KEY_ENV) or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    relative = Path(".package-secrets") / "authorization" / "issuer_private_key.dpapi.json"
    candidates = [Path.cwd() / relative]
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        candidates.extend(parent / relative for parent in list(executable.parents)[:3])
    else:
        candidates.append(Path(__file__).resolve().parents[2] / relative)
    return next((path.resolve() for path in candidates if path.exists()), candidates[0].resolve())
