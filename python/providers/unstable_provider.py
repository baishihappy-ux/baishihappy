from python.providers.base_provider import BaseProvider, ProviderResponse, ProviderTier
from python.providers.provider_shim import normalize_exception, normalize_http_response


class UnstableHttpProvider(BaseProvider):
    alias = "unstable_http"
    tier = ProviderTier.UNSTABLE

    def fetch(self, task, session=None) -> ProviderResponse:
        if not task.url:
            return ProviderResponse(ok=False, error="task has no url")
        if not self.enable_network:
            html = f"<html><body data-provider='unstable-dry'><a href='{task.url}'>dry run</a></body></html>"
            return ProviderResponse(ok=True, status_code=200, text=html, url=task.url, metadata={"dry_run": True})
        try:
            response = self.network_client.get(task.url)
        except Exception as exc:
            return normalize_exception(exc, task.url, self.alias)
        return normalize_http_response(response, task.url, self.alias)
