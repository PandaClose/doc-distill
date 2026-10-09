"""Shared helpers for exporters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

from ..ir import Chunk, group_chunks_by_top_section, load_chunks, load_outline, load_source_meta
from ..utils import stable_slug, write_text


def build_pushy_description(meta: dict, outline: List[dict], chunks_count: int) -> str:
    """Draft the always-in-context description that decides triggering."""
    title = meta.get("title", "")
    topics = "、".join(e["title"] for e in outline[:6])
    source_type = meta.get("type", "text")
    type_label = {
        "github": "代码仓库",
        "website": "文档站",
        "llms_txt": "文档站",
        "epub": "电子书",
        "pdf": "书籍",
    }.get(source_type, "文档")
    desc = (
        f"《{title}》知识手册（源自{type_label}，{len(outline)} 个章节主题、{chunks_count} 个内容块）。"
        f"当用户问到该{type_label}覆盖的主题（如：{topics}），想查阅其中概念、方法、"
        f"代码或决策规则，或明确提到《{title}》时使用。"
    )
    return desc.replace("\n", " ").strip()


def write_full_references(ir_dir: Path, skill_dir: Path) -> List[Tuple[str, str]]:
    """Copy IR chunks into references/full/chNN-<slug>.md grouped by top section.

    Returns [(section_title, relative_path)] preserving document order.
    """
    chunks = load_chunks(ir_dir)
    groups = group_chunks_by_top_section(chunks)
    out: List[Tuple[str, str]] = []
    full_dir = skill_dir / "references" / "full"
    for idx, (section, section_chunks) in enumerate(groups, start=1):
        parts: List[str] = [f"# {section}", ""]
        for chunk in section_chunks:
            parts.append(f"<!-- [{chunk.id}] {chunk.section} · ~{chunk.tokens} tokens · {chunk.source} -->")
            parts.append(chunk.body.strip())
            parts.append("")
        fname = f"ch{idx:02d}-{stable_slug(section, max_len=32)}.md"
        write_text(full_dir / fname, "\n".join(parts).rstrip() + "\n")
        out.append((section, f"references/full/{fname}"))
    return out


def load_ir_all(ir_dir: Path):
    meta = load_source_meta(ir_dir)
    outline = load_outline(ir_dir)
    chunks = load_chunks(ir_dir)
    return meta, outline, chunks


def chunk_toc_rows(chunks: List[Chunk], full_files: List[Tuple[str, str]]):
    """Map each top-section to its full-text file for the SKILL.md index."""
    lookup: Dict[str, str] = {}
    for section, relpath in full_files:
        lookup[section] = relpath
    return lookup


def build_outline_file_map(outline, chunks, full_files) -> List[str]:
    """For every outline entry, resolve which references/full file contains it.

    Matching is by section-path component, since outline titles are heading
    paths without the document-title root while chunk sections include it.
    Returns a list parallel to ``outline`` ("" when unresolved).
    """
    top_to_file = {section: rel for section, rel in full_files}
    component_to_file: Dict[str, str] = {}
    for chunk in chunks:
        rel = top_to_file.get(chunk.section.split(" > ")[0], "")
        if not rel:
            continue
        for comp in chunk.section.split(" > "):
            comp = comp.strip()
            if comp and comp not in component_to_file:
                component_to_file[comp] = rel

    resolved: List[str] = []
    for entry in outline:
        title = entry["title"]
        rel = component_to_file.get(title, "")
        if not rel and " > " in title:
            rel = component_to_file.get(title.split(" > ")[-1].strip(), "")
        resolved.append(rel)
    return resolved
