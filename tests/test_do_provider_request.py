import unittest
from urllib.parse import parse_qs, urlparse

from python.providers.do_provider import DoProvider
from python.queue.tasks import Task, TaskStage


class FakeHttpClient:
    def __init__(self):
        self.calls = []

    def get(self, url, headers=None):
        self.calls.append((url, dict(headers or {})))
        return type("Response", (), {"status_code": 200, "text": "ok", "url": url, "headers": {}})()


class DoProviderRequestTests(unittest.TestCase):
    def config(self):
        return {
            "provider": {
                "primary_provider": {
                    "token": "test-token",
                    "params": {"super": True, "device": "desktop", "output": "raw"},
                }
            }
        }

    def test_same_session_and_referer_are_forwarded_per_request(self):
        client = FakeHttpClient()
        provider = DoProvider(self.config(), network_client=client, enable_network=True)
        task = Task(
            phone="",
            stage=TaskStage.PARENT,
            target_source="T",
            url="https://target.invalid/detail?id=1",
            session_id=123456,
            referer="https://target.invalid/search",
        )

        response = provider.fetch(task)

        self.assertTrue(response.ok)
        self.assertEqual(1, len(client.calls))
        url, headers = client.calls[0]
        query = parse_qs(urlparse(url).query)
        self.assertEqual(["123456"], query["sessionId"])
        self.assertEqual(["True"], query["extraHeaders"])
        self.assertEqual(["test-token"], query["token"])
        self.assertEqual("https://target.invalid/search", headers["sd-Referer"])

    def test_global_headers_are_not_mutated_by_local_referer(self):
        client = FakeHttpClient()
        provider = DoProvider(self.config(), network_client=client, enable_network=True)
        first = Task(phone="", url="https://target.invalid/a", session_id=1, referer="https://target.invalid/one")
        second = Task(phone="", url="https://target.invalid/b", session_id=2, referer="https://target.invalid/two")

        provider.fetch(first)
        provider.fetch(second)

        self.assertEqual("https://target.invalid/one", client.calls[0][1]["sd-Referer"])
        self.assertEqual("https://target.invalid/two", client.calls[1][1]["sd-Referer"])
        self.assertNotIn("sd-Referer", provider.config.get("provider", {}).get("headers", {}))

    def test_dry_run_keeps_request_contract_without_network(self):
        provider = DoProvider(self.config(), enable_network=False)
        task = Task(phone="", url="https://target.invalid/search", session_id=9, referer="https://target.invalid/")

        response = provider.fetch(task)

        query = parse_qs(urlparse(response.metadata["provider_url"]).query)
        self.assertEqual(["9"], query["sessionId"])
        self.assertEqual({"sd-Referer": "https://target.invalid/"}, response.metadata["request_headers"])


if __name__ == "__main__":
    unittest.main()
