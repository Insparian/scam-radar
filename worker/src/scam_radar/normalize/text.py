from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
ID_RE = re.compile(r"(?<![0-9A-Z])\d{17}[0-9Xx](?![0-9A-Z])")
BANK_RE = re.compile(r"(?<!\d)(?:\d[ -]?){15,19}(?!\d)")
URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
WHITESPACE_RE = re.compile(r"[\t\r\f\v ]+")
BLANK_LINES_RE = re.compile(r"\n{3,}")


@dataclass(frozen=True)
class NormalizedText:
    text: str
    truncated: bool
    pii_masked: bool


def defang_url(match: re.Match[str]) -> str:
    value = match.group(0)
    return value.replace("http://", "hxxp://").replace("https://", "hxxps://").replace(".", "[.]")


def normalize_text(
    value: str, *, max_chars: int = 50_000, defang_urls: bool = False
) -> NormalizedText:
    normalized = unicodedata.normalize("NFKC", value).replace("\u200b", "")
    normalized = "\n".join(WHITESPACE_RE.sub(" ", line).strip() for line in normalized.splitlines())
    normalized = BLANK_LINES_RE.sub("\n\n", normalized).strip()
    masked = False
    for expression, token in (
        (PHONE_RE, "[已隐藏手机号]"),
        (ID_RE, "[已隐藏身份证号]"),
        (BANK_RE, "[已隐藏账号]"),
    ):
        normalized, count = expression.subn(token, normalized)
        masked = masked or count > 0
    if defang_urls:
        normalized = URL_RE.sub(defang_url, normalized)
    truncated = len(normalized) > max_chars
    if truncated:
        normalized = normalized[:max_chars].rstrip()
    return NormalizedText(text=normalized, truncated=truncated, pii_masked=masked)
