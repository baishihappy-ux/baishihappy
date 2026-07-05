from dataclasses import dataclass
import re


@dataclass
class ChallengeFinding:
    blocked: bool
    kind: str = ""
    reason: str = ""


STATUS_CHALLENGES = {
    401: ("auth", "HTTPError status=401"),
    403: ("forbidden", "HTTPError status=403"),
    407: ("proxy_auth", "HTTPError status=407"),
    408: ("timeout", "HTTPError status=408"),
    429: ("rate_limited", "HTTPError status=429"),
    502: ("bad_gateway", "HTTPError status=502"),
    503: ("unavailable", "HTTPError status=503"),
    504: ("timeout", "HTTPError status=504"),
}

BODY_PATTERNS = [
    ("captcha", r"\b(captcha|hcaptcha|recaptcha|verify you are human)\b"),
    ("cloudflare", r"\b(cloudflare|cf-chl|checking your browser|just a moment)\b"),
    ("access_denied", r"\b(access denied|request blocked|forbidden|not authorized)\b"),
    ("rate_limited", r"\b(too many requests|rate limit|temporarily blocked)\b"),
    ("do_error", r"\b(\.do|do provider|provider).{0,80}\b(error|timeout|failed)\b"),
]


def detect_challenge(status_code: int = 0, text: str = "", headers: dict = None) -> ChallengeFinding:
    status_code = int(status_code or 0)
    if status_code in STATUS_CHALLENGES:
        kind, reason = STATUS_CHALLENGES[status_code]
        return ChallengeFinding(True, kind, reason)
    if status_code == 0:
        return ChallengeFinding(True, "network", "network error")
    body = (text or "")[:20000]
    for kind, pattern in BODY_PATTERNS:
        if re.search(pattern, body, re.I):
            return ChallengeFinding(True, kind, f"challenge detected: {kind}")
    return ChallengeFinding(False)
