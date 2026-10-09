"""GitHub repository extractor (no PyGithub — stdlib only).

Remote: downloads the repo tarball via codeload (no git binary needed), walks
text/code files with vendor-aware skip rules.
Local: accepts a path to a repo/checkout or any docs directory.
Concepts ported from Skill_Seekers' github_scraper / codebase_scraper.
"""

from __future__ import annotations

import io
import re
import tarfile
from pathlib import Path
from typing import List, Optional

from ..ir import DocUnit
from .local import extract_docs_dir, extract_text_file, fetch_url

CODELOAD_URL = "https://codeload.github.com/{repo}/tar.gz/HEAD"
MAX_FILE_BYTES = 512 * 1024
MAX_TOTAL_FILES = 800

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", "target", "vendor", "packages", ".idea", ".vscode",
    "coverage", ".next", ".nuxt", "Pods", "DerivedData",
}
DOC_EXTS = {".md", ".markdown", ".txt", ".rst", ".adoc"}
CODE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt", ".swift",
    ".c", ".h", ".cpp", ".hpp", ".cs", ".rb", ".php", ".sh", ".bash", ".zsh",
    ".sql", ".yaml", ".yml", ".toml", ".json", ".vue", ".svelte", ".dart", ".scala",
}
CODE_MAX_LINES = 400  # code files are distilled as overview snippets


def repo_slug(item: str) -> Optional[str]:
    m = re.match(r"^https?://(?:www\.)?github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", item)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    p = Path(item)
    if p.is_dir() and (p / ".git").exists():
        return None  # local handled separately
    return None


def _wanted(name: str, is_dir: bool) -> bool:
    parts = Path(name).parts
    if any(part in SKIP_DIRS or part.startswith(".") for part in parts[:-1]):
        return False
    if is_dir:
        return not Path(name).name.startswith(".")
    ext = Path(name).suffix.lower()
    return ext in DOC_EXTS or ext in CODE_EXTS


def extract_github_repo(item: str) -> List[DocUnit]:
    slug = repo_slug(item)
    units: List[DocUnit] = []

    if slug is None:
        # local repo / directory
        root = Path(item).expanduser()
        return extract_docs_dir(root, max_files=MAX_TOTAL_FILES)

    print(f"[doc-distill] 下载仓库 tarball：{slug}（无需 git）")
    blob = fetch_url(CODELOAD_URL.format(repo=slug))
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
        members = [m for m in tar.getmembers() if m.isfile() and _wanted(m.name, False)]
        # docs first, then code, then the rest — priority ordering
        def priority(m) -> tuple:
            name = m.name
            base = name.split("/", 1)[-1]
            if base.lower() in ("readme.md", "readme"):
                return (0, name)
            ext = Path(name).suffix.lower()
            return (1 if ext in DOC_EXTS else 2, name)

        members.sort(key=priority)
        count = 0
        for member in members:
            if count >= MAX_TOTAL_FILES:
                print(f"[doc-distill] 仓库文件数超过 {MAX_TOTAL_FILES}，已截断")
                break
            try:
                fh = tar.extractfile(member)
                if fh is None:
                    continue
                data = fh.read(MAX_FILE_BYTES + 1)
            except Exception:
                continue
            if len(data) > MAX_FILE_BYTES:
                continue
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                continue
            rel = member.name.split("/", 1)[-1]  # strip repo-name prefix
            ext = Path(rel).suffix.lower()
            if ext in CODE_EXTS and ext not in DOC_EXTS:
                lines = text.splitlines()
                if len(lines) > CODE_MAX_LINES:
                    text = "\n".join(lines[:CODE_MAX_LINES]) + f"\n<!-- … 截断，原文件 {len(lines)} 行 -->"
                doc_text = f"# `{rel}`\n\n```{ext.lstrip('.')}\n{text}\n```\n"
                unit = DocUnit(source=f"{slug}/{rel}", title=rel, blocks=[])
                from .local import markdown_text_to_unit

                parsed = markdown_text_to_unit(doc_text, source=f"{slug}/{rel}")
                parsed.title = rel
                units.append(parsed)
            else:
                unit = extract_text_file_from_text(text, source=f"{slug}/{rel}", title=rel)
                units.append(unit)
            count += 1

    print(f"[doc-distill] GitHub 仓库提取完成：{len(units)} 个文件")
    return units


def extract_text_file_from_text(text: str, source: str, title: str = "") -> DocUnit:
    from .local import markdown_text_to_unit

    unit = markdown_text_to_unit(text, source=source)
    if title:
        unit.title = title
    return unit
