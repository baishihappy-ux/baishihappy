import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DevelopmentLauncherTests(unittest.TestCase):
    def read_launcher(self, name):
        return (ROOT / name).read_text(encoding="utf-8")

    def test_authorizer_launcher_executes_current_source(self):
        source = self.read_launcher("启动开发者授权程序.cmd")
        self.assertIn(r"%~dp0tools\developer_authorizer.py", source)
        self.assertIn(r".recovery\venv\Scripts\python.exe", source)
        self.assertIn('"%PYTHON_EXE%" -B', source)
        self.assertNotIn("app.asar", source)
        self.assertNotIn("DeveloperAuthorizer.exe", source)

    def test_client_launcher_executes_current_ui_and_engine_sources(self):
        source = self.read_launcher("启动当前源码客户端.cmd")
        self.assertIn(r"%~dp0electron\main.js", source)
        self.assertIn(r"%~dp0python\main.py", source)
        self.assertIn(r"electron\node_modules\.bin\electron.cmd", source)
        self.assertIn(r"default_app.asar", source)
        self.assertIn('if exist "%DEV_ELECTRON_RESOURCES%\\app.asar"', source)
        self.assertIn(r'"%~dp0electron\main.js"', source)
        self.assertIn(
            r"DINGFENG_RUNTIME_ROOT=%~dp0.recovery\development-runtime", source
        )
        self.assertIn(
            r"PYTHON_EXECUTABLE=%~dp0.recovery\venv\Scripts\python.exe", source
        )
        for forbidden in ["dingfeng_engine.exe", "客户包", "示例kehubao"]:
            self.assertNotIn(forbidden, source)

    def test_client_launcher_rejects_contaminated_restored_electron(self):
        source = self.read_launcher("启动当前源码客户端.cmd")
        self.assertIn(r"%~dp0electron\node_modules\.bin\electron.cmd", source)
        self.assertIn("contaminated by a packaged app.asar", source)

    def test_development_main_process_uses_source_engine(self):
        source = (ROOT / "electron" / "main.js").read_text(encoding="utf-8")
        self.assertIn("if (app.isPackaged)", source)
        self.assertIn("args: [getPythonScript(), ...args]", source)
        self.assertIn("return path.join(APP_ROOT, 'python', 'main.py')", source)

    def test_black_gold_client_is_the_only_renderer_entry(self):
        main = (ROOT / "electron" / "main.js").read_text(encoding="utf-8")
        page = (ROOT / "electron" / "renderer" / "index.html").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'))",
            main,
        )
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
            "electron/main.js": "69ef54d8f55855ea5fa3828988d6c69b8a25675053d1f68a1f6c0fd2f8b70f08",
            "electron/preload.js": "b40de97c629400fc0210e27dfdd615ef72797612721b9a3d28b3649488a6cc8e",
            "electron/renderer/index.html": "9e622c4e9ac81ad500e136cb1f8ca1596a3682083a7e2353a8e415095e6c927e",
            "electron/renderer/style.css": "4e9035ba6bd45d4b240655f5b2c0b5b9329f924f46e7e81c15483466bb60b25a",
        }
        for relative, digest in expected.items():
            normalized = (ROOT / relative).read_text(encoding="utf-8")
            actual = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            self.assertEqual(digest, actual, relative)

    def test_black_gold_renderer_keeps_df9_authorization_support(self):
        source = (ROOT / "electron" / "renderer" / "renderer.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("text.includes('DF9-')", source)


if __name__ == "__main__":
    unittest.main()
