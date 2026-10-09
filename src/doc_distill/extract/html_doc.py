"""Single HTML document extractor (file or fetched page).

Tries ``trafilatura`` (optional extra ``[web]``) for main-content extraction
quality, falls back to the built-in zero-dependency converter.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from ..html_convert import html_to_markdown
from ..ir import DocUnit
from .local import markdown_text_to_unit

try:  # optional quality upgrade
    import trafilatura  # type: ignore

    HAS_TRAFILATURA = True
except ImportError:
    trafilatura = None
    HAS_TRAFILATURA = False


def extract_html_text(html: str, source: str, base_url: str = "") -> DocUnit:
    markdown, title, _links = _convert(html, base_url=base_url or source)
    unit = markdown_text_to_unit(markdown, source=source)
    if title:
        unit.title = title
    if not unit.blocks:
        unit.blocks = unit.blocks  # keep empty; caller decides whether to skip
    return unit


def _convert(html: str, base_url: str = "") -> Tuple[str, str, list]:
    if HAS_TRAFILATURA and not base_url.startswith("file:"):
        try:
            downloaded = trafilatura.extract(
                html,
                output_format="markdown",
                include_links=True,
                include_tables=True,
                include_comments=False,
            )
            if downloaded:
                metadata = trafilatura.bare_extraction(html, only_with_metadata=False) or {}
                title = str(metadata.get("title", "") or "")
                # trafilatura drops links when returning markdown-with-links off;
                # normalize to unit via markdown parser, links lost is acceptable
                return downloaded, title, []
        except Exception:
            pass  # fall through to stdlib converter
    return html_to_markdown(html, base_url=base_url)
