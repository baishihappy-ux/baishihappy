from dataclasses import dataclass

from python.parser.encoded_sources import encoded_source_config


@dataclass
class SourceProfile:
    alias: str
    config_key: str
    default_base: str

    def from_config(self, config: dict) -> dict:
        source_cfg = dict(config.get("sources", {}).get(self.config_key, {}) or {})
        if source_cfg.get("encoded_key"):
            restored = encoded_source_config(source_cfg.get("encoded_key"))
            restored.update({key: value for key, value in source_cfg.items() if value not in ("", None) and value != []})
            return restored
        return source_cfg


PROFILES = {
    "T": SourceProfile("T", "source_t", ""),
    "F": SourceProfile("F", "source_f", ""),
    "P": SourceProfile("P", "source_p", ""),
}


def build_entry_url(config: dict, source: str, phone: str) -> str:
    profile = PROFILES[source]
    source_cfg = profile.from_config(config)
    template = source_cfg.get("input_url_template") or "{phone_digits}"
    return template.format(phone_digits=phone, record_id=phone)


