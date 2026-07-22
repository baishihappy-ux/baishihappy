import unittest
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DevelopmentLauncherTests(unittest.TestCase):
    def read_launcher(self, name):
        return (ROOT / name).read_text(encoding="utf-8")

    def test_authorizer_launcher_executes_current_source(self):
        source = self.read_launcher("启动开发者授权程序.cmd")
        self.assertIn(r"%~dp0tools\developer_authorizer.py", source)
        self.assertIn("python -B", source)
        self.assertNotIn("app.asar", source)
        self.assertNotIn("DeveloperAuthorizer.exe", source)

    def test_client_launcher_executes_current_ui_and_engine_sources(self):
        source = self.read_launcher("启动当前源码客户端.cmd")
        self.assertIn(r"%~dp0electron\main.js", source)
        self.assertIn(r"%~dp0python\main.py", source)
        self.assertIn(r".tmp_dev_electron\node_modules\.bin\electron.cmd", source)
        self.assertIn(r"default_app.asar", source)
        self.assertIn('if exist "%DEV_ELECTRON_RESOURCES%\\app.asar"', source)
        self.assertIn(r'"%~dp0electron\main.js"', source)
        self.assertIn(r"DINGFENG_RUNTIME_ROOT=%~dp0.tmp_dev_client\runtime", source)
        for forbidden in ["dingfeng_engine.exe", "客户包_", "示例kehubao"]:
            self.assertNotIn(forbidden, source)

    def test_client_launcher_does_not_use_contaminated_project_electron(self):
        source = self.read_launcher("启动当前源码客户端.cmd")
        self.assertNotIn(r'%~dp0electron\node_modules\.bin\electron.cmd', source)
        self.assertIn("contaminated by a packaged app.asar", source)

    def test_development_main_process_uses_source_engine(self):
        source = (ROOT / "electron" / "main.js").read_text(encoding="utf-8")
        self.assertIn("if (app.isPackaged)", source)
        self.assertIn("args: [getPythonScript(), ...args]", source)
        self.assertIn("return path.join(APP_ROOT, 'python', 'main.py')", source)

    def test_black_gold_client_is_the_only_renderer_entry(self):
        main = (ROOT / "electron" / "main.js").read_text(encoding="utf-8")
        page = (ROOT / "electron" / "renderer" / "index.html").read_text(encoding="utf-8")
        self.assertIn("mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'))", main)
        self.assertIn('<script src="./renderer.js"></script>', page)
        self.assertNotIn("app.js", page)
        self.assertFalse((ROOT / "electron/renderer/app.js").exists())
        for relative in [
            "electron/renderer/components",
            "electron/renderer/dashboard",
            "electron/renderer/services",
        ]:
            directory = ROOT / relative
            self.assertFalse(directory.exists() and any(directory.rglob("*.js")), relative)

    def test_black_gold_visual_baseline_is_unchanged(self):
        expected = {
            "electron/main.js": "9f5eb7ea157181d82f60fdc9ba5c881f289cbbb2334a7e2434c0adbee9750b6a",
            "electron/preload.js": "40d7ab0c5006e6a36f1c0c879c41409d70a8c437f0951ae0926f0153f26f1d32",
            "electron/renderer/index.html": "861406f26edf1f5f1eeae869eed9ca702f02b7d991777785d3cbc1a5dd289dcd",
            "electron/renderer/style.css": "d90b258efab6937b1117acc094a55429b6df96cdccb662d372f97d1baf0ecaae",
        }
        for relative, digest in expected.items():
            actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            self.assertEqual(digest, actual, relative)

    def test_black_gold_renderer_keeps_df9_authorization_support(self):
        source = (ROOT / "electron" / "renderer" / "renderer.js").read_text(encoding="utf-8")
        self.assertIn("text.includes('DF9-')", source)


if __name__ == "__main__":
    unittest.main()
