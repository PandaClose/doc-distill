"""Unified Intermediate Representation (IR) — the hub of the whole pipeline.

Layout on disk::

    <ir-dir>/
    ├── source.json     metadata: slug, title, type, sources[], stats
    ├── outline.json    flat ordered heading list with anchors
    └── chunks/
        └── 0001-<slug>.md   chunked body with simple frontmatter

Every extractor produces ``DocUnit``s; every exporter consumes a loaded IR.
Nothing else in the codebase couples extractors to exporters.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .utils import (
    estimate_tokens,
    parse_frontmatter,
    render_frontmatter,
    stable_slug,
    write_text,
)

SOURCE_FILE = "source.json"
OUTLINE_FILE = "outline.json"
CHUNKS_DIR = "chunks"


@dataclass
class Block:
    """A structural unit of a document. ``kind`` is one of
    heading | text | code | quote | list."""

    kind: str
    text: str
    level: int = 0  # heading level (1-6); ignored for other kinds
    lang: str = ""  # code fence language hint


@dataclass
class DocUnit:
    """One extracted source document (a chapter file, a crawled page, a repo
    file...). An input asset may expand into many DocUnits."""

    source: str  # original path or URL
    title: str
    blocks: List[Block] = field(default_factory=list)


@dataclass
class Chunk:
    """A chunk as stored in the IR."""

    id: str
    title: str
    source: str
    section: str  # heading path joined with " > "
    tokens: int
    body: str
    file: str = ""  # filename inside chunks/
    # outline hints (not persisted in frontmatter)
    heading_level: int = 0
    heading_title: str = ""


# ---------------------------------------------------------------------------
# Extraction results -> IR
# ---------------------------------------------------------------------------

def write_ir(
    ir_dir: Path,
    slug: str,
    title: str,
    source_type: str,
    doc_units: List[DocUnit],
    chunker_cfg: Optional[dict] = None,
    append: bool = False,
) -> dict:
    """Chunk ``doc_units`` and write a complete IR directory.

    With ``append=True``, existing chunks are kept and new ones are numbered
    after them (fold-in support); source.json is merged.
    Returns the stats dict written into source.json.
    """
    from .chunker import chunk_doc_units

    ir_dir = Path(ir_dir)
    chunks_dir = ir_dir / CHUNKS_DIR
    chunks_dir.mkdir(parents=True, exist_ok=True)

    if append and (ir_dir / SOURCE_FILE).exists():
        meta = load_source_meta(ir_dir)
        start_index = count_existing_chunks(chunks_dir)
    else:
        meta = {
            "slug": slug,
            "title": title or slug,
            "type": source_type,
            "sources": [],
            "stats": {},
        }
        start_index = 0

    meta["sources"].append(
        {"source": ", ".join(u.source for u in doc_units[:5]) or title, "type": source_type}
    )

    cfg = chunker_cfg or {}
    chunks = chunk_doc_units(doc_units, start_index=start_index, **cfg)

    outline: List[dict] = []
    total_tokens = 0
    for chunk in chunks:
        fname = f"{chunk.id}-{stable_slug(chunk.title, max_len=30)}.md"
        chunk.file = fname
        fm = render_frontmatter(
            [
                ("id", chunk.id),
                ("title", chunk.title),
                ("source", chunk.source),
                ("section", chunk.section),
                ("tokens", chunk.tokens),
            ]
        )
        write_text(chunks_dir / fname, f"{fm}\n\n{chunk.body.rstrip()}\n")
        total_tokens += chunk.tokens
        if chunk.heading_level and chunk.heading_level <= 3:
            outline.append(
                {
                    "level": chunk.heading_level,
                    "title": chunk.heading_title,
                    "anchor": chunk.id,
                    "file": fname,
                }
            )

    # de-duplicate consecutive outline entries (a chunk may repeat its heading)
    deduped: List[dict] = []
    for entry in outline:
        if deduped and deduped[-1]["title"] == entry["title"] and deduped[-1]["level"] == entry["level"]:
            continue
        deduped.append(entry)

    meta["stats"] = {
        "chunks": count_existing_chunks(chunks_dir),
        "tokens": (meta["stats"].get("tokens", 0) if append else 0) + total_tokens,
        "docs": len(meta["sources"]),
    }

    write_text(ir_dir / SOURCE_FILE, json.dumps(meta, ensure_ascii=False, indent=2))
    write_text(ir_dir / OUTLINE_FILE, json.dumps(deduped, ensure_ascii=False, indent=2))
    return meta["stats"]


def count_existing_chunks(chunks_dir: Path) -> int:
    if not chunks_dir.is_dir():
        return 0
    return len([p for p in chunks_dir.glob("*.md") if re.match(r"^\d{4}-", p.name)])


# ---------------------------------------------------------------------------
# IR -> consumers
# ---------------------------------------------------------------------------

def load_source_meta(ir_dir: Path) -> dict:
    return json.loads((Path(ir_dir) / SOURCE_FILE).read_text(encoding="utf-8"))


def load_outline(ir_dir: Path) -> List[dict]:
    path = Path(ir_dir) / OUTLINE_FILE
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def load_chunks(ir_dir: Path) -> List[Chunk]:
    chunks_dir = Path(ir_dir) / CHUNKS_DIR
    chunks: List[Chunk] = []
    if not chunks_dir.is_dir():
        return chunks
    for path in sorted(chunks_dir.glob("*.md")):
        fields, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        chunks.append(
            Chunk(
                id=fields.get("id", ""),
                title=fields.get("title", ""),
                source=fields.get("source", ""),
                section=fields.get("section", ""),
                tokens=int(fields.get("tokens", "0") or 0),
                body=body,
                file=path.name,
            )
        )
    return chunks


def group_chunks_by_top_section(chunks: List[Chunk]) -> "List[tuple[str, List[Chunk]]]":
    """Group chunks by their top-level section for skill references/full files."""
    groups: "Dict[str, List[Chunk]]" = {}
    order: List[str] = []
    for chunk in chunks:
        top = chunk.section.split(" > ")[0].strip() if chunk.section else "未分节"
        if not top:
            top = "未分节"
        if top not in groups:
            groups[top] = []
            order.append(top)
        groups[top].append(chunk)
    return [(name, groups[name]) for name in order]
