from python.providers.base_provider import BaseProvider, ProviderResponse, ProviderTier


class LocalFixtureProvider(BaseProvider):
    alias = "local_fixture"
    tier = ProviderTier.SEMI_MANAGED

    def fetch(self, task, session=None) -> ProviderResponse:
        return ProviderResponse(
            ok=True,
            status_code=200,
            text=f"<html><body><a href='/find/person/{task.phone}'>fixture</a></body></html>",
            url=task.url or "",
            metadata={"fixture": True},
        )
