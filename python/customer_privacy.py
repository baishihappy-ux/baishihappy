import re


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", str(value or ""))


def mask_phone(value: str) -> str:
    digits = digits_only(value)
    if not digits:
        return "***"
    return f"***{digits[-4:]}"


def allow_plain_record_logging(config: dict) -> bool:
    runtime = config.get("runtime", {}) if isinstance(config, dict) else {}
    return bool(runtime.get("plain_record_logging") or runtime.get("diagnostic_mode"))


def privacy_record_id(value: str, config: dict = None) -> str:
    if config and allow_plain_record_logging(config):
        return digits_only(value) or str(value or "")
    return mask_phone(value)


def redact_text(value: str, config: dict = None) -> str:
    if config and allow_plain_record_logging(config):
        return str(value or "")
    return re.sub(r"(?:\+?1[\s.-]?)?\(?([2-9]\d{2})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})", lambda m: f"***{m.group(3)}", str(value or ""))


