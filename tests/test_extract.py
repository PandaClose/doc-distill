import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401
from doc_distill.detect import detect_source, expand_inputs
from doc_distill.extract.local import extract_docs_dir, extract_text_file
from doc_distill.html_convert import html_to_markdown
from doc_distill.extract.llms_txt import parse_llms_txt


class TestMarkdownExtract(unittest.TestCase):
    def test_blocks(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "book.md"
            p.write_text(
                "# 我的第一章\n\n段落一。\n\n- 甲\n- 乙\n\n```python\nprint(1)\n```\n\n## 小节\n\n> 引用\n",
                encoding="utf-8",
            )
            unit = extract_text_file(p)
        self.assertEqual(unit.title, "我的第一章")
        kinds = [b.kind for b in unit.blocks]
        self.assertIn("heading", kinds)
        self.assertIn("code", kinds)
        self.assertIn("list", kinds)
        self.assertIn("quote", kinds)
        headings = [b for b in unit.blocks if b.kind == "heading"]
        self.assertEqual([h.text for h in headings], ["我的第一章", "小节"])
        self.assertEqual(headings[0].level, 1)
        self.assertEqual(headings[1].level, 2)

    def test_setext_heading(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.md"
            p.write_text("标题行\n=====\n\n正文\n", encoding="utf-8")
            unit = extract_text_file(p)
        self.assertEqual(unit.title, "标题行")
        self.assertEqual(unit.blocks[0].kind, "heading")
        self.assertEqual(unit.blocks[0].level, 1)


class TestDocsDir(unittest.TestCase):
    def test_walk_and_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "docs"
            (root / "sub").mkdir(parents=True)
            (root / "intro.md").write_text("# Intro\n\nhi\n", encoding="utf-8")
            (root / "sub" / "deep.md").write_text("# Deep\n\nho\n", encoding="utf-8")
            (root / "skip.bin").write_bytes(b"\x00\x01")
            units = extract_docs_dir(root)
        names = [u.title for u in units]
        lowered = [n.lower() for n in names]
        self.assertEqual(len(units), 2)
        self.assertTrue(any("docs/intro" in n for n in lowered))
        self.assertTrue(any("deep" in n for n in lowered))


class TestDetect(unittest.TestCase):
    def test_file_types(self):
        self.assertEqual(detect_source("x/y.md")["kind"], "text")
        self.assertEqual(detect_source("x/y.epub")["kind"], "epub")
        self.assertEqual(detect_source("x/y.docx")["kind"], "docx")
        self.assertEqual(detect_source("x/y.exe")["kind"], "unsupported")

    def test_urls(self):
        self.assertEqual(detect_source("https://github.com/a/b")["kind"], "github")
        self.assertEqual(detect_source("https://x.com/llms.txt")["kind"], "llms_txt")
        self.assertEqual(detect_source("https://docs.example.com/guide/")["kind"], "website")
        self.assertEqual(detect_source("https://x.com/manual.pdf")["kind"], "pdf")

    def test_glob_expansion(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(3):
                (Path(tmp) / f"f{i}.md").write_text("# t\n", encoding="utf-8")
            expanded = expand_inputs([str(Path(tmp) / "f*.md")])
        self.assertEqual(len(expanded), 3)


class TestHtmlConvert(unittest.TestCase):
    def test_headings_and_code(self):
        html = "<html><head><title>T</title></head><body><h1>Head</h1><p>para <b>bold</b></p><pre><code class=\"language-js\">let x=1</code></pre></body></html>"
        md, title, links = html_to_markdown(html)
        self.assertEqual(title, "T")
        self.assertIn("# Head", md)
        self.assertIn("**bold**", md)
        self.assertIn("```js", md)
        self.assertIn("let x=1", md)

    def test_script_skipped_and_links(self):
        html = "<body><script>evil()</script><a href='/docs/x'>Doc X</a><a href='https://k.im'>K</a></body>"
        md, _, links = html_to_markdown(html, base_url="https://example.com")
        self.assertNotIn("evil", md)
        self.assertIn(("/docs/x", "Doc X"), links)
        self.assertIn("[Doc X](https://example.com/docs/x)", md)


class TestLlmsTxt(unittest.TestCase):
    def test_parse(self):
        text = "# Title\n\n## Docs\n\n- [Guide](/guide.md): the guide\n- [API](https://a.com/api)\n* [Ref](ref.md)\n"
        entries = parse_llms_txt(text)
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0], ("Guide", "/guide.md"))


if __name__ == "__main__":
    unittest.main()
