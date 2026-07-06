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

    def get(self, url: str):
        if requests is None:
            raise RuntimeError("requests is required for live network mode")
        return requests.get(url, timeout=self.timeout, headers=self.headers, proxies=self.proxies, verify=self.verify)


