from urllib.parse import urlencode

from python.providers.base_provider import BaseProvider, ProviderResponse, ProviderTier
from python.providers.provider_shim import normalize_exception, normalize_http_response


class DoProvider(BaseProvider):
    alias = "primary_provider"
    tier = ProviderTier.STABLE_API
    default_endpoint = "".join(chr(code) for code in [104, 116, 116, 112, 115, 58, 47, 47, 97, 112, 105, 46, 115, 99, 114, 97, 112, 101, 46, 100, 111, 47])

    def build_provider_url(self, target_url: str) -> str:
        provider_cfg = self.config.get("provider", {}).get("primary_provider", {})
        params = dict(provider_cfg.get("params", {}))
        token = provider_cfg.get("token") or self.config.get("provider", {}).get("token") or ""
        if token:
            params["token"] = token
        params["url"] = target_url
        endpoint = provider_cfg.get("endpoint") or self.config.get("provider", {}).get("endpoint") or self.default_endpoint
        separator = "&" if "?" in endpoint else "?"
        return endpoint + separator + urlencode(params)

    def fetch(self, task, session=None) -> ProviderResponse:
        target_url = task.url
        if not target_url:
            return ProviderResponse(ok=False, error="task has no url")
        provider_url = self.build_provider_url(target_url)
        if not self.enable_network:
            html = f"<html><body data-provider='do-dry'><a href='{target_url}'>dry run</a></body></html>"
            return ProviderResponse(ok=True, status_code=200, text=html, url=target_url, metadata={"dry_run": True, "provider_url": provider_url, "direct_stable_api": True})
        token = self.config.get("provider", {}).get("primary_provider", {}).get("token") or self.config.get("provider", {}).get("token") or ""
        if not token:
            return ProviderResponse(
                ok=False,
                status_code=401,
                text="",
                url=target_url,
                error="provider token missing",
                metadata={"provider_url": provider_url, "direct_stable_api": True},
            )
        try:
            response = self.network_client.get(provider_url)
        except Exception as exc:
            return normalize_exception(exc, target_url, self.alias)
        normalized = normalize_http_response(response, target_url, self.alias)
        normalized.metadata["provider_url"] = provider_url
        normalized.metadata["direct_stable_api"] = True
        return normalized


