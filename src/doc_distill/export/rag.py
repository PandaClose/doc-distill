"""RAG corpus exporters: JSONL (zero-dep default) and Markdown bundle.

JSONL row format::

    {"id": "0001", "text": "...", "metadata": {"source", "section", "title",
     "tokens", "type"}}

Drop-in for any embedding pipeline (LangChain / LlamaIndex / vector stores);
the plan's RAG-format extras (faiss/chroma/...) build on this in M4.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from ..ir import Chunk, load_chunks, load_source_meta
from ..utils import write_text


def _rows(ir_dir: Path) -> List[dict]:
    meta = load_source_meta(ir_dir)
    chunks: List[Chunk] = load_chunks(ir_dir)
    rows = []
    for chunk in chunks:
        rows.append(
            {
                "id": chunk.id,
                "text": chunk.body.strip(),
                "metadata": {
                    "source": chunk.source,
                    "section": chunk.section,
                    "title": chunk.title,
                    "tokens": chunk.tokens,
                    "type": meta.get("type", "text"),
                    "asset": meta.get("title", ""),
                },
            }
        )
    return rows


def export_rag_jsonl(ir_dir: Path, out_dir: Path, slug: str = "") -> Path:
    meta = load_source_meta(ir_dir)
    slug = slug or meta.get("slug") or "doc"
    target = Path(out_dir) / f"{slug}-rag" / "chunks.jsonl"
    rows = _rows(ir_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return target


def export_rag_markdown(ir_dir: Path, out_dir: Path, slug: str = "") -> Path:
    meta = load_source_meta(ir_dir)
    slug = slug or meta.get("slug") or "doc"
    target = Path(out_dir) / f"{slug}-rag" / "full.md"
    chunks = load_chunks(ir_dir)
    parts: List[str] = [
        f"# {meta.get('title', slug)} — RAG 语料（Markdown 包）",
        "",
        f"> 共 {len(chunks)} 块，~{meta.get('stats', {}).get('tokens', 0)} tokens；每块以 `<!-- [id] section -->` 标注。",
        "",
    ]
    for chunk in chunks:
        parts.append(f"<!-- [{chunk.id}] {chunk.section} -->")
        parts.append(chunk.body.strip())
        parts.append("")
    write_text(target, "\n".join(parts))
    return target
