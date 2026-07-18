import argparse
import getpass
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.hazmat.primitives import serialization

from python.auth.license_issuer import load_issuer_private_key


def export_recovery(private_key, passphrase: bytes, output: Path):
    if len(passphrase) < 16:
        raise ValueError("Recovery passphrase must contain at least 16 characters.")
    path = output.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(passphrase),
    )
    with path.open("xb") as handle:
        handle.write(pem)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export an encrypted offline recovery copy of the issuer private key.")
    parser.add_argument("--output", default=".package-secrets/authorization/issuer_private_key.recovery.pem")
    args = parser.parse_args(argv)
    passphrase = getpass.getpass("Recovery passphrase: ").encode("utf-8")
    confirmation = getpass.getpass("Confirm recovery passphrase: ").encode("utf-8")
    if passphrase != confirmation:
        raise SystemExit("Recovery passphrases do not match.")
    private_key, key_id = load_issuer_private_key()
    try:
        output = export_recovery(private_key, passphrase, Path(args.output))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps({"ok": True, "key_id": key_id, "recovery_file": str(output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
