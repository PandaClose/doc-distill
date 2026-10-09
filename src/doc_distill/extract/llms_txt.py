"""llms.txt adapter — the cheapest, highest-quality path for doc sites.

llms.txt is a markdown manifest at the site root listing canonical docs URLs.
We parse the link list and download each entry; ``.md`` links are kept raw,
everything else is run through the HTML converter.
Spec: https://llmstxt.org/
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from .html_doc import extract_html_text
from .local import fetch_url, markdown_text_to_unit

LINK_RE = re.compile(r"^\s*[-*]\s*\[([^\]]+)\]\(([^)\s]+)\)")


def parse_llms_txt(text: str) -> List[tuple]:
    """Returns [(title, absolute_or_relative_url), ...] from llms.txt content."""
    out = []
    for line in text.splitlines():
        m = LINK_RE.match(line)
        if m:
            title, url = m.group(1).strip(), m.group(2).strip()
            if not url.startswith(("mailto:", "javascript:")):
                out.append((title, url))
    return out


def _absolute(base: str, url: str) -> str:
    if url.startswith(("http://", "https://")):
        return url
    root = base.split("/llms.txt")[0] if "/llms.txt" in base else base.rstrip("/")
    return root + (url if url.startswith("/") else "/" + url)


def extract_llms_txt(llms_txt_url: str, max_pages: int = 50) -> List[tuple]:
    """Fetch llms.txt and return [(title, url)] manifest entries (bounded)."""
    text = fetch_url(llms_txt_url).decode("utf-8", errors="replace")
    entries = parse_llms_txt(text)[:max_pages]
    return [(_t, _absolute(llms_txt_url, _u)) for _t, _u in entries]


def extract_llms_site(llms_txt_url: str, max_pages: int = 50) -> List:
    """Download every manifest entry as a DocUnit."""
    units = []
    for title, url in extract_llms_txt(llms_txt_url, max_pages=max_pages):
        try:
            raw = fetch_url(url).decode("utf-8", errors="replace")
        except Exception as exc:
            print(f"[doc-distill] 跳过 {url}: {exc}")
            continue
        if url.lower().endswith((".md", ".markdown", ".mdx", ".txt")) or not raw.lstrip().startswith("<"):
            unit = markdown_text_to_unit(raw, source=url)
        else:
            unit = extract_html_text(raw, source=url, base_url=url)
        unit.title = title or unit.title
        units.append(unit)
        print(f"[doc-distill] llms.txt {len(units)}/{min(max_pages, 50)}: {title or url}")
    return units


def _unused(*_args) -> None:
    _ = Path
