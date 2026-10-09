"""Exporter registry."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List

EXPORTERS: Dict[str, Callable[[Path, Path, str], Path]] = {}


def _register(name: str):
    def deco(fn):
        EXPORTERS[name] = fn
        return fn

    return deco


_register("skill-manual")(lambda ir_dir, out_dir, slug: _lazy("skill_manual", "export_skill_manual", ir_dir, out_dir, slug))
_register("skill-router")(lambda ir_dir, out_dir, slug: _lazy("skill_router", "export_skill_router", ir_dir, out_dir, slug))
_register("rag-jsonl")(lambda ir_dir, out_dir, slug: _lazy("rag", "export_rag_jsonl", ir_dir, out_dir, slug))
_register("rag-markdown")(lambda ir_dir, out_dir, slug: _lazy("rag", "export_rag_markdown", ir_dir, out_dir, slug))


def _lazy(module: str, fn_name: str, ir_dir: Path, out_dir: Path, slug: str) -> Path:
    import importlib

    mod = importlib.import_module(f".{module}", package=__package__)
    return getattr(mod, fn_name)(ir_dir, out_dir, slug)


def run_exporters(ir_dir: Path, out_dir: Path, targets: List[str], slug: str = "") -> Dict[str, Path]:
    results: Dict[str, Path] = {}
    for target in targets:
        if target not in EXPORTERS:
            raise SystemExit(
                f"[doc-distill] 未知导出目标：{target}（可用：{', '.join(sorted(EXPORTERS))}）"
            )
        results[target] = EXPORTERS[target](Path(ir_dir), Path(out_dir), slug)
        print(f"[doc-distill] 导出 {target} → {results[target]}")
    return results
