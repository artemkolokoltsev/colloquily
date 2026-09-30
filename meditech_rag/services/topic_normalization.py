from __future__ import annotations

import re
import unicodedata


ICON_OR_REPLACEMENT = re.compile(r"[\ue000-\uf8ff\ufffd]")
SLIDE_PREFIX = re.compile(
    r"^[\s\W_]*(?:(?:page|slide|chapter|lecture)\s*)?\d+(?:[.\-:]\d+)*[\s.:\-_]*",
    re.I,
)
GENERIC_OR_UNCERTAIN = {
    "additional",
    "author",
    "conditions",
    "contents",
    "example",
    "examples",
    "introduction",
    "license",
    "link",
    "overview",
    "solution",
    "source",
    "structure",
    "student",
    "summary",
    "teacher",
    "techniques",
    "theories",
    "title",
    "tutor",
    "worker",
    "you",
}


def _clean_part(value: str) -> str:
    value = SLIDE_PREFIX.sub("", value)
    value = re.sub(r"\s*\(\s*\d+\s*\)\s*$", "", value)
    value = re.sub(r"\s+\d+\s*$", "", value)
    value = re.sub(r"\s+", " ", value).strip(" -–—:;,.|•…")
    return value


def normalize_topic_titles(raw_title: str | None) -> list[str]:
    """Return clean topic candidates while leaving source text untouched.

    PDF icon-font glyphs are separators rather than letters. Treating them as
    separators also recovers accidentally concatenated headings.
    """
    text = unicodedata.normalize("NFKC", str(raw_title or ""))
    if not text.strip() or text.strip().casefold() == "unassigned":
        return []
    text = ICON_OR_REPLACEMENT.sub("\n", text)
    raw_parts = re.split(r"[\r\n|]+|\s*[•▪◦]\s*", text)
    parts: list[str] = []
    seen: set[str] = set()
    for raw_part in raw_parts:
        part = _clean_part(raw_part)
        key = part.casefold()
        if len(part) < 3 or part.isdigit() or key in GENERIC_OR_UNCERTAIN:
            continue
        if re.fullmatch(r"(?:page|slide|lecture)\s*\d+", part, re.I):
            continue
        if key not in seen:
            seen.add(key)
            parts.append(part)
    return parts


def single_topic_title(raw_title: str | None) -> str | None:
    """Return one unambiguous topic; multi-heading fragments stay Unassigned."""
    titles = normalize_topic_titles(raw_title)
    return titles[0] if len(titles) == 1 else None
