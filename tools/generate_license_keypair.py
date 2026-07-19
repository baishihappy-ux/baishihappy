import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from python.auth.license_codec import b64encode, key_id_from_public_bytes
from python.auth.windows_dpapi import protect_current_user


def generate_keypair(private_key_file: Path):
    path = private_key_file.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    private_key = Ed25519PrivateKey.generate()
    private_raw = private_key.private_bytes_raw()
    public_raw = private_key.public_key().public_bytes_raw()
    key_id = key_id_from_public_bytes(public_raw)
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
    return {
        "ok": True,
        "key_id": key_id,
        "public_key": record["public_key"],
        "private_key_file": str(path),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate the one-time DingFeng Ed25519 issuer keypair.")
    parser.add_argument(
        "--private-key-file",
        default=".package-secrets/authorization/issuer_private_key.dpapi.json",
    )
    args = parser.parse_args(argv)
    print(json.dumps(generate_keypair(Path(args.private_key_file)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
