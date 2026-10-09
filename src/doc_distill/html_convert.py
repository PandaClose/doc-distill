"""HTML → Markdown conversion + link extraction, zero dependencies (stdlib
html.parser). Quality upgrade path: if ``trafilatura`` is installed it is
used for main-content extraction first (see extract/html_doc.py).
"""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from typing import List, Optional, Tuple

SKIP_TAGS = {"script", "style", "noscript", "svg", "iframe", "nav", "footer", "header", "aside", "form", "template"}
BLOCK_TAGS = {"p", "div", "section", "article", "main", "br", "hr", "table", "ul", "ol", "dl", "blockquote", "pre", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "figure", "figcaption"}

HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}


def decode_entities(text: str) -> str:
    return unescape(text).replace("\u00a0", " ").strip()


class _HTMLToMarkdown(HTMLParser):
    def __init__(self, base_url: str = "") -> None:
        super().__init__(convert_charrefs=False)
        self.base_url = base_url.rstrip("/")
        self.out: List[str] = []
        self.links: List[Tuple[str, str]] = []  # (href, text)
        self.title = ""
        self._skip_depth = 0
        self._heading: Optional[int] = None
        self._heading_buf: List[str] = []
        self._list_stack: List[str] = []  # "ul" | "ol"
        self._ol_counters: List[int] = []
        self._code_block = False
        self._code_lang = ""
        self._code_buf: List[str] = []
        self._href = ""
        self._link_buf: List[str] = []
        self._blockquote_depth = 0
        self._in_title = False
        self._title_buf: List[str] = []
        self._table_cell: List[str] = []
        self._table_row: List[str] = []
        self._in_table = False

    # -- helpers ---------------------------------------------------------
    def _emit(self, text: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self._title_buf.append(text)
            return
        if self._heading is not None:
            self._heading_buf.append(text)
            return
        if self._href:
            self._link_buf.append(text)
            return
        if self._code_block:
            self._code_buf.append(text)
            return
        self.out.append(text)

    def _absolute(self, href: str) -> str:
        if not href or href.startswith(("mailto:", "javascript:", "#")):
            return href
        if href.startswith(("http://", "https://")):
            return href
        if href.startswith("/"):
            return self.base_url + href
        return href  # relative; keep as-is

    # -- tag handlers ------------------------------------------------------
    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_d = dict(attrs)
        if tag in SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
            return
        if tag in HEADING_TAGS:
            self._heading = HEADING_TAGS[tag]
            self._heading_buf = []
            return
        if tag == "a":
            self._href = attrs_d.get("href", "")
            self._link_buf = []
            return
        if tag == "img":
            alt = decode_entities(attrs_d.get("alt", "") or "")
            src = self._absolute(attrs_d.get("src", "") or "")
            self._emit(f"![{alt}]({src})" if alt else f"!({src})")
            return
        if tag == "pre":
            self._code_block = True
            cls = attrs_d.get("class", "") or ""
            m = re.search(r"(?:language-|lang-)([\w+-]+)", cls)
            self._code_lang = m.group(1) if m else (attrs_d.get("data-lang", "") or "")
            self._code_buf = []
            return
        if tag == "code":
            if self._code_block:
                # <code> inside <pre> may carry the language hint
                cls = attrs_d.get("class", "") or ""
                m = re.search(r"(?:language-|lang-)([\w+-]+)", cls)
                if m and not self._code_lang:
                    self._code_lang = m.group(1)
            else:
                self._emit("`")
            return
        if tag == "blockquote":
            self._blockquote_depth += 1
            if self._blockquote_depth == 1:
                self.out.append("\n")
            return
        if tag in ("ul", "ol"):
            self._list_stack.append(tag)
            self._ol_counters.append(0)
            return
        if tag == "li":
            if self._list_stack:
                kind = self._list_stack[-1]
                if kind == "ol":
                    self._ol_counters[-1] += 1
                    self.out.append(f"\n{self._ol_counters[-1]}. ")
                else:
                    self.out.append("\n- ")
            return
        if tag == "br":
            self._emit("\n")
            return
        if tag == "hr":
            self.out.append("\n\n---\n\n")
            return
        if tag == "table":
            self._in_table = True
            self._table_row = []
            return
        if tag == "tr":
            self._table_row = []
            return
        if tag in ("td", "th"):
            self._table_cell = []
            return
        if tag == "strong" or tag == "b":
            self._emit("**")
            return
        if tag == "em" or tag == "i":
            self._emit("*")
            return
        if tag == "code":
            self._emit("`")
            return
        if tag in BLOCK_TAGS:
            self.out.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag == "title":
            self._in_title = False
            self.title = decode_entities("".join(self._title_buf))
            return
        if tag in HEADING_TAGS and self._heading is not None:
            text = decode_entities("".join(self._heading_buf))
            if text:
                self.out.append(f"\n\n{'#' * self._heading} {text}\n\n")
            self._heading = None
            return
        if tag == "a" and self._href:
            text = decode_entities("".join(self._link_buf))
            href = self._absolute(self._href)
            if text or href:
                self.links.append((self._href, text))
                if text and href.startswith("http"):
                    self.out.append(f"[{text}]({href})")
                else:
                    self.out.append(text)
            self._href = ""
            return
        if tag == "pre":
            self._code_block = False
            code = unescape("".join(self._code_buf)).strip("\n")
            self.out.append(f"\n\n```{self._code_lang}\n{code}\n```\n\n")
            self._code_buf = []
            return
        if tag == "blockquote":
            self._blockquote_depth = max(0, self._blockquote_depth - 1)
            return
        if tag in ("ul", "ol"):
            if self._list_stack:
                self._list_stack.pop()
                if self._ol_counters:
                    self._ol_counters.pop()
                self.out.append("\n")
            return
        if tag == "table":
            self._in_table = False
            return
        if tag == "tr" and self._table_row:
            self.out.append("\n|" + "|".join(self._table_row) + "|")
            if len(self.out) >= 1 and not getattr(self, "_table_header_done", False):
                pass
            self._table_row = []
            return
        if tag in ("td", "th"):
            self._table_row.append(decode_entities("".join(self._table_cell)).replace("|", "\\|"))
            self._table_cell = []
            return
        if tag in ("thead",):
            self.out.append("\n")
            return
        if tag == "strong" or tag == "b":
            self._emit("**")
            return
        if tag == "em" or tag == "i":
            self._emit("*")
            return
        if tag == "code":
            if not self._code_block:
                self._emit("`")
            return
        if tag in BLOCK_TAGS:
            self.out.append("\n")

    def handle_data(self, data: str) -> None:
        self._emit(data)

    def handle_entityref(self, name: str) -> None:
        self._emit(unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        self._emit(unescape(f"&#{name};"))

    # -- result -----------------------------------------------------------
    def markdown(self) -> str:
        text = "".join(self.out)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip() + "\n"


def html_to_markdown(html: str, base_url: str = "") -> Tuple[str, str, List[Tuple[str, str]]]:
    """Returns (markdown, title, links[(href, text)])."""
    parser = _HTMLToMarkdown(base_url=base_url)
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        pass  # lenient: broken markup still yields whatever was parsed
    return parser.markdown(), parser.title, parser.links
