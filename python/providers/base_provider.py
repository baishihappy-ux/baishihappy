from dataclasses import dataclass
from enum import Enum


class ProviderTier(str, Enum):
    STABLE_API = "tier_a_stable_api"
    SEMI_MANAGED = "tier_b_semi_managed"
    UNSTABLE = "tier_c_unstable"


@dataclass
class ProviderResponse:
    ok: bool
    status_code: int = 0
    text: str = ""
    url: str = ""
    error: str = ""
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseProvider:
    alias = "base"
    tier = ProviderTier.UNSTABLE

    def __init__(self, config: dict, network_client=None, enable_network=False):
        self.config = config
        self.network_client = network_client
        self.enable_network = enable_network

    def fetch(self, task, session=None) -> ProviderResponse:
        raise NotImplementedError
