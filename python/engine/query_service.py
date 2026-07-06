import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from python.engine.config import load_config
from python.parser.source_profiles import build_entry_url
from python.providers.provider_manager import ProviderManager
from python.queue.tasks import Task, TaskStage


def query_once(root: Path, phone=None, url=None, target="T", provider=None, enable_network=False):
    config = load_config(root)
    target_url = url or build_entry_url(config, target, phone or "")
    task = Task(phone=phone or "", stage=TaskStage.RESULTPHONE, target_source=target, url=target_url)
    response = ProviderManager(config, enable_network=enable_network).get(provider).fetch(task)
    return {"ok": response.ok, "status_code": response.status_code, "url": response.url, "text_chars": len(response.text), "error": response.error}


def serve(root: Path, host="127.0.0.1", port=8765, provider=None, enable_network=False):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/ready":
                self.respond({"ok": True})
                return
            if parsed.path == "/query":
                qs = parse_qs(parsed.query)
                payload = query_once(root, phone=(qs.get("phone") or [""])[0], url=(qs.get("url") or [None])[0], provider=provider, enable_network=enable_network)
                self.respond(payload)
                return
            self.respond({"ok": False, "error": "not found"}, 404)

        def respond(self, payload, status=200):
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    HTTPServer((host, int(port)), Handler).serve_forever()


