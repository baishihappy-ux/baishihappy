import json

from python.challenge.detector import detect_challenge
from python.providers.base_provider import ProviderResponse


def normalize_http_response(raw_response, target_url: str = "", provider_alias: str = "") -> ProviderResponse:
    status_code = int(getattr(raw_response, "status_code", 0) or 0)
    text = getattr(raw_response, "text", "") or ""
    headers = dict(getattr(raw_response, "headers", {}) or {})
    content_type = headers.get("content-type") or headers.get("Content-Type") or ""
    metadata = {
        "provider": provider_alias,
        "content_type": content_type,
        "headers": _safe_headers(headers),
    }
    text, metadata = _unwrap_provider_payload(text, metadata)
    finding = detect_challenge(status_code, text, headers)
    ok = 200 <= status_code < 300 and not finding.blocked
    error = "" if ok else finding.reason or f"HTTPError status={status_code}"
    if finding.blocked:
        metadata["challenge"] = {"kind": finding.kind, "reason": finding.reason}
    return ProviderResponse(
        ok=ok,
        status_code=status_code,
        text=text,
        url=target_url or getattr(raw_response, "url", ""),
        error=error,
        metadata=metadata,
    )


def normalize_exception(exc: Exception, target_url: str = "", provider_alias: str = "") -> ProviderResponse:
    name = exc.__class__.__name__
    message = str(exc) or name
    status_code = 0
    if "timeout" in message.lower() or "timeout" in name.lower():
        message = "timeout"
    return ProviderResponse(
        ok=False,
        status_code=status_code,
        text="",
        url=target_url,
        error=message,
        metadata={"provider": provider_alias, "exception": name},
    )


def _unwrap_provider_payload(text: str, metadata: dict):
    stripped = (text or "").strip()
    if not stripped or stripped[0] not in "[{":
        return text, metadata
    try:
        payload = json.loads(stripped)
    except Exception:
        return text, metadata
    if not isinstance(payload, dict):
        return text, metadata
    for key in ["body", "html", "content", "response", "result"]:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            metadata["wrapped_json_key"] = key
            return value, metadata
    if "error" in payload:
        metadata["provider_error"] = str(payload.get("error"))
    return text, metadata


def _safe_headers(headers: dict):
    safe = {}
    for key, value in (headers or {}).items():
        lower = str(key).lower()
        if lower in {"authorization", "proxy-authorization", "cookie", "set-cookie"}:
            safe[key] = "***"
        else:
            safe[key] = value
    return safe


