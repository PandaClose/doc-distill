"""Binary document formats: PDF / EPUB / DOCX / RTF / MOBI-Calibre.

- EPUB & DOCX are parsed with the stdlib (they are zip+XML containers).
- PDF prefers ``pypdf`` (extra ``[pdf]``); ``docling`` (extra ``[pdf-pro]``)
  gives structure-aware markdown for technical books when installed.
- RTF needs ``striprtf`` (extra ``[rtf]``).
- MOBI/AZW needs Calibre's ``ebook-convert`` on PATH.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import zipfile
from html import unescape
from pathlib import Path
from typing import List, Optional
from xml.etree import ElementTree

from ..html_convert import html_to_markdown
from ..ir import Block, DocUnit
from .local import markdown_text_to_unit
from .local import missing_dep_error

# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

HEADING_PATTERNS = [
    re.compile(r"^第\s*[一二三四五六七八九十百\d]+\s*[章讲部分篇回]\b"),
    re.compile(r"^(?:Chapter|CHAPTER)\s+\d+"),
    re.compile(r"^\d{1,2}(?:\.\d{1,2}){0,2}\s+\S.{0,60}$"),
]


def extract_pdf(path: Path) -> List[DocUnit]:
    try:
        import pypdf  # type: ignore
    except ImportError:
        try:
            return _extract_pdf_docling(path)
        except SystemExit:
            raise missing_dep_error("PDF", "pdf", "（技术书推荐 pip install 'doc-distill[pdf-pro]' 用 docling 保留表格与代码块）")

    if shutil.which("docling"):  # structure-aware when available
        try:
            return _extract_pdf_docling(path)
        except SystemExit:
            pass

    reader = pypdf.PdfReader(str(path))
    blocks: List[Block] = []
    title = ""
    for pageno, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        if not title and text:
            title = text.splitlines()[0][:80]
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if len(line) < 80 and any(p.match(line) for p in HEADING_PATTERNS):
                level = 1 if (re.match(r"^第|^Chapter|^CHAPTER|^\d{1,2}\s+\S", line) and "." not in line.split(" ")[0]) else 2
                blocks.append(Block(kind="heading", level=level, text=line))
            else:
                blocks.append(Block(kind="text", text=line))
        if pageno % 25 == 0:
            blocks.append(Block(kind="text", text=f"<!-- page {pageno} -->"))
    if not blocks:
        print("[doc-distill] 警告：PDF 未提取到文本（可能是扫描版）。请先 OCR：ocrmypdf input.pdf output.pdf")
    return [DocUnit(source=str(path), title=title or path.stem, blocks=blocks)]


def _extract_pdf_docling(path: Path) -> List[DocUnit]:
    try:
        from docling.document_converter import DocumentConverter  # type: ignore
    except ImportError:
        raise missing_dep_error("技术书 PDF（docling）", "pdf-pro")
    result = DocumentConverter().convert(str(path))
    markdown = result.document.export_to_markdown()
    return [markdown_text_to_unit(markdown, source=str(path))]


# ---------------------------------------------------------------------------
# EPUB (stdlib: zip + OPF spine)
# ---------------------------------------------------------------------------

def extract_epub(path: Path) -> List[DocUnit]:
    units: List[DocUnit] = []
    with zipfile.ZipFile(path) as zf:
        container = ElementTree.fromstring(zf.read("META-INF/container.xml"))
        rootfile = None
        for el in container.iter():
            if el.tag.endswith("}rootfile") or el.tag == "rootfile":
                rootfile = el
                break
        if rootfile is None:
            raise SystemExit(f"[doc-distill] EPUB 缺少 container.xml 的 rootfile：{path}")
        opf_path = rootfile.get("full-path", "")
        opf_dir = opf_path.rsplit("/", 1)[0] if "/" in opf_path else ""

        def resolve(href: str) -> str:
            return f"{opf_dir}/{href}" if opf_dir else href

        opf = ElementTree.fromstring(zf.read(opf_path))
        ns = {"o": "http://www.idpf.org/2007/opf", "dc": "http://purl.org/dc/elements/1.1/"}
        title = ""
        for el in opf.iter():
            if el.tag.endswith("}title"):
                title = unescape(el.text or "").strip()
                break

        manifest = {}
        for item in opf.iter():
            if item.tag.endswith("}item"):
                manifest[item.get("id", "")] = (item.get("href", ""), item.get("media-type", ""))

        spine_refs = []
        for itemref in opf.iter():
            if itemref.tag.endswith("}itemref"):
                spine_refs.append(itemref.get("idref", ""))

        for idx, idref in enumerate(spine_refs, start=1):
            href, mtype = manifest.get(idref, ("", ""))
            if not href or ("html" not in mtype and not href.lower().endswith((".xhtml", ".html", ".htm"))):
                continue
            try:
                raw = zf.read(resolve(href)).decode("utf-8", errors="replace")
            except KeyError:
                continue
            md, doc_title, _ = html_to_markdown(raw)
            if not md.strip():
                continue
            unit = markdown_text_to_unit(md, source=str(path))
            unit.title = doc_title or unit.title or f"chapter {idx:02d}"
            unit.source = f"{path}#{href}"
            units.append(unit)

    if units and title:
        units[0].title = units[0].title or title
    return units or [DocUnit(source=str(path), title=path.stem, blocks=[])]


# ---------------------------------------------------------------------------
# DOCX (stdlib: zip + document.xml)
# ---------------------------------------------------------------------------

_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_docx(path: Path) -> List[DocUnit]:
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    blocks: List[Block] = []
    title = ""

    for para in root.iter(f"{_W_NS}p"):
        style = ""
        ppr = para.find(f"{_W_NS}pPr")
        if ppr is not None:
            pstyle = ppr.find(f"{_W_NS}pStyle")
            if pstyle is not None:
                style = pstyle.get(f"{_W_NS}val", "")
        texts = [t.text or "" for t in para.iter(f"{_W_NS}t")]
        text = unescape("".join(texts)).strip()
        if not text:
            continue
        m = re.match(r"[Hh]eading(\d)", style)
        if m:
            level = min(6, int(m.group(1)))
            if level == 1 and not title:
                title = text
            blocks.append(Block(kind="heading", level=level, text=text))
        else:
            blocks.append(Block(kind="text", text=text))

    return [DocUnit(source=str(path), title=title or path.stem, blocks=blocks)]


# ---------------------------------------------------------------------------
# RTF / Calibre
# ---------------------------------------------------------------------------

def extract_rtf(path: Path) -> List[DocUnit]:
    try:
        from striprtf.striprtf import rtf_to_text  # type: ignore
    except ImportError:
        raise missing_dep_error("RTF", "rtf")
    text = rtf_to_text(path.read_text(encoding="utf-8", errors="replace"))
    return [markdown_text_to_unit(text, source=str(path))]


def extract_calibre(path: Path) -> List[DocUnit]:
    binary = shutil.which("ebook-convert")
    if not binary:
        raise SystemExit(
            "[doc-distill] 处理 MOBI/AZW 需要 Calibre：请先安装 https://calibre-ebook.com\n"
            "  并确保 `ebook-convert` 在 PATH 中；或先手动转换为 EPUB 再输入。"
        )
    with tempfile.TemporaryDirectory() as tmp:
        out_txt = Path(tmp) / "out.txt"
        subprocess.run([binary, str(path), str(out_txt)], check=True, capture_output=True, timeout=600)
        text = out_txt.read_text(encoding="utf-8", errors="replace")
    return [markdown_text_to_unit(text, source=str(path))]
