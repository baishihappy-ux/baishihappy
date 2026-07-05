from python.parser.source_profiles import PROFILES, build_entry_url


SOURCE_ALIASES = {
    "T": "source_t",
    "F": "source_f",
    "P": "source_p",
}


def get_source_rule(config: dict, source: str) -> dict:
    source = (source or "T").upper()
    profile = PROFILES.get(source)
    if not profile:
        raise KeyError(f"unknown target source: {source}")
    rule = dict(profile.from_config(config))
    rule["source"] = source
    rule["config_key"] = SOURCE_ALIASES[source]
    rule["detail_url_base"] = rule.get("detail_url_base") or profile.default_base
    return rule


def build_phone_search_url(config: dict, source: str, phone: str) -> str:
    return build_entry_url(config, (source or "T").upper(), phone)
