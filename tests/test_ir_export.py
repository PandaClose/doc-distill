import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import _bootstrap  # noqa: F401
from doc_distill.extract.documents import extract_docx, extract_epub
from doc_distill.ir import load_chunks, load_outline, load_source_meta, write_ir
from doc_distill.extract.local import markdown_text_to_unit


MINIMAL_DOCX_XML = """<?xml version="1.0"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body>
  <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Chapter One</w:t></w:r></w:p>
  <w:p><w:r><w:t>Hello docx world.</w:t></w:r></w:p>
  <w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>Section</w:t></w:r></w:p>
  <w:p><w:r><w:t>More text here.</w:t></w:r></w:p>
</w:body>
</w:document>"""


def make_docx(path: Path):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", MINIMAL_DOCX_XML)


MINIMAL_OPF = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>My Epub</dc:title></metadata>
  <manifest>
    <item id="c1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
    <item id="c2" href="ch2.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="c1"/><itemref idref="c2"/></spine>
</package>"""

CONTAINER = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""


def make_epub(path: Path):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("META-INF/container.xml", CONTAINER)
        zf.writestr("content.opf", MINIMAL_OPF)
        zf.writestr("ch1.xhtml", "<html><body><h1>First</h1><p>alpha</p></body></html>")
        zf.writestr("ch2.xhtml", "<html><body><h1>Second</h1><p>beta</p></body></html>")


class TestDocuments(unittest.TestCase):
    def test_docx(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.docx"
            make_docx(p)
            units = extract_docx(p)
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0].title, "Chapter One")
        headings = [b for b in units[0].blocks if b.kind == "heading"]
        self.assertEqual([h.level for h in headings], [1, 2])

    def test_epub(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.epub"
            make_epub(p)
            units = extract_epub(p)
        self.assertEqual(len(units), 2)
        self.assertEqual(units[0].title, "First")
        self.assertEqual(units[1].title, "Second")
        self.assertIn("beta", " ".join(b.text for b in units[1].blocks))


class TestIRRoundtrip(unittest.TestCase):
    def test_write_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            ir = Path(tmp) / "ir"
            units = [markdown_text_to_unit("# 一章\n\n内容A\n\n## 节\n\n内容B\n", source="a.md")]
            stats = write_ir(ir, slug="demo", title="Demo", source_type="text", doc_units=units)
            self.assertGreater(stats["chunks"], 0)
            meta = load_source_meta(ir)
            self.assertEqual(meta["slug"], "demo")
            outline = load_outline(ir)
            self.assertTrue(any("一章" in e["title"] for e in outline))
            chunks = load_chunks(ir)
            self.assertTrue(all(c.body.strip() for c in chunks))
            self.assertTrue(all(c.id for c in chunks))

    def test_append_fold_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            ir = Path(tmp) / "ir"
            u1 = [markdown_text_to_unit("# A\n\ntext one\n", source="1.md")]
            write_ir(ir, slug="x", title="X", source_type="text", doc_units=u1)
            u2 = [markdown_text_to_unit("# B\n\ntext two\n", source="2.md")]
            stats = write_ir(ir, slug="x", title="X", source_type="text", doc_units=u2, append=True)
            chunks = load_chunks(ir)
            ids = [c.id for c in chunks]
            self.assertEqual(len(ids), len(set(ids)))  # no id collision
            self.assertIn("B", " ".join(c.section for c in chunks))
            meta = load_source_meta(ir)
            self.assertEqual(len(meta["sources"]), 2)


class TestExporters(unittest.TestCase):
    def test_all_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            units = [markdown_text_to_unit("# Book\n\n## Alpha\n\n" + "内容 " * 40 + "\n\n## Beta\n\n代码 `\n", source="s.md")]
            ir = tmp / "ir"
            write_ir(ir, slug="book-slug", title="Book", source_type="text", doc_units=units)
            from doc_distill.export import run_exporters

            results = run_exporters(ir, tmp / "out", ["skill-manual", "skill-router", "rag-jsonl", "rag-markdown"])
            self.assertEqual(len(results), 4)

            # manual skill
            manual = tmp / "out" / "book-slug" / "SKILL.md"
            self.assertTrue(manual.exists())
            text = manual.read_text(encoding="utf-8")
            self.assertIn("name: book-slug", text)
            self.assertIn("description:", text)
            self.assertIn("章节地图", text)
            self.assertIn("TODO(distill)", text)
            full_dir = tmp / "out" / "book-slug" / "references" / "full"
            self.assertTrue(any(full_dir.glob("*.md")))

            # rag jsonl valid
            rows = [json.loads(l) for l in (tmp / "out" / "book-slug-rag" / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertTrue(rows)
            self.assertIn("id", rows[0])
            self.assertIn("metadata", rows[0])
            self.assertIn("text", rows[0])

            # validate passes non-strict, fails strict
            from doc_distill.validate import validate_skill

            non_strict = validate_skill(tmp / "out" / "book-slug")
            hard = [p for p in non_strict if not p.startswith("提示")]
            self.assertEqual(hard, [])
            strict = validate_skill(tmp / "out" / "book-slug", strict=True)
            self.assertTrue(any("占位" in p for p in strict))

    def test_unknown_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            from doc_distill.export import run_exporters

            with self.assertRaises(SystemExit):
                run_exporters(Path(tmp), Path(tmp), ["nope"])


if __name__ == "__main__":
    unittest.main()
