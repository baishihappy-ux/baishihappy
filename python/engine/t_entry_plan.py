import math
import random
import threading
from dataclasses import dataclass

from python.parser.source_profiles import PROFILES


LEGACY_REMOVAL_WEIGHT_PCT = 5.0
MAX_REMOVAL_WEIGHT_PCT = 60.0


def _s(values):
    return "".join(chr(value) for value in values)


_TARGET_CAMEL = _s([84, 114, 117, 101, 80, 101, 111, 112, 108, 101, 83, 101, 97, 114, 99, 104])
_TARGET_SLUG = _s([116, 114, 117, 101, 112, 101, 111, 112, 108, 101, 115, 101, 97, 114, 99, 104])
_TARGET_DASHED = _s([116, 114, 117, 101, 45, 112, 101, 111, 112, 108, 101, 45, 115, 101, 97, 114, 99, 104])
_TARGET_TITLE_DASHED = _s([84, 114, 117, 101, 80, 101, 111, 112, 108, 101, 45, 83, 101, 97, 114, 99, 104])


@dataclass(frozen=True)
class EntryReferer:
    key: str
    url: str
    weight: float
    entry_kind: str = "home"


@dataclass(frozen=True)
class TEntryPlan:
    sequence_no: int
    entry_url: str
    referer: str
    referer_key: str
    entry_kind: str
    nominal_weight: float
    conditional_probability: float


def _configured_removal_weight(config: dict) -> float:
    processing = config.get("processing", {}) or {}
    raw = processing.get("smart_session_t_entry_removal_weight_pct", LEGACY_REMOVAL_WEIGHT_PCT)
    if isinstance(raw, bool):
        raise ValueError("smart_session_t_entry_removal_weight_pct must be numeric, not boolean")
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("smart_session_t_entry_removal_weight_pct must be numeric") from exc
    if not math.isfinite(value) or value < 0 or value > MAX_REMOVAL_WEIGHT_PCT:
        raise ValueError(
            f"smart_session_t_entry_removal_weight_pct must be between 0 and {MAX_REMOVAL_WEIGHT_PCT:g}"
        )
    return value


def build_t_entry_referers(config: dict) -> tuple[EntryReferer, ...]:
    removal_weight = _configured_removal_weight(config)
    major_search_weight = MAX_REMOVAL_WEIGHT_PCT - removal_weight
    target_domain = f"{_TARGET_SLUG}.com"
    specs = [
        ("major_search", f"https://www.google.com/search?q={_TARGET_CAMEL}&sourceid=chrome&ie=UTF-8", major_search_weight, "home"),
        ("social", f"https://www.facebook.com/{_TARGET_SLUG}/", 10.0, "home"),
        ("other_01", f"https://www.whois.com/whois/{target_domain}", 2.5, "home"),
        ("other_02", f"https://blog.incogni.com/{_TARGET_DASHED}-removal/", 2.5, "home"),
        ("other_03", f"https://apify.com/scrapyspider/{_TARGET_SLUG}-contact-finder", 2.5, "home"),
        ("other_04", f"https://www.semrush.com/website/{target_domain}/competitors/", 2.5, "home"),
        ("other_05", f"https://www.quora.com/Is-{_TARGET_CAMEL}-legit-What-are-your-reviews-of-{_TARGET_TITLE_DASHED}", 2.5, "home"),
        ("other_06", f"https://{_TARGET_DASHED}-free-reverse-phone-lookup.soft112.com/download.html", 2.5, "home"),
        ("removal_01", f"https://duckduckgo.com/duckduckgo-help-pages/{_TARGET_SLUG}-removal", removal_weight / 2.0, "removal"),
        ("other_07", f"https://freepeoplesearchtool.com/{_TARGET_SLUG}#gsc.tab=0", 2.5, "home"),
        ("other_08", f"https://www.wxii12.com/article/experts-warn-how-to-protect-your-identity-on-{_TARGET_SLUG}com/9663089", 2.5, "home"),
        ("removal_02", f"https://onerep.com/blog/{_TARGET_SLUG}-opt-out", removal_weight / 2.0, "removal"),
        ("other_09", "https://www.lifewire.com/find-anyone-online-3482687", 2.5, "home"),
        ("other_10", "https://www.lifewire.com/remove-personal-information-from-internet-3482691", 2.5, "home"),
        ("other_11", "https://www.tomsguide.com/computing/online-security/is-your-personal-information-public-the-simple-step-to-securing-your-privacy-online", 2.5, "home"),
    ]
    home_url = PROFILES["T"].from_config(config).get("entry_home_url") or ""
    specs.append(("other_12", home_url, 2.5, "home"))
    referers = tuple(EntryReferer(*spec) for spec in specs)
    _validate_referers(referers)
    return referers


