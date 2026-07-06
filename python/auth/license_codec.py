import base64
import hashlib
import hmac
import json
import os
import time
import uuid


LICENSE_PREFIX = "DF8-"
DEFAULT_SECRET = "Workspace-License-Key-v1"


def _secret() -> bytes:
    return os.environ.get("APP_LICENSE_SECRET", DEFAULT_SECRET).encode("utf-8")


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_payload(payload: dict) -> str:
    return _b64encode(hmac.new(_secret(), _canonical(payload), hashlib.sha256).digest())


def verify_payload(payload: dict, signature: str) -> bool:
    return hmac.compare_digest(sign_payload(payload), signature or "")


def generate_authorization_code(machine_code: str, valid_days: int, max_concurrency: int, do_token: str) -> str:
    now = int(time.time())
    payload = {
        "v": 1,
        "machine_code": machine_code.strip().upper(),
        "valid_days": int(valid_days),
        "max_concurrency": int(max_concurrency),
        "do_token": do_token.strip(),
        "issued_at": now,
        "expires_at": now + int(valid_days) * 86400,
        "nonce": uuid.uuid4().hex,
    }
    envelope = {"v": 1, "n": payload["nonce"], "c": _b64encode(_canonical(payload)), "s": sign_payload(payload)}
    return LICENSE_PREFIX + _b64encode(_canonical(envelope))


def decode_authorization_code(code: str) -> dict:
    if not code.startswith(LICENSE_PREFIX):
        raise ValueError("authorization code must start with DF8-")
    envelope = json.loads(_b64decode(code[len(LICENSE_PREFIX):]).decode("utf-8"))
    payload = json.loads(_b64decode(envelope["c"]).decode("utf-8"))
    if not verify_payload(payload, envelope.get("s", "")):
        raise ValueError("authorization signature verification failed")
    return payload


