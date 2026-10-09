"""Shared helpers: slugs, token estimation, markdown frontmatter, misc IO."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import List, Optional


def estimate_tokens(text: str) -> int:
    """Rough token estimate. CJK chars count ~1 token each; ASCII ~4 chars/token."""
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff" or "\u3000" <= ch <= "\u30ff")
    ascii_len = len(text) - cjk
    return max(1, cjk + ascii_len // 4)


def slugify(text: str, fallback: str = "doc", max_len: int = 40) -> str:
    """ASCII lowercase kebab-case slug safe for skill names and filenames.

    CJK and other non-ASCII chars are dropped; if nothing survives, use
    ``fallback`` plus a short content hash so the slug is still unique.
    """
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    text = re.sub(r"-{2,}", "-", text)
    if not text:
        return fallback
    return text[:max_len].strip("-") or fallback


def stable_slug(text: str, fallback: str = "doc", max_len: int = 40) -> str:
    """Like slugify, but guarantees a non-empty unique slug for pure-CJK input
    by appending a digest of the original text."""
    slug = slugify(text, fallback=fallback, max_len=max_len)
    if slug == fallback and text:
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:6]
        return f"{fallback}-{digest}"
    return slug


def guess_title_from_source(source: str) -> str:
    """Derive a human title from a path or URL."""
    s = source.rstrip("/")
    if "://" in s:
        s = s.split("://", 1)[1]
    name = s.rstrip("/").split("/")[-1]
    name = re.sub(r"\.[a-zA-Z0-9]{1,5}$", "", name)
    name = name.replace("-", " ").replace("_", " ").strip()
    return name or source


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def render_frontmatter(fields: List[tuple]) -> str:
    """Render simple ``key: value`` YAML-ish frontmatter (no nesting)."""
    lines = ["---"]
    for key, value in fields:
        value = str(value).replace("\n", " ").strip()
        if any(ch in value for ch in ":#[]{}>") and not (value.startswith('"') and value.endswith('"')):
            value = '"%s"' % value.replace('"', '\\"')
        lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def parse_frontmatter(text: str) -> "tuple[dict, str]":
    """Split ``---`` delimited frontmatter from a markdown string.

    Returns (fields_dict, body). Tolerates missing frontmatter.
    """
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    if lines[0].strip() != "---":
        return {}, text
    fields = {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            body = "\n".join(lines[i + 1:]).lstrip("\n")
            return fields, body
        if ":" in line:
            key, _, value = line.partition(":")
            value = value.strip()
            if value.startswith('"') and value.endswith('"') and len(value) >= 2:
                value = value[1:-1].replace('\\"', '"')
            fields[key.strip()] = value
    return {}, text


def short_hash(text: str, n: int = 8) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:n]


def truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def find_existing(paths: List[str]) -> Optional[str]:
    for p in paths:
        if Path(p).exists():
            return p
    return None
