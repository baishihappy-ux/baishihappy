try:
    import requests
except Exception:  # pragma: no cover
    requests = None


class HttpClient:
    def __init__(self, provider_config: dict):
        self.timeout = provider_config.get("timeout_seconds", 90)
        self.headers = provider_config.get("headers", {})
        network = provider_config.get("network", {})
        proxy = network.get("proxy") or ""
        self.proxies = {"http": proxy, "https": proxy} if proxy else None
        self.verify = bool(network.get("verify_ssl", True))

    def get(self, url: str, headers=None):
        if requests is None:
            raise RuntimeError("requests is required for live network mode")
        request_headers = dict(self.headers or {})
        request_headers.update(dict(headers or {}))
        return requests.get(url, timeout=self.timeout, headers=request_headers, proxies=self.proxies, verify=self.verify)
