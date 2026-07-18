import argparse
import getpass
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from python.auth.license_codec import b64encode, key_id_from_public_bytes
from python.auth.license_public_keys import ACTIVE_KEY_ID, PUBLIC_KEYS
from python.auth.windows_dpapi import protect_current_user


def import_recovery(input_path: Path, passphrase: bytes, output: Path):
    private_key = serialization.load_pem_private_key(input_path.read_bytes(), password=passphrase)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("Recovery key is not Ed25519.")
    private_raw = private_key.private_bytes_raw()
    public_raw = private_key.public_key().public_bytes_raw()
    key_id = key_id_from_public_bytes(public_raw)
    if key_id != ACTIVE_KEY_ID or PUBLIC_KEYS.get(key_id) != b64encode(public_raw):
        raise ValueError("Recovery key does not match the active customer public key.")
    path = output.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema": "dingfeng-ed25519-private-dpapi-v1",
        "key_id": key_id,
        "public_key": b64encode(public_raw),
        "protected_private_key": b64encode(protect_current_user(private_raw)),
        "created_at": int(time.time()),
        "dpapi_scope": "current_user",
    }
    with path.open("x", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return path, key_id


def main(argv=None):
    parser = argparse.ArgumentParser(description="Restore the issuer key into this Windows user's DPAPI store.")
    parser.add_argument("--input", default=".package-secrets/authorization/issuer_private_key.recovery.pem")
    parser.add_argument("--output", default=".package-secrets/authorization/issuer_private_key.dpapi.json")
    args = parser.parse_args(argv)
    passphrase = getpass.getpass("Recovery passphrase: ").encode("utf-8")
    try:
        output, key_id = import_recovery(Path(args.input), passphrase, Path(args.output))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps({"ok": True, "key_id": key_id, "private_key_file": str(output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
