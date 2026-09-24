"""Local, schema-blind regex redaction with stable per-import pseudonyms."""

from __future__ import annotations

import hashlib
import hmac
import re
from typing import Any

_SENSITIVE_KEY = re.compile(
    r"(?:^|[_-])(api[_-]?key|secret|password|passwd|authorization|auth[_-]?token|"
    r"access[_-]?token|refresh[_-]?token|private[_-]?key|user[_-]?id|"
    r"session[_-]?id|email|ip[_-]?address)(?:$|[_-])",
    re.IGNORECASE,
)
MAX_DEPTH = 30
MAX_STRING_CHARS = 100_000
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("EMAIL", re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("SSN", re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")),
    (
        "IP",
        re.compile(
            r"(?<![\d.])(?:25[0-5]|2[0-4]\d|1?\d?\d)"
            r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?![\d.])"
        ),
    ),
    (
        "PHONE",
        re.compile(
            r"(?<!\w)(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)|\d{2,4})"
            r"[\s.-]\d{3,4}[\s.-]\d{4}(?!\w)"
        ),
    ),
    (
        "SECRET",
        re.compile(
            r"(?i)\b(?:bearer\s+[\w.~+/=-]{12,}|"
            r"(?:sk|pk|rk|api)[-_][A-Za-z0-9_-]{16,}|"
            r"AKIA[0-9A-Z]{16})"
        ),
    ),
)
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")


class Redactor:
    def __init__(self, import_fingerprint: bytes):
        self._key = hashlib.sha256(
            b"ollie-langfuse-redaction-v1\0" + import_fingerprint
        ).digest()
        self.truncated_strings = 0
        self.truncated_depth = 0

    def _pseudonym(self, kind: str, value: str) -> str:
        digest = hmac.new(
            self._key, f"{kind}\0{value}".encode("utf-8"), hashlib.sha256
        ).hexdigest()[:12]
        return f"<OLLIE_REDACTED_{kind}_{digest}>"

    @staticmethod
    def _is_card(match: re.Match[str]) -> bool:
        digits = [int(char) for char in match.group(0) if char.isdigit()]
        if not 13 <= len(digits) <= 19:
            return False
        checksum = 0
        parity = len(digits) % 2
        for index, digit in enumerate(digits):
            if index % 2 == parity:
                digit *= 2
                if digit > 9:
                    digit -= 9
            checksum += digit
        return checksum % 10 == 0

    def text(self, value: str) -> str:
        if len(value) > MAX_STRING_CHARS:
            value = value[:MAX_STRING_CHARS]
            self.truncated_strings += 1
        redacted = value
        for kind, pattern in _PATTERNS:
            redacted = pattern.sub(
                lambda match, label=kind: self._pseudonym(label, match.group(0)),
                redacted,
            )
        redacted = _CARD.sub(
            lambda match: (
                self._pseudonym("CARD", match.group(0))
                if self._is_card(match)
                else match.group(0)
            ),
            redacted,
        )
        return redacted

    def value(self, value: Any, key: str | None = None, _depth: int = 0) -> Any:
        if _depth > MAX_DEPTH:
            self.truncated_depth += 1
            return "<OLLIE_TRUNCATED_DEPTH>"
        if key and _SENSITIVE_KEY.search(key):
            return self._pseudonym("SECRET", str(value)[:MAX_STRING_CHARS])
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, list):
            return [self.value(item, _depth=_depth + 1) for item in value]
        if isinstance(value, dict):
            return {
                child_key: self.value(child_value, child_key, _depth + 1)
                for child_key, child_value in value.items()
            }
        return value
