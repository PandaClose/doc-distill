"""doc-distill CLI.

    doc-distill detect   <INPUT>...                     识别源类型
    doc-distill extract  <INPUT>... -o IR_DIR           提取为统一 IR
    doc-distill export   IR_DIR --targets ... -o DIR    从 IR 导出产物
    doc-distill run      <INPUT>... -o DIR              一条龙（确定性管线，无蒸馏）
    doc-distill validate SKILL_DIR [--strict]            校验生成的 skill

蒸馏本身由宿主 agent 完成（skill 模式，零 API）；CI/无宿主场景可配 API 引擎（M3）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .detect import detect_all
from .export import run_exporters
from .ir import write_ir
from .utils import guess_title_from_source, stable_slug
from .validate import validate_skill

ALL_TARGETS = "skill-manual, skill-router, rag-jsonl, rag-markdown"


def _cmd_detect(args: argparse.Namespace) -> int:
    results = detect_all(args.inputs)
    for item in results:
        flag = item["kind"] if item["kind"] not in ("unsupported", "missing") else "✗"
        print(f"{flag:>12}  {item['input']}  ({item['detail']})")
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all(r["kind"] not in ("unsupported", "missing") for r in results) else 1


def _cmd_extract(args: argparse.Namespace) -> int:
    from .extract import extract_inputs

    units = extract_inputs(args.inputs, max_pages=args.max_pages, max_depth=args.max_depth)
    if not units:
        print("[doc-distill] 错误：未提取到任何内容", file=sys.stderr)
        return 1

    title = args.title or guess_title_from_source(args.inputs[0])
    slug = stable_slug(args.slug or title, fallback="doc")
    stats = write_ir(
        Path(args.out),
        slug=slug,
        title=title,
        source_type=args.type or _guess_type(args.inputs),
        doc_units=units,
        chunker_cfg={"max_tokens": args.chunk_size, "overlap_tokens": args.overlap},
        append=args.append,
    )
    print(f"[doc-distill] IR 写入 {args.out}：{stats['chunks']} 块 / ~{stats['tokens']} tokens / {stats['docs']} 源")
    if args.json:
        print(json.dumps({"ir": args.out, "slug": slug, "title": title, "stats": stats}, ensure_ascii=False, indent=2))
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    ir_dir = Path(args.ir_dir)
    if not (ir_dir / "source.json").exists():
        print(f"[doc-distill] 错误：{ir_dir} 不是有效的 IR 目录（缺 source.json）", file=sys.stderr)
        return 1
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    results = run_exporters(ir_dir, Path(args.out), targets, slug=args.slug or "")
    if args.json:
        print(json.dumps({k: str(v) for k, v in results.items()}, ensure_ascii=False, indent=2))
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    """One-shot deterministic pipeline: extract -> IR -> export (no distill)."""
    from .extract import extract_inputs

    units = extract_inputs(args.inputs, max_pages=args.max_pages, max_depth=args.max_depth)
    if not units:
        print("[doc-distill] 错误：未提取到任何内容", file=sys.stderr)
        return 1

    title = args.title or units[0].title or guess_title_from_source(args.inputs[0])
    slug = stable_slug(args.slug or title, fallback="doc")
    ir_dir = Path(args.out) / f"{slug}.ir"
    stats = write_ir(
        ir_dir,
        slug=slug,
        title=title,
        source_type=args.type or _guess_type(args.inputs),
        doc_units=units,
        chunker_cfg={"max_tokens": args.chunk_size, "overlap_tokens": args.overlap},
        append=args.append,
    )
    print(f"[doc-distill] IR：{ir_dir}（{stats['chunks']} 块）")

    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    results = run_exporters(ir_dir, Path(args.out), targets, slug=slug)
    print(
        f"\n[doc-distill] 完成：《{title}》→ {stats['chunks']} 块 / ~{stats['tokens']} tokens\n"
        f"  产物目录：{Path(args.out).resolve()}\n"
        f"  下一步：把 skill 目录移入 ~/.agents/skills/ 即可全局使用；\n"
        f"  或在本 skill 触发的会话中让宿主 agent 按 SKILL.md 内注释补全蒸馏三节。"
    )
    if args.json:
        print(json.dumps({"slug": slug, "ir": str(ir_dir), "stats": stats, "exports": {k: str(v) for k, v in results.items()}}, ensure_ascii=False, indent=2))
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    problems = validate_skill(Path(args.skill_dir), strict=args.strict)
    if problems:
        print(f"[doc-distill] {args.skill_dir}")
        for problem in problems:
            print(f"  - {problem}")
        hard = [p for p in problems if not p.startswith("提示")]
        return 1 if (hard or args.strict) else 0
    print(f"[doc-distill] ✓ {args.skill_dir} 通过校验")
    return 0


def _guess_type(inputs: list) -> str:
    info = detect_all(inputs)[0]
    return info["kind"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doc-distill",
        description="把文档资产蒸馏为手册型 agent skill + RAG 语料（零核心依赖，无 API/无 Docker）",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("detect", help="识别输入源类型")
    p.add_argument("inputs", nargs="+", help="文件/目录/URL/glob")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_detect)

    p = sub.add_parser("extract", help="提取为统一 IR（供宿主 agent 蒸馏或后续导出）")
    p.add_argument("inputs", nargs="+")
    p.add_argument("-o", "--out", required=True, help="IR 输出目录")
    p.add_argument("--title", default="", help="资产标题（默认从输入推断）")
    p.add_argument("--slug", default="", help="slug（默认从标题生成）")
    p.add_argument("--type", default="", help="源类型标记（默认自动）")
    p.add_argument("--append", action="store_true", help="并入已有 IR（fold-in 增量更新）")
    p.add_argument("--max-pages", type=int, default=20, help="website/llms.txt 最大抓取页数（默认 20）")
    p.add_argument("--max-depth", type=int, default=2, help="website 爬取深度（默认 2）")
    p.add_argument("--chunk-size", type=int, default=512, help="块大小上限 tokens（默认 512）")
    p.add_argument("--overlap", type=int, default=50, help="块间重叠 tokens（默认 50）")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_extract)

    p = sub.add_parser("export", help="从 IR 导出产物")
    p.add_argument("ir_dir", help="IR 目录（含 source.json）")
    p.add_argument("--targets", default="skill-manual,rag-jsonl", help=f"逗号分隔，可选：{ALL_TARGETS}")
    p.add_argument("-o", "--out", required=True, help="产物输出目录")
    p.add_argument("--slug", default="", help="覆盖 slug")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_export)

    p = sub.add_parser("run", help="一条龙：提取 → IR → 导出（确定性管线，蒸馏交给宿主 agent）")
    p.add_argument("inputs", nargs="+")
    p.add_argument("-o", "--out", required=True, help="产物输出目录")
    p.add_argument("--targets", default="skill-manual,rag-jsonl,rag-markdown")
    p.add_argument("--title", default="", help="资产标题（默认从输入推断）")
    p.add_argument("--slug", default="", help="slug（默认从标题生成）")
    p.add_argument("--type", default="", help="源类型标记（默认自动）")
    p.add_argument("--append", action="store_true", help="并入已有 IR 后重导出")
    p.add_argument("--max-pages", type=int, default=20)
    p.add_argument("--max-depth", type=int, default=2)
    p.add_argument("--chunk-size", type=int, default=512)
    p.add_argument("--overlap", type=int, default=50)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_run)

    p = sub.add_parser("validate", help="校验生成的 skill")
    p.add_argument("skill_dir")
    p.add_argument("--strict", action="store_true", help="蒸馏占位未补全视为失败")
    p.set_defaults(func=_cmd_validate)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n[doc-distill] 已中断", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
