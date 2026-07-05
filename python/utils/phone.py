import re


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits if len(digits) == 10 else ""


def unique_phones(lines):
    seen = set()
    for line in lines:
        phone = normalize_phone(line)
        if phone and phone not in seen:
            seen.add(phone)
            yield phone
