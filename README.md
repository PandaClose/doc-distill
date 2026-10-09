# doc-distill

**English** | [简体中文](README.zh-CN.md)

**Distill any document asset into a manual-style Agent Skill + RAG corpus.**

One book, a documentation site, a GitHub repo, or an llms.txt manifest — a single command turns it into two layers of output:

1. **Manual-style skill**: `SKILL.md` (when to use + chapter map + distilled sections) + `references/full/` (on-demand original-text chunks). Drop it into `~/.agents/skills/` and use it in Claude Code / ZCode / Codex, or any Agent Skills-compatible runtime.
2. **RAG corpus**: dependency-free JSONL / Markdown packages, each record carrying `id / text / metadata`, ready for any embedding + vector-store pipeline.

```bash
doc-distill run my-book.epub -o out/
# out/
# ├── <slug>/               ← manual-style skill (chapter map + original chunks + three distillation placeholders)
# ├── <slug>-rag/chunks.jsonl
# └── <slug>-rag/full.md
```

> **Note**: CLI messages and the bundled distillation spec (`SKILL.md`, `references/`) are currently written in Chinese. English localization is on the roadmap — PRs welcome.

## Design Philosophy

**Zero core dependencies, zero API keys, zero Docker.** Extraction and export run as deterministic local Python; distillation is delegated to your host agent (Claude Code / ZCode / …) following the built-in spec — the model you already pay for *is* the distillation engine, so no extra API setup is needed.

Architecturally, everything flows through a **unified intermediate representation (IR)**:

```
input (book/site/repo/…) → extractors (plugins) → IR (chunks+outline+meta) → distill (host agent, optional) → exporters (plugins)
```

Sources × distillation × export are fully decoupled; incremental fold-in merges at the IR level only.

## Supported Inputs

| Input | Dependencies | Notes |
|---|---|---|
| Markdown / plain text / RST / AsciiDoc | none | setext headings, fenced code blocks |
| HTML (file/URL) | none (`[web]` optional, better quality) | built-in zero-dependency HTML→MD converter |
| EPUB / DOCX | none | stdlib zip+XML container parsing |
| PDF | `[pdf]` (pypdf) | for technical books prefer `[pdf-pro]` (docling — preserves table/code structure) |
| RTF | `[rtf]` | |
| MOBI / AZW / AZW3 | system [Calibre](https://calibre-ebook.com) | calls `ebook-convert` |
| Doc sites | none | same-domain BFS crawl (default 20 pages / depth 2); **probes `/llms.txt` first and uses it when available** |
| GitHub repos | none (git not required) | codeload tarball; docs in full, code truncated to overviews |
| Local doc dirs / globs | none | multiple inputs merge into one volume |

Scanned PDFs need OCR first: `ocrmypdf in.pdf out.pdf`.

## Installation

```bash
# PyPI (once published)
pipx install doc-distill[all]        # or: uv tool install

# From source
git clone https://github.com/PandaClose/doc-distill.git && cd doc-distill
pip install -e .[all]
```

## Usage

```bash
doc-distill detect <input...>            # identify source type
doc-distill run <input...> -o out/       # all-in-one: extract → IR → export (no distillation, instantly usable)
doc-distill extract <input...> -o ir/    # build IR only (for host-agent distillation)
doc-distill export ir/ --targets skill-manual,rag-jsonl -o out/
doc-distill extract <new-material> -o ir/ --append   # incremental fold-in
doc-distill validate out/<slug> --strict       # QA gate (fails while distillation placeholders remain)
```

### Use as a skill (recommended)

Register this repository root as a skill — it is itself a `SKILL.md` distillation spec:

```bash
npx skills add PandaClose/doc-distill       # or clone manually into ~/.agents/skills/doc-distill
```

Then, inside Claude Code / ZCode, just say *"turn xx.pdf into a skill"* — the host agent follows `SKILL.md` + `references/distill-spec.md` through the full **extract → read-through → distill → validate** pipeline.

**How the two modes relate**: `run` produces an "index + full-text lookup" skill that works immediately; once the host agent fills in the three distillation sections (core frameworks / patterns & techniques / decision quick-reference) it upgrades into a full manual — a passing `validate --strict` means distillation is complete.

## RAG Corpus Format

Each line of `chunks.jsonl` is one JSON record:

```json
{"id": "0012", "text": "…", "metadata": {"source": "…", "section": "Ch.3 > 3.2", "title": "…", "tokens": 487, "type": "epub", "asset": "book title"}}
```

Semantic chunking guarantees: code blocks are never split, paragraph boundaries are respected, and chunks run ~512 tokens with 50 overlap. Vector-store exports (faiss/chroma etc.) are on the M4 roadmap.

## Roadmap

- [x] **M1** unified IR + 7 local formats + skill-manual/router + rag-jsonl/markdown + skill form
- [x] **M2** doc-site / llms.txt / GitHub adapters + source auto-detection
- [ ] **M3** API distillation engine (CI / headless scenarios, optional) + stronger output-consistency checks
- [ ] **M4** video transcripts / Notion / Confluence / vector-store extras

## Relationship to its predecessors

This project merges [book-to-skill](https://github.com/virgiliojr94/book-to-skill) (extract/distill separation, manual spec, optional-dependency philosophy) with [Skill_Seekers](https://github.com/yusufkaraaslan/Skill_Seekers) (multi-source adapters, semantic chunking, multi-target export). See [NOTICE.md](NOTICE.md). Both are MIT.

## Disclaimer

This tool contains and distributes no copyrighted content. Distilled outputs are derivative notes for personal study — please do not redistribute them.
