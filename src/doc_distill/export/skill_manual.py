"""skill-manual exporter — the book-to-skill product spec.

Deterministic part: SKILL.md scaffold (pushy description, chapter map, full
text in references/full/) + distilled-section placeholders the hosting agent
fills per references/distill-spec.md.

Design property: the exported skill is *immediately usable* even with zero
distillation (index + on-demand full text = lookup-style skill); agent
distillation upgrades it to the full manual (frameworks/patterns/cheatsheet).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from ..ir import load_chunks
from ..utils import render_frontmatter, write_text
from ._common import build_outline_file_map, build_pushy_description, load_ir_all, write_full_references

# Embedded compact distillation instructions — keeps the generated skill
# self-contained even when doc-distill itself is not installed on the host.
_SELF_CONTAINED_SPEC = """
<!--
补全本手册（蒸馏规格摘要）：
1. 阅读用户的问题 → 判断应引用哪个章节（references/full/）→ 先读再答，答案注明出处块 [id]。
2. 通读 references/full/ 后补全下方三节（把 HTML 注释替换为正文）：
   - 核心框架：3-7 个命名框架/心智模型，保留作者的原始命名与精确表述，每个框架给出「何时用 + 一句话用法」。
   - 高频模式与技巧：从全书提炼可复用的模式、步骤化技巧、代码惯用法（如书中有代码，给最小可运行示例）。
   - 决策速查：一张「遇到 X → 做 Y」规则表，以及反模式清单（什么不要做、为什么）。
3. 硬性要求：结构而非摘要；不得虚构书中没有的内容；每条尽量标注来源章节；保留作者的口语与判断。
4. 补全后删除本注释块。
-->
""".strip()


def export_skill_manual(ir_dir: Path, out_dir: Path, slug: str = "") -> Path:
    meta, outline, _chunks = load_ir_all(ir_dir)
    slug = slug or meta.get("slug") or "doc"
    skill_dir = Path(out_dir) / slug
    chunks = load_chunks(ir_dir)

    full_files = write_full_references(ir_dir, skill_dir)
    description = build_pushy_description(meta, outline, len(chunks))
    outline_files = build_outline_file_map(outline, chunks, full_files)

    lines: List[str] = [
        render_frontmatter([("name", slug), ("description", description)]),
        "",
        f"# 《{meta.get('title', slug)}》知识手册",
        "",
        f"> 由 doc-distill 从 `{meta.get('type', 'text')}` 源生成；"
        f"共 {len(outline)} 个章节主题、{len(chunks)} 个内容块（~{meta.get('stats', {}).get('tokens', 0)} tokens）。",
        "",
        "## 何时使用",
        "",
        "- 用户的问题落在本书主题范围内（见下方章节地图）",
        f"- 需要《{meta.get('title', '')}》中的方法、概念、代码或决策规则",
        "- 按本书方法论执行任务时（先读对应章节再回答，注明出处块 [id]）",
        "",
        "## 章节地图",
        "",
        "| # | 主题 | 原文 |",
        "|---|---|---|",
    ]

    for idx, entry in enumerate(outline, start=1):
        lines.append(f"| {idx} | {entry['title']} | {outline_files[idx - 1] or '—'} |")
    lines.append("")

    lines += [
        "## 核心框架",
        "",
        "<!-- TODO(distill): 按 distill-spec 提炼 3-7 个命名框架/心智模型 -->",
        "",
        "## 高频模式与技巧",
        "",
        "<!-- TODO(distill): 提炼可复用的模式、步骤化技巧、代码惯用法 -->",
        "",
        "## 决策速查",
        "",
        "<!-- TODO(distill): 「遇到 X → 做 Y」规则表 + 反模式清单 -->",
        "",
        "## 深入阅读",
        "",
        "- 原文按章节分组存放在 `references/full/`，回答时按需读取对应文件，不必全部加载。",
        "- 检索技巧：先看上方章节地图定位主题 → 读对应文件 → 引用内容块 id。",
        "",
        _SELF_CONTAINED_SPEC,
        "",
    ]

    write_text(skill_dir / "SKILL.md", "\n".join(lines))
    write_text(
        skill_dir / "references" / "manifest.json",
        json.dumps(
            {
                "source_ir": str(ir_dir),
                "title": meta.get("title", ""),
                "type": meta.get("type", ""),
                "sections": [{"title": s, "file": f} for s, f in full_files],
                "stats": meta.get("stats", {}),
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    return skill_dir
