import base64
import hashlib
import json
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from python.auth.license_public_keys import PUBLIC_KEYS


LICENSE_PREFIX = "DF9-"
LICENSE_VERSION = 2
MACHINE_CODE_RE = re.compile(r"^[A-F0-9]{32}$")


def b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def key_id_from_public_bytes(public_bytes: bytes) -> str:
    return hashlib.sha256(public_bytes).hexdigest()[:32]


def decode_authorization_code(code: str, public_keys=None) -> dict:
    text = str(code or "").strip()
    if not text.startswith(LICENSE_PREFIX):
        raise ValueError(f"authorization code must start with {LICENSE_PREFIX}")
    try:
        envelope = json.loads(b64decode(text[len(LICENSE_PREFIX):]).decode("utf-8"))
        version = int(envelope.get("v") or 0)
        key_id = str(envelope.get("kid") or "")
        payload_bytes = b64decode(str(envelope.get("p") or ""))
        signature = b64decode(str(envelope.get("s") or ""))
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception as exc:
        raise ValueError("license envelope is invalid") from exc
    if version != LICENSE_VERSION or int(payload.get("v") or 0) != LICENSE_VERSION:
        raise ValueError("unsupported license version")
    if payload.get("key_id") != key_id:
        raise ValueError("license key id mismatch")
    keys = PUBLIC_KEYS if public_keys is None else public_keys
    public_b64 = keys.get(key_id)
    if not public_b64:
        raise ValueError("license signing key is not trusted")
    try:
        public_bytes = b64decode(public_b64)
        if key_id_from_public_bytes(public_bytes) != key_id:
            raise ValueError("trusted public key fingerprint mismatch")
        Ed25519PublicKey.from_public_bytes(public_bytes).verify(signature, payload_bytes)
    except InvalidSignature as exc:
        raise ValueError("authorization signature verification failed") from exc
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("trusted public key is invalid") from exc
    _validate_payload(payload)
    return payload


def _validate_payload(payload: dict):
    machine = str(payload.get("machine_code") or "").upper()
    if not MACHINE_CODE_RE.fullmatch(machine):
        raise ValueError("authorization machine code is invalid")
    valid_days = _positive_int(payload.get("valid_days"), "valid days")
    _positive_int(payload.get("max_concurrency"), "max concurrency")
    issued_at = _positive_int(payload.get("issued_at"), "issued time")
    expires_at = _positive_int(payload.get("expires_at"), "expiry time")
    if expires_at != issued_at + valid_days * 86400:
        raise ValueError("authorization expiry is inconsistent")
    if not str(payload.get("do_token") or "").strip():
        raise ValueError("provider token is required")
    if not re.fullmatch(r"[0-9a-f]{32}", str(payload.get("nonce") or "")):
        raise ValueError("authorization nonce is invalid")


def _positive_int(value, label):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"authorization {label} is invalid") from exc
    if parsed <= 0:
        raise ValueError(f"authorization {label} must be positive")
    return parsed
