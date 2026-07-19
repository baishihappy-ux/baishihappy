import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from python.auth import license as license_runtime
from python.auth.license_codec import LICENSE_PREFIX, PUBLIC_KEYS, b64decode, b64encode, canonical, decode_authorization_code, key_id_from_public_bytes
from python.auth.license_issuer import generate_with_private_key
from python.auth.license_public_keys import ACTIVE_KEY_ID, PUBLIC_KEYS as PRODUCTION_PUBLIC_KEYS
from python.engine.cli import build_parser


MACHINE = "A" * 32
TOKEN = "synthetic-provider-token-for-tests"


class LicenseEd25519Tests(unittest.TestCase):
    def setUp(self):
        self.private_key = Ed25519PrivateKey.generate()
        public_raw = self.private_key.public_key().public_bytes_raw()
        self.key_id = key_id_from_public_bytes(public_raw)
        self.public_keys = {self.key_id: b64encode(public_raw)}

    def issue(self, **overrides):
        values = {
            "machine_code": MACHINE,
            "valid_days": 30,
            "max_concurrency": 32,
            "do_token": TOKEN,
            "issued_at": int(time.time()),
        }
        values.update(overrides)
        return generate_with_private_key(private_key=self.private_key, key_id=self.key_id, **values)

    def test_valid_code_contains_only_signed_v2_payload(self):
        code = self.issue()
        self.assertTrue(code.startswith("DF9-"))
        payload = decode_authorization_code(code, self.public_keys)
        self.assertEqual(MACHINE, payload["machine_code"])
        self.assertEqual(32, payload["max_concurrency"])
        self.assertEqual(TOKEN, payload["do_token"])
        self.assertEqual(self.key_id, payload["key_id"])

    def test_active_customer_public_key_fingerprint_is_consistent(self):
        self.assertIn(ACTIVE_KEY_ID, PRODUCTION_PUBLIC_KEYS)
        self.assertEqual(ACTIVE_KEY_ID, key_id_from_public_bytes(b64decode(PRODUCTION_PUBLIC_KEYS[ACTIVE_KEY_ID])))

    def test_tampered_payload_is_rejected(self):
        code = self.issue()
        envelope = json.loads(b64decode(code[len(LICENSE_PREFIX):]).decode("utf-8"))
        payload = json.loads(b64decode(envelope["p"]).decode("utf-8"))
        payload["max_concurrency"] = 999
        envelope["p"] = b64encode(canonical(payload))
        tampered = LICENSE_PREFIX + b64encode(canonical(envelope))
        with self.assertRaisesRegex(ValueError, "signature verification failed"):
            decode_authorization_code(tampered, self.public_keys)

    def test_wrong_public_key_and_old_df8_code_are_rejected(self):
        other_public = Ed25519PrivateKey.generate().public_key().public_bytes_raw()
        with self.assertRaises(ValueError):
            decode_authorization_code(self.issue(), {self.key_id: b64encode(other_public)})
        with self.assertRaisesRegex(ValueError, "DF9-"):
            decode_authorization_code("DF8-old-code", self.public_keys)

    def test_activation_saves_raw_code_and_public_status_never_exposes_token(self):
        with tempfile.TemporaryDirectory() as raw, patch.dict(PUBLIC_KEYS, self.public_keys, clear=True), patch(
            "python.auth.license.machine_code", return_value=MACHINE
        ):
            runtime = Path(raw)
            code = self.issue()
            activated = license_runtime.activate(runtime, {}, code)
            self.assertTrue(activated["valid"])
            self.assertNotIn("payload", activated)
            self.assertNotIn("do_token", json.dumps(activated))
            self.assertEqual(code, (runtime / "license.dat").read_text(encoding="utf-8").strip())

            config = {"provider": {"primary_provider": {}}, "runtime": {}}
            applied = license_runtime.apply_license_to_config(runtime, config)
            self.assertEqual(TOKEN, applied["provider"]["token"])
            self.assertEqual(32, applied["runtime"]["authorized_concurrency"])

    def test_opaque_json_expired_and_wrong_machine_licenses_are_invalid(self):
        with tempfile.TemporaryDirectory() as raw, patch.dict(PUBLIC_KEYS, self.public_keys, clear=True), patch(
            "python.auth.license.machine_code", return_value=MACHINE
        ):
            runtime = Path(raw)
            path = runtime / "license.dat"
            path.write_text("not-json-and-not-a-code", encoding="utf-8")
            self.assertFalse(license_runtime.status(runtime, {})["valid"])
            path.write_text('{"machine_code":"' + MACHINE + '"}', encoding="utf-8")
            self.assertFalse(license_runtime.status(runtime, {})["valid"])

            expired = self.issue(valid_days=1, issued_at=int(time.time()) - 2 * 86400)
            self.assertFalse(license_runtime.activate(runtime, {}, expired)["valid"])
            wrong_machine = self.issue(machine_code="B" * 32)
            self.assertFalse(license_runtime.activate(runtime, {}, wrong_machine)["valid"])

    def test_customer_cli_cannot_generate_authorization_codes(self):
        self.assertNotIn("generate-license", build_parser()._subparsers._group_actions[0].choices)

    def test_authorizer_customer_field_copy_remains_unchanged(self):
        source = (Path(__file__).parents[1] / "tools" / "developer_authorizer.py").read_text(encoding="utf-8")
        for label in ["Machine Code", "Valid Days", "Max Windows", "Provider Token"]:
            self.assertIn(f'"{label}"', source)

if __name__ == "__main__":
    unittest.main()
