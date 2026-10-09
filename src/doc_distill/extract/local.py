"""Extractor layer: turn any supported input into DocUnits (IR pre-stage).

Each module owns one source family; ``extract.py`` routes by detected kind.
Heavy formats are optional-dependency guarded with actionable install hints
(the book-to-skill dependency philosophy).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List
from urllib.request import Request, urlopen

from ..ir import DocUnit

USER_AGENT = "doc-distill/0.1 (+local knowledge tooling)"
MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024  # 64 MB safety cap per remote resource


def fetch_url(url: str, timeout: int = 30) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:  # nosec - user-provided URL by design
        return resp.read(MAX_DOWNLOAD_BYTES)


def missing_dep_error(feature: str, extra: str, hint: str = "") -> SystemExit:
    msg = (
        f"[doc-distill] 处理{feature}需要可选依赖：pip install 'doc-distill[{extra}]'\n"
        f"  （或一次性全装：pip install 'doc-distill[all]'）{hint}"
    )
    return SystemExit(msg)


# ---------------------------------------------------------------------------
# Local formats
# ---------------------------------------------------------------------------

def extract_text_file(path: Path) -> DocUnit:
    raw = path.read_text(encoding="utf-8", errors="replace")
    return markdown_text_to_unit(raw, source=str(path))


def markdown_text_to_unit(raw: str, source: str) -> DocUnit:
    """Parse markdown/plain text into blocks (headings drive the outline)."""
    from ..ir import Block

    blocks: List[Block] = []
    lines = raw.splitlines()
    i = 0
    title = ""
    in_code = False
    code_lang = ""
    code_buf: List[str] = []
    para_buf: List[str] = []
    list_buf: List[str] = []
    quote_buf: List[str] = []

    def flush_para() -> None:
        nonlocal para_buf
        if para_buf:
            blocks.append(Block(kind="text", text=" ".join(para_buf).strip()))
            para_buf = []

    def flush_list() -> None:
        nonlocal list_buf
        if list_buf:
            blocks.append(Block(kind="list", text="\n".join(list_buf)))
            list_buf = []

    def flush_quote() -> None:
        nonlocal quote_buf
        if quote_buf:
            blocks.append(Block(kind="quote", text="\n".join(quote_buf)))
            quote_buf = []

    def flush_all() -> None:
        flush_para()
        flush_list()
        flush_quote()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if in_code:
            if stripped.startswith("```"):
                blocks.append(Block(kind="code", text="\n".join(code_buf), lang=code_lang))
                code_buf = []
                in_code = False
            else:
                code_buf.append(line)
            i += 1
            continue

        if stripped.startswith("```"):
            flush_all()
            in_code = True
            code_lang = stripped[3:].strip()
            i += 1
            continue

        m = __import__("re").match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush_all()
            level = len(m.group(1))
            text = m.group(2).strip().strip("#").strip()
            if level == 1 and not title:
                title = text
            blocks.append(Block(kind="heading", level=level, text=text))
            i += 1
            continue

        setext = False
        if stripped and i + 1 < len(lines):
            nxt = lines[i + 1].strip()
            if (nxt and all(c == "=" for c in nxt)) or (nxt and all(c == "-" for c in nxt)):
                level = 1 if nxt[0] == "=" else 2
                flush_all()
                if level == 1 and not title:
                    title = stripped
                blocks.append(Block(kind="heading", level=level, text=stripped))
                i += 2
                setext = True
        if setext:
            continue

        if not stripped:
            flush_all()
            i += 1
            continue

        if stripped.startswith(">"):
            flush_para()
            flush_list()
            quote_buf.append(stripped.lstrip(">").strip())
            i += 1
            continue

        lm = __import__("re").match(r"^[-*+]\s+(.*)$", stripped)
        om = __import__("re").match(r"^\d+[.)]\s+(.*)$", stripped)
        if lm or om:
            flush_para()
            flush_quote()
            list_buf.append((lm or om).group(1))
            i += 1
            continue

        flush_list()
        flush_quote()
        para_buf.append(stripped)
        i += 1

    flush_all()
    if in_code and code_buf:
        blocks.append(Block(kind="code", text="\n".join(code_buf), lang=code_lang))

    if not title:
        for block in blocks:
            if block.kind == "heading":
                title = block.text
                break
    if not title:
        title = Path(source).stem if not source.startswith("http") else source
    return DocUnit(source=source, title=title or "untitled", blocks=blocks)


def extract_docs_dir(root: Path, max_files: int = 500) -> List[DocUnit]:
    """Walk a local docs directory; text-ish files become DocUnits."""
    import os

    TEXT_EXTS = {".md", ".markdown", ".txt", ".rst", ".adoc", ".html", ".htm"}
    SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".idea", ".vscode"}
    units: List[DocUnit] = []
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in sorted(dirnames) if d not in SKIP_DIRS and not d.startswith(".")]
        dirnames.sort()
        rel = Path(dirpath).relative_to(root)
        for fn in sorted(filenames):
            if Path(fn).suffix.lower() not in TEXT_EXTS:
                continue
            if count >= max_files:
                print(f"[doc-distill] docs_dir 文件数超过 {max_files}，已截断", file=sys.stderr)
                return units
            fpath = Path(dirpath) / fn
            try:
                if fpath.suffix.lower() in (".html", ".htm"):
                    from .html_doc import extract_html_text

                    units.append(extract_html_text(fpath.read_text(encoding="utf-8", errors="replace"), source=str(fpath)))
                else:
                    units.append(extract_text_file(fpath))
                count += 1
            except Exception as exc:  # skip unreadable file, keep going
                print(f"[doc-distill] 跳过 {fpath}: {exc}", file=sys.stderr)
    prefix = str(root.name)
    for unit in units:
        unit.title = f"{prefix}/{unit.title}" if not unit.title.startswith(prefix) else unit.title
    return units
