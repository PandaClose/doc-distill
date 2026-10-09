"""Semantic chunker — ports Skill_Seekers' RAGChunker rules onto doc-distill IR:

- code blocks are atomic (never split mid-code)
- paragraphs/list items are packing units (semantic boundaries)
- heading boundaries flush chunks (section-aligned retrieval)
- greedy packing to ``max_tokens`` with ``overlap_tokens`` carry-over
- rich metadata (source, section path, tokens) attached per chunk
"""

from __future__ import annotations

from typing import List, Optional

from .ir import Block, Chunk, DocUnit
from .utils import estimate_tokens

PACKABLE = {"text", "quote", "list"}


def render_block(block: Block) -> str:
    if block.kind == "heading":
        return f"{'#' * max(1, block.level)} {block.text}"
    if block.kind == "code":
        fence = "```"
        return f"{fence}{block.lang}\n{block.text}\n{fence}" if block.text else f"{fence}\n\n{fence}"
    if block.kind == "quote":
        return "\n".join(f"> {line}" for line in block.text.splitlines())
    if block.kind == "list":
        return "\n".join(f"- {line}" for line in block.text.splitlines())
    return block.text


class _Section:
    """Heading stack for one document."""

    def __init__(self, doc_title: str) -> None:
        self.doc_title = doc_title
        self.stack: "List[tuple[int, str]]" = []  # (level, title)

    def push(self, level: int, title: str) -> None:
        while self.stack and self.stack[-1][0] >= level:
            self.stack.pop()
        self.stack.append((level, title))

    @property
    def path(self) -> str:
        if not self.stack:
            return self.doc_title
        return " > ".join([self.doc_title] + [t for _, t in self.stack])

    @property
    def top(self) -> str:
        return self.stack[0][1] if self.stack else self.doc_title

    def governing(self) -> "Optional[tuple[int, str]]":
        """Shallowest heading at level <= 3, else the deepest."""
        for level, title in self.stack:
            if level <= 3:
                return (level, title)
        return self.stack[-1] if self.stack else None


def chunk_doc_units(
    doc_units: List[DocUnit],
    max_tokens: int = 512,
    overlap_tokens: int = 50,
    start_index: int = 0,
) -> List[Chunk]:
    chunks: List[Chunk] = []
    index = start_index

    for unit in doc_units:
        section = _Section(unit.title)
        pending: List[str] = []  # rendered blocks of the chunk being built
        pending_tokens = 0
        pending_has_content = False  # non-heading content present?
        chunk_heading: "Optional[tuple[int, str]]" = None
        first_heading_in_chunk = ""

        def flush() -> None:
            nonlocal index, pending, pending_tokens, chunk_heading, first_heading_in_chunk, pending_has_content
            if not pending:
                return
            index += 1
            body = "\n\n".join(pending).strip()
            gov = chunk_heading or section.governing()
            level, gov_title = gov if gov else (0, section.path or unit.title)
            title = first_heading_in_chunk or gov_title or unit.title
            chunks.append(
                Chunk(
                    id=f"{index:04d}",
                    title=title,
                    source=unit.source,
                    section=section.path,
                    tokens=estimate_tokens(body),
                    body=body,
                    heading_level=level,
                    heading_title=gov_title,
                )
            )
            # carry-over for overlap
            carry: List[str] = []
            carried = 0
            for block_text in reversed(pending):
                t = estimate_tokens(block_text)
                if carried + t > overlap_tokens or block_text.startswith("```"):
                    break
                carry.insert(0, block_text)
                carried += t
            pending = list(carry)
            pending_tokens = carried
            pending_has_content = False
            chunk_heading = None
            first_heading_in_chunk = ""

        for block in unit.blocks:
            if block.kind == "heading":
                level = max(1, min(6, block.level or 1))
                section.push(level, block.text)
                # a new top/mid heading starts a new chunk (section-aligned)
                if pending and level <= 2:
                    flush()
                if not chunk_heading and level <= 3:
                    chunk_heading = (level, block.text)
                if not first_heading_in_chunk:
                    first_heading_in_chunk = block.text
                pending.append(render_block(block))
                pending_tokens += estimate_tokens(block.text)
                continue

            rendered = render_block(block)
            block_tokens = estimate_tokens(rendered)

            if block.kind == "code" and block_tokens > max_tokens:
                # atomic oversize code block: flush real content first; a
                # heading-only prefix merges into the code chunk
                if pending_has_content:
                    flush()
                pending.append(rendered)
                pending_tokens += block_tokens
                pending_has_content = True
                flush()
                continue

            if pending_tokens + block_tokens > max_tokens and pending:
                flush()
                # do not carry a code block as overlap context
                if pending and pending[0].startswith("```"):
                    pending, pending_tokens = [], 0

            pending.append(rendered)
            pending_tokens += block_tokens
            pending_has_content = True

        flush()

    return chunks
