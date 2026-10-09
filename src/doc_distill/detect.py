"""Source type detection — inspired by Skill_Seekers' source_detector.

Classifies a user input (path / URL / glob) into an extractor name so the
pipeline can route it. Zero dependencies; network I/O only when the input is
a URL (and only to read headers/body, never to execute anything).
"""

from __future__ import annotations

import glob as globmod
import re
from pathlib import Path
from typing import List, Optional

EXT_MAP = {
    ".md": "text",
    ".markdown": "text",
    ".mdx": "text",
    ".txt": "text",
    ".rst": "text",
    ".adoc": "text",
    ".html": "html",
    ".htm": "html",
    ".xhtml": "html",
    ".pdf": "pdf",
    ".epub": "epub",
    ".docx": "docx",
    ".rtf": "rtf",
    ".mobi": "calibre",
    ".azw": "calibre",
    ".azw3": "calibre",
}

GITHUB_RE = re.compile(r"^https?://(?:www\.)?github\.com/([\w.-]+)/([\w.-]+)", re.I)
LLMS_TXT_RE = re.compile(r"llms\.txt$", re.I)
URL_RE = re.compile(r"^https?://", re.I)

SUPPORTED = ["text", "html", "pdf", "epub", "docx", "rtf", "calibre", "website", "llms_txt", "github", "docs_dir"]


def expand_inputs(inputs: List[str]) -> List[str]:
    """Expand glob patterns; return concrete paths/URLs preserving order."""
    out: List[str] = []
    for item in inputs:
        if URL_RE.match(item) or Path(item).exists():
            out.append(item)
            continue
        matches = sorted(globmod.glob(item))
        if matches:
            out.extend(matches)
        else:
            out.append(item)  # let the extractor raise a helpful error
    return out


def detect_source(item: str) -> dict:
    """Classify one input. Returns {"kind": ..., "detail": ...}."""
    if URL_RE.match(item):
        return _detect_url(item)

    path = Path(item).expanduser()
    if path.exists():
        if path.is_dir():
            if (path / ".git").exists():
                return {"kind": "github", "detail": "local git repo"}
            return {"kind": "docs_dir", "detail": str(path)}
        ext = path.suffix.lower()
        kind = EXT_MAP.get(ext)
        if kind:
            return {"kind": kind, "detail": str(path)}
        if ext == ".zip":
            return {"kind": "unsupported", "detail": "zip 未解压；EPUB 是特殊 zip，可直接传 .epub 文件"}
        return {
            "kind": "unsupported",
            "detail": f"不支持的扩展名 {ext or '(无)'}；支持：{' '.join(sorted(set(EXT_MAP)))} 或目录/URL",
        }

    if any(ch in item for ch in "*?["):
        return {"kind": "unsupported", "detail": f"glob 未匹配到任何文件：{item}"}
    # non-existent path: route by extension when possible (the extractor will
    # raise a clear read error later), otherwise report missing/unsupported
    ext = path.suffix.lower()
    kind = EXT_MAP.get(ext)
    if kind:
        return {"kind": kind, "detail": f"{item}（注意：路径当前不存在）"}
    if ext:
        return {"kind": "unsupported", "detail": f"不支持的扩展名 {ext}；支持：{' '.join(sorted(set(EXT_MAP)))} 或目录/URL"}
    return {"kind": "missing", "detail": f"路径不存在：{item}"}


def _detect_url(url: str) -> dict:
    if GITHUB_RE.match(url):
        m = GITHUB_RE.match(url)
        return {"kind": "github", "detail": f"{m.group(1)}/{m.group(2).removesuffix('.git') if hasattr(str, 'removesuffix') else m.group(2)}"}
    if LLMS_TXT_RE.search(url):
        return {"kind": "llms_txt", "detail": url}
    lower = url.lower()
    for ext, kind in EXT_MAP.items():
        if lower.endswith(ext):
            return {"kind": kind if kind != "text" else "text", "detail": url}
    return {"kind": "website", "detail": url}


def detect_all(inputs: List[str]) -> List[dict]:
    return [dict(detect_source(item), input=item) for item in expand_inputs(inputs)]


def first_github_repo(urls: List[str]) -> Optional[str]:
    for url in urls:
        m = GITHUB_RE.match(url)
        if m:
            owner, repo = m.group(1), m.group(2)
            if repo.endswith(".git"):
                repo = repo[:-4]
            return f"{owner}/{repo}"
    return None
