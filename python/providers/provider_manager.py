import threading

from python.network.http_client import HttpClient
from python.providers.base_provider import ProviderTier
from python.providers.local_provider import LocalFixtureProvider
from python.providers.do_provider import DoProvider
from python.providers.semi_managed_provider import CloudBypassProvider, ScrapFlyProvider, ZenRowsProvider
from python.providers.unstable_provider import UnstableHttpProvider


class ProviderManager:
    def __init__(self, config: dict, enable_network=False):
        self.config = config
        self.enable_network = enable_network
        self.registry = {
            DoProvider.alias: DoProvider,
            LocalFixtureProvider.alias: LocalFixtureProvider,
            CloudBypassProvider.alias: CloudBypassProvider,
            ZenRowsProvider.alias: ZenRowsProvider,
            ScrapFlyProvider.alias: ScrapFlyProvider,
            UnstableHttpProvider.alias: UnstableHttpProvider,
        }
        self.scores = {name: 1.0 for name in self.registry}
        self.failure_counts = {name: 0 for name in self.registry}
        self.success_counts = {name: 0 for name in self.registry}
        self.active_alias = config.get("provider", {}).get("active") or "primary_provider"
        self.lock = threading.RLock()

    def get(self, alias=None):
        provider_config = self.config.get("provider", {})
        name = alias or self.active_alias
        cls = self.registry.get(name)
        if not cls:
            raise KeyError(f"unknown provider: {name}")
        client = HttpClient(provider_config)
        return cls(self.config, network_client=client, enable_network=self.enable_network)

    def route(self, control_signal=None):
        with self.lock:
            tier = self.tier(self.active_alias)
            if tier == ProviderTier.STABLE_API:
                alias = self.active_alias
                return self.get(alias), alias
            if tier == ProviderTier.SEMI_MANAGED:
                alias = self.active_alias
                return self.get(alias), alias
            if control_signal and control_signal.fallback_required:
                self.active_alias = self._best_fallback()
            else:
                self.active_alias = self._best_provider()
            alias = self.active_alias
            return self.get(alias), alias

    def record_result(self, alias: str, response):
        with self.lock:
            if self.tier(alias) == ProviderTier.STABLE_API:
                if response.ok:
                    self.success_counts[alias] += 1
                else:
                    self.failure_counts[alias] += 1
                return
            if response.ok:
                self.success_counts[alias] += 1
                self.scores[alias] = min(1.0, self.scores[alias] + 0.05)
                return
            self.failure_counts[alias] += 1
            spike = 0.35 if response.status_code in {0, 502, 504} else 0.15
            self.scores[alias] = max(0.01, self.scores[alias] - spike)

    def apply_control_signal(self, control_signal):
        with self.lock:
            if not control_signal:
                return
            if self.tier(self.active_alias) != ProviderTier.UNSTABLE:
                return
            self.scores[self.active_alias] = max(0.01, min(1.0, self.scores[self.active_alias] + control_signal.provider_weight_delta))
            if control_signal.fallback_required:
                self.active_alias = self._best_fallback()

    def tier(self, alias=None):
        name = alias or self.active_alias
        cls = self.registry.get(name)
        if not cls:
            raise KeyError(f"unknown provider: {name}")
        return cls.tier

    def uses_control_brain(self, alias=None):
        return self.tier(alias) == ProviderTier.UNSTABLE

    def uses_session_pool(self, alias=None):
        return self.tier(alias) == ProviderTier.UNSTABLE

    def retry_count(self, alias=None):
        tier = self.tier(alias)
        if tier == ProviderTier.STABLE_API:
            return min(int(self.config.get("provider", {}).get("retry_count", 1)), 1)
        return int(self.config.get("provider", {}).get("retry_count", 1))

    def should_try_fallback(self, alias, response):
        if response.ok:
            return False
        return self.tier(alias) == ProviderTier.SEMI_MANAGED and response.status_code in {0, 429, 502, 503, 504}

    def fallback_alias(self, alias):
        tier = self.tier(alias)
        candidates = {
            name: score
            for name, score in self.scores.items()
            if name != alias and self.tier(name) == tier
        }
        if not candidates:
            return alias
        return max(candidates, key=lambda name: candidates[name])

    def snapshot(self):
        with self.lock:
            total = max(1, self.success_counts.get(self.active_alias, 0) + self.failure_counts.get(self.active_alias, 0))
            health = self.scores.get(self.active_alias, 1.0)
            return {
                "active": self.active_alias,
                "tier": self.tier(self.active_alias).value,
                "uses_control_brain": self.uses_control_brain(self.active_alias),
                "uses_session_pool": self.uses_session_pool(self.active_alias),
                "active_health": health,
                "scores": dict(self.scores),
                "success_counts": dict(self.success_counts),
                "failure_counts": dict(self.failure_counts),
                "failure_rate": self.failure_counts.get(self.active_alias, 0) / total,
            }

    def _best_provider(self):
        return self._best_by_tier(ProviderTier.UNSTABLE)

    def _best_fallback(self):
        candidates = {name: score for name, score in self.scores.items() if name != self.active_alias and self.tier(name) == ProviderTier.UNSTABLE}
        if not candidates:
            return self.active_alias
        return max(candidates, key=lambda name: candidates[name])

    def _best_by_tier(self, tier):
        candidates = {name: score for name, score in self.scores.items() if self.tier(name) == tier}
        if not candidates:
            return self.active_alias
        return max(candidates, key=lambda name: candidates[name])


