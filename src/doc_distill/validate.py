"""Quality gate for generated skills (adapted from book-to-skill's validator)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from .utils import parse_frontmatter

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def validate_skill(skill_dir: Path, strict: bool = False) -> List[str]:
    """Returns a list of problems (empty = pass). strict additionally fails on
    unfinished distillation TODOs."""
    problems: List[str] = []
    skill_dir = Path(skill_dir)
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return [f"缺少 SKILL.md：{skill_md}"]

    fields, body = parse_frontmatter(skill_md.read_text(encoding="utf-8"))

    name = fields.get("name", "")
    if not name:
        problems.append("frontmatter 缺少 name")
    elif not NAME_RE.match(name):
        problems.append(f"name 不符合规范（小写 kebab-case，1-64 字符）：{name}")
    elif skill_dir.name and name != skill_dir.name:
        problems.append(f"name 与目录名不一致：{name} ≠ {skill_dir.name}")

    description = fields.get("description", "")
    if len(description) < 30:
        problems.append(f"description 过短（{len(description)} 字符）——它是唯一的常驻触发信号，应具体、偏触发友好")

    # referenced files must exist; trailing-slash refs are directory mentions
    for ref in set(re.findall(r"references/[\w./-]+", body)):
        if ref.endswith("/"):
            continue
        if not (skill_dir / ref).exists():
            problems.append(f"SKILL.md 引用了不存在的文件：{ref}")

    todo_count = body.count("TODO(distill)")
    if todo_count and strict:
        problems.append(f"还有 {todo_count} 处蒸馏占位未补全（--strict 模式不允许）")
    elif todo_count:
        problems.append(
            f"提示：{todo_count} 处蒸馏占位待补全（骨架模式可用；完整手册需宿主 agent 按 distill-spec 补全）"
        )
    return problems
