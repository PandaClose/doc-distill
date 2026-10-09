"""Extractor dispatch: detected kind -> DocUnits."""

from __future__ import annotations

import glob as globmod
from pathlib import Path
from typing import List

from ..detect import detect_source
from ..ir import DocUnit

# re-export the public surface
from .local import extract_docs_dir, extract_text_file, markdown_text_to_unit  # noqa: F401
from .html_doc import extract_html_text  # noqa: F401


def extract_item(item: str, max_pages: int = 20, max_depth: int = 2) -> List[DocUnit]:
    """Extract one detected input into DocUnits. Raises SystemExit with an
    actionable hint when an optional dependency is missing."""
    info = detect_source(item)
    kind = info["kind"]
    if kind in ("unsupported", "missing"):
        raise SystemExit(f"[doc-distill] {info['detail']}")

    if kind in ("text",):
        return [extract_text_file(Path(item))]
    if kind == "html":
        if item.startswith("http"):
            from .local import fetch_url

            html = fetch_url(item).decode("utf-8", errors="replace")
            return [extract_html_text(html, source=item, base_url=item)]
        return [extract_html_text(Path(item).read_text(encoding="utf-8", errors="replace"), source=str(item))]
    if kind == "pdf":
        from .documents import extract_pdf

        return extract_pdf(Path(item))
    if kind == "epub":
        from .documents import extract_epub

        return extract_epub(Path(item))
    if kind == "docx":
        from .documents import extract_docx

        return extract_docx(Path(item))
    if kind == "rtf":
        from .documents import extract_rtf

        return extract_rtf(Path(item))
    if kind == "calibre":
        from .documents import extract_calibre

        return extract_calibre(Path(item))
    if kind == "docs_dir":
        return extract_docs_dir(Path(item))
    if kind == "github":
        from .github import extract_github_repo

        return extract_github_repo(item)
    if kind == "llms_txt":
        from .llms_txt import extract_llms_site

        return extract_llms_site(item, max_pages=max(max_pages, 50) if max_pages >= 20 else max_pages)
    if kind == "website":
        from .website import extract_website

        return extract_website(item, max_pages=max_pages, max_depth=max_depth)

    raise SystemExit(f"[doc-distill] 未知源类型：{kind}（{item}）")


def extract_inputs(inputs: List[str], max_pages: int = 20, max_depth: int = 2) -> List[DocUnit]:
    from ..detect import expand_inputs

    units: List[DocUnit] = []
    for item in expand_inputs(inputs):
        print(f"[doc-distill] 提取：{item}（类型 {detect_source(item)['kind']}）")
        units.extend(extract_item(item, max_pages=max_pages, max_depth=max_depth))
    return units