def _validate_referers(referers: tuple[EntryReferer, ...]):
    if len(referers) != 16:
        raise ValueError("T entry referer pool must contain exactly 16 sources")
    keys = [item.key for item in referers]
    urls = [item.url for item in referers]
    if len(set(keys)) != len(keys) or len(set(urls)) != len(urls):
        raise ValueError("T entry referer keys and URLs must be unique")
    if any(not item.key or not item.url for item in referers):
        raise ValueError("T entry referer key and URL cannot be empty")
    if any(not math.isfinite(item.weight) or item.weight < 0 for item in referers):
        raise ValueError("T entry referer weights must be finite and non-negative")
    if sum(item.weight for item in referers) <= 0:
        raise ValueError("T entry referer pool must have positive total weight")


class TEntryPlanner:
    """Process-local, thread-safe implementation of the T1 entry selection rule."""

    def __init__(self, config: dict, rng=None):
        source_cfg = PROFILES["T"].from_config(config)
        self.home_url = source_cfg.get("entry_home_url") or ""
        self.removal_url = source_cfg.get("entry_removal_url") or ""
        if not self.home_url or not self.removal_url:
            raise ValueError("T entry home and removal URLs are required")
        if self.home_url == self.removal_url:
            raise ValueError("T entry home and removal URLs must be different")
        self.removal_weight_pct = _configured_removal_weight(config)
        self.referers = build_t_entry_referers(config)
        self.rng = rng or random.Random()
        self.lock = threading.RLock()
        self.last_referer_key = ""
        self.sequence_no = 0
        self.kind_counts = {"home": 0, "removal": 0}
        self.referer_counts = {item.key: 0 for item in self.referers}

    def choose(self) -> TEntryPlan:
        with self.lock:
            candidates = [
                item for item in self.referers
                if item.key != self.last_referer_key and item.weight > 0
            ]
            if not candidates:
                candidates = [item for item in self.referers if item.weight > 0]
            weights = [item.weight for item in candidates]
            selected = self.rng.choices(candidates, weights=weights, k=1)[0]
            total = sum(weights)
            self.last_referer_key = selected.key
            self.sequence_no += 1
            self.kind_counts[selected.entry_kind] += 1
            self.referer_counts[selected.key] += 1
            return TEntryPlan(
                sequence_no=self.sequence_no,
                entry_url=self.removal_url if selected.entry_kind == "removal" else self.home_url,
                referer=selected.url,
                referer_key=selected.key,
                entry_kind=selected.entry_kind,
                nominal_weight=selected.weight,
                conditional_probability=selected.weight / total,
            )

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "ready": True,
                "source_count": len(self.referers),
                "nominal_removal_weight_pct": self.removal_weight_pct,
                "expected_long_run_removal_pct": self._stationary_removal_probability() * 100.0,
                "avoid_immediate_repeat": True,
                "selection_count": self.sequence_no,
                "last_referer_key": self.last_referer_key,
                "entry_kind_counts": dict(self.kind_counts),
                "referer_counts": dict(self.referer_counts),
            }

    def _stationary_removal_probability(self) -> float:
        total = sum(item.weight for item in self.referers)
        values = [(item, item.weight / total) for item in self.referers if item.weight > 0]
        denominator = sum(weight * (1.0 - weight) for _item, weight in values)
        if denominator <= 0:
            return 0.0
        return sum(
            weight * (1.0 - weight)
            for item, weight in values
            if item.entry_kind == "removal"
        ) / denominator
