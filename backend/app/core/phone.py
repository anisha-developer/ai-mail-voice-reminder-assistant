from __future__ import annotations

import re


PHONE_NUMBER_ERROR = "Invalid phone number. Use international format like +919843731545"
_NON_DIGIT_RE = re.compile(r"\D+")


def normalize_phone_number(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        raise ValueError(PHONE_NUMBER_ERROR)

    compact = raw.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if compact.startswith("+"):
        digits = compact[1:]
        if digits.isdigit() and 8 <= len(digits) <= 15:
            return f"+{digits}"
        raise ValueError(PHONE_NUMBER_ERROR)

    digits = _NON_DIGIT_RE.sub("", raw)
    if len(digits) == 10 and digits.isdigit():
        return f"+91{digits}"
    if len(digits) == 12 and digits.startswith("91") and digits.isdigit():
        return f"+{digits}"

    raise ValueError(PHONE_NUMBER_ERROR)

