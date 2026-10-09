import unittest

import _bootstrap  # noqa: F401
from doc_distill.utils import estimate_tokens, parse_frontmatter, render_frontmatter, stable_slug, slugify, guess_title_from_source


class TestSlug(unittest.TestCase):
    def test_ascii(self):
        self.assertEqual(slugify("The Pragmatic Programmer!"), "the-pragmatic-programmer")

    def test_cjk_falls_back_with_hash(self):
        slug = stable_slug("代码整洁之道")
        self.assertTrue(slug.startswith("doc-"))
        self.assertNotEqual(slug, stable_slug("别的书"))

    def test_mixed(self):
        self.assertEqual(slugify("Clean Code 第1章"), "clean-code-1")

    def test_length_cap(self):
        self.assertLessEqual(len(slugify("a" * 100)), 40)


class TestTokens(unittest.TestCase):
    def test_cjk_counts_more(self):
        self.assertGreater(estimate_tokens("这是一段中文内容" * 10), estimate_tokens("ascii words " * 10))

    def test_empty(self):
        self.assertEqual(estimate_tokens(""), 0)


class TestFrontmatter(unittest.TestCase):
    def test_roundtrip(self):
        fm = render_frontmatter([("name", "my-skill"), ("description", 'has: colon "quotes"'), ("tokens", "512")])
        fields, body = parse_frontmatter(fm + "\n\nbody text\n")
        self.assertEqual(fields["name"], "my-skill")
        self.assertEqual(fields["tokens"], "512")
        self.assertIn("colon", fields["description"])
        self.assertEqual(body.strip(), "body text")

    def test_no_frontmatter(self):
        fields, body = parse_frontmatter("just text")
        self.assertEqual(fields, {})
        self.assertEqual(body, "just text")


class TestTitle(unittest.TestCase):
    def test_from_url(self):
        self.assertEqual(guess_title_from_source("https://example.com/docs/getting-started/"), "getting started")

    def test_from_path(self):
        self.assertEqual(guess_title_from_source("/a/b/my_book.pdf"), "my book")


if __name__ == "__main__":
    unittest.main()
