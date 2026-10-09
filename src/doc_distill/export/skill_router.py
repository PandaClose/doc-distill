"""skill-router exporter — the Skill_Seekers-style thin router product.

SKILL.md = description + section map + "read the referenced file on demand"
rules. references/full/ carries the complete text. No distillation sections —
best for reference-style assets (API docs, repos) where fidelity beats curation.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from ..ir import load_chunks
from ..utils import render_frontmatter, write_text
from ._common import build_outline_file_map, build_pushy_description, load_ir_all, write_full_references


def export_skill_router(ir_dir: Path, out_dir: Path, slug: str = "") -> Path:
    meta, outline, _ = load_ir_all(ir_dir)
    slug = slug or meta.get("slug") or "doc"
    skill_dir = Path(out_dir) / f"{slug}-router"
    chunks = load_chunks(ir_dir)

    full_files = write_full_references(ir_dir, skill_dir)
    description = build_pushy_description(meta, outline, len(chunks))
    outline_files = build_outline_file_map(outline, chunks, full_files)

    lines: List[str] = [
        render_frontmatter([("name", slug), ("description", description)]),
        "",
        f"# {meta.get('title', slug)} — 查阅路由",
        "",
        "## 使用规则",
        "",
        "1. 先在下方章节地图中定位与用户问题最相关的主题（可同时借助 Grep 在 references/full/ 中搜索关键词）。",
        "2. 只读取命中的 1~2 个文件，回答需注明来源（文件 + 内容块 id）。",
        "3. 地图与文件都没有覆盖的问题，如实说明「该资料未覆盖」，不要编造。",
        "",
        "## 章节地图",
        "",
        "| # | 主题 | 原文文件 |",
        "|---|---|---|",
    ]
    for idx, entry in enumerate(outline, start=1):
        rel = outline_files[idx - 1] or "—"
        lines.append(f"| {idx} | {entry['title']} | `{rel}` |")

    lines += [
        "",
        "## 关键词速查",
        "",
        "```text",
        "# 在 references/full/ 中找代码/报错/概念：",
        '#   grep -rn "关键词" references/full/',
        "```",
        "",
    ]

    write_text(skill_dir / "SKILL.md", "\n".join(lines))
    return skill_dir
