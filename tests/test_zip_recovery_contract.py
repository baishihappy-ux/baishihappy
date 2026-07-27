import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ZipRecoveryContractTests(unittest.TestCase):
    def test_root_restore_launcher_is_the_only_formal_entry(self):
        launcher = ROOT / "恢复生产环境.cmd"
        self.assertTrue(launcher.is_file())
        source = launcher.read_text(encoding="utf-8")
        self.assertIn(r"recovery\restore.ps1", source)
        self.assertIn("-ExecutionPolicy Bypass", source)

    def test_recovery_scripts_do_not_execute_git(self):
        command_name = "g" + "it"
        command_pattern = re.compile(
            rf"(?im)^\s*(?:&\s*)?{command_name}(?:\.exe)?\s+"
        )
        for relative in [
            "recovery/restore.ps1",
            "scripts/scan_public_tree.ps1",
            "scripts/build_production_validation.ps1",
            "scripts/verify_zip_recovery.ps1",
        ]:
            source = (ROOT / relative).read_text(encoding="utf-8-sig")
            self.assertIsNone(command_pattern.search(source), relative)

    def test_maintainer_manifest_generator_is_not_called_by_restore(self):
        restore = (ROOT / "recovery/restore.ps1").read_text(encoding="utf-8-sig")
        self.assertNotIn("update_source_manifest", restore)
        generator = (ROOT / "scripts/update_source_manifest.ps1").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("正式恢复不调用", generator)

    def test_build_asset_is_repository_owned_and_stable(self):
        asset = ROOT / "assets/build/gender/_gender_map.js"
        self.assertEqual(2_046_506, asset.stat().st_size)
        self.assertEqual(
            "20b0122a7be802b95e1c6ccb44854bfb4a55023c672dec0dbae348058a0859dc",
            hashlib.sha256(asset.read_bytes()).hexdigest(),
        )

    def test_dependency_manifests_cover_runtime_and_build_imports(self):
        runtime = (ROOT / "requirements-runtime.txt").read_text(encoding="utf-8")
        build = (ROOT / "requirements-build.txt").read_text(encoding="utf-8")
        self.assertIn("beautifulsoup4==4.14.3", runtime)
        self.assertIn("cryptography==49.0.0", runtime)
        self.assertIn("pyinstaller==6.21.0", build)

    def test_toolchain_versions_and_hashes_are_pinned(self):
        lock = json.loads(
            (ROOT / "recovery/toolchain.lock.json").read_text(encoding="utf-8")
        )
        self.assertEqual("windows-x64", lock["platform"])
        self.assertEqual("recovery-toolchain-v2", lock["bundle"]["tag"])
        self.assertRegex(lock["bundle"]["sha256"], r"^[0-9a-f]{64}$")
        for tool in ["python", "node", "gitleaks", "electron"]:
            self.assertRegex(lock[tool]["sha256"], r"^[0-9a-f]{64}$")
            self.assertNotIn("latest", lock[tool]["url"].lower())

    def test_active_recovery_docs_do_not_offer_vcs_restore(self):
        forbidden = ["g" + "it clone", "g" + "it pull"]
        for relative in [
            "README.md",
            "docs/唯一恢复方式.md",
            "docs/RESTORE_AND_PACKAGING.md",
        ]:
            text = (ROOT / relative).read_text(encoding="utf-8-sig").lower()
            for phrase in forbidden:
                self.assertNotIn(phrase, text, relative)


if __name__ == "__main__":
    unittest.main()
