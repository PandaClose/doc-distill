"""Documentation-site crawler: same-domain BFS with depth/page caps.

Concepts ported from Skill_Seekers' doc_scraper, rebuilt on stdlib urllib +
our own HTML converter. Politeness: sequential fetch, per-host delay, cap on
pages, skips binary/asset links and login-ish anchors.
"""

from __future__ import annotations

import re
import time
from collections import deque
from html.parser import HTMLParser
from pathlib import Path
from typing import Deque, List, Set, Tuple
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from ..html_convert import html_to_markdown
from ..ir import DocUnit
from .html_doc import extract_html_text
from .local import fetch_url

SKIP_EXT = re.compile(
    r"\.(png|jpe?g|gif|svg|ico|css|js|json|xml|zip|gz|tar|pdf|epub|mp4|mp3|webm|woff2?|ttf|eot|exe|dmg|whl|jar)$",
    re.I,
)
SKIP_ANCHOR = re.compile(r"(login|signin|signup|register|edit|delete|/blog/|/news/|twitter\.com|x\.com|github\.com)", re.I)


def _normalize(url: str, base: str = "") -> str:
    url = urljoin(base, url) if base else url
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def _same_site(url: str, root: str) -> bool:
    return urlsplit(url).netloc == urlsplit(root).netloc


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href", "")
            if href and not href.startswith(("#", "mailto:", "javascript:")):
                self.links.append(href)


def crawl_website(
    start_url: str,
    max_pages: int = 20,
    max_depth: int = 2,
    delay: float = 0.5,
) -> List[DocUnit]:
    start = _normalize(start_url)
    seen: Set[str] = set([start])
    queue: Deque[Tuple[str, int]] = deque([(start, 0)])
    units: List[DocUnit] = []

    while queue and len(units) < max_pages:
        url, depth = queue.popleft()
        try:
            raw = fetch_url(url)
            html = raw.decode("utf-8", errors="replace")
        except Exception as exc:
            print(f"[doc-distill] 跳过 {url}: {exc}")
            continue
        if "<html" not in html.lower() and "<body" not in html.lower():
            continue  # not an html page

        unit = extract_html_text(html, source=url, base_url=url)
        if unit.blocks:
            units.append(unit)

        if depth < max_depth:
            parser = _LinkParser()
            try:
                parser.feed(html)
            except Exception:
                pass
            for href in parser.links:
                link = _normalize(href, url)
                if (
                    link not in seen
                    and _same_site(link, start)
                    and not SKIP_EXT.search(link)
                    and not SKIP_ANCHOR.search(link)
                ):
                    seen.add(link)
                    queue.append((link, depth + 1))

        time.sleep(delay)

    return units


def extract_website(url: str, max_pages: int = 20, max_depth: int = 2) -> List[DocUnit]:
    units = crawl_website(url, max_pages=max_pages, max_depth=max_depth)
    host = urlsplit(url).netloc
    for unit in units:
        if not unit.title or unit.title == "untitled":
            unit.title = unit.source
    print(f"[doc-distill] website 抓取完成：{len(units)} 页（站点 {host}）")
    return units


def _unused(*_args) -> None:  # keep imports referenced
    _ = (urljoin, Path, DocUnit, html_to_markdown)
