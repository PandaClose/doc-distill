import unittest

import _bootstrap  # noqa: F401
from doc_distill.chunker import chunk_doc_units, render_block
from doc_distill.ir import Block, DocUnit


def md_unit(*blocks, title="doc"):
    return DocUnit(source="test.md", title=title, blocks=list(blocks))


H = lambda lvl, t: Block(kind="heading", level=lvl, text=t)
T = lambda t: Block(kind="text", text=t)
C = lambda t, lang="py": Block(kind="code", text=t, lang=lang)


class TestChunker(unittest.TestCase):
    def test_code_block_never_split(self):
        big_code = "\n".join(f"line_{i} = {i}" for i in range(200))  # > 512 tokens worth
        chunks = chunk_doc_units([md_unit(H(1, "ch"), C(big_code))], max_tokens=64)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].body.count("```"), 2)
        self.assertIn("line_0", chunks[0].body)
        self.assertIn("line_199", chunks[0].body)

    def test_heading_boundary_flushes(self):
        chunks = chunk_doc_units([md_unit(H(1, "a"), T("x " * 50), H(1, "b"), T("y " * 50))], max_tokens=512)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].heading_title, "a")
        self.assertEqual(chunks[1].heading_title, "b")

    def test_packing_respects_max_tokens(self):
        chunks = chunk_doc_units([md_unit(H(1, "t"), *[T("word " * 120) for _ in range(6)])], max_tokens=100)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(chunk.tokens, 160)  # some slack for carry-over

    def test_overlap_carries_context(self):
        chunks = chunk_doc_units([md_unit(H(1, "t"), *[T(f"para{i} " + "w " * 30) for i in range(4)])],
                                 max_tokens=60, overlap_tokens=40)
        if len(chunks) > 1:
            # second chunk should contain a carried paragraph from the first
            first_paras = chunks[0].body.split("\n\n")
            self.assertTrue(any(p in chunks[1].body for p in first_paras if p.strip()))

    def test_section_path(self):
        chunks = chunk_doc_units([md_unit(H(1, "ch1"), H(2, "sec"), T("content here"))])
        self.assertEqual(chunks[0].section, "doc > ch1 > sec")

    def test_render_code_fence(self):
        self.assertIn("```py", render_block(C("x=1", "py")))

    def test_start_index_offset(self):
        chunks = chunk_doc_units([md_unit(H(1, "a"), T("t"))], start_index=7)
        self.assertEqual(chunks[0].id, "0008")


if __name__ == "__main__":
    unittest.main()
