from python.providers.base_provider import BaseProvider, ProviderResponse, ProviderTier
from python.queue.tasks import TaskStage


class LocalFixtureProvider(BaseProvider):
    alias = "local_fixture"
    tier = ProviderTier.SEMI_MANAGED

    def fetch(self, task, session=None) -> ProviderResponse:
        url = task.url or ""
        if task.stage == TaskStage.ENTRY:
            text = "<html><body><main>Local entry fixture</main></body></html>"
        elif task.stage == TaskStage.RESULTPHONE:
            text = f"<html><body><a href='/find/person/parent-{task.phone}'>fixture parent</a></body></html>"
        else:
            associates = ""
            if task.stage == TaskStage.PARENT:
                associates = "".join(
                    f"<a data-link-to-more='associate' href='/find/person/associate-{suffix}-{task.phone}'>associate {suffix}</a>"
                    for suffix in "abc"
                )
            text = (
                "<html><head><title>Local Fixture Person Age 40 in Seattle, WA</title></head><body>"
                f"<h1 id='details-header'>Local Fixture Person</h1>"
                f"<a href='/find/phone/{task.phone}'>{task.phone}</a>"
                f"{associates}</body></html>"
            )
        return ProviderResponse(
            ok=True,
            status_code=200,
            text=text,
            url=url,
            metadata={"fixture": True, "stage": task.stage.value},
        )
