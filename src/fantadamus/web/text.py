"""A fetched page's readable text, for Claude to extract facts from (mvp-collect design C3.2; R3.2).

It reads `main` when the page has one, otherwise `body`, and leaves out menus, footers, side panels, forms and
graphics. Headings become `#` lines, paragraphs and list items lines of their own, and table rows their cells
joined by ` | `. A link with text shows its address only when `follow` accepts it, so a squad page lists its
profile links and none of the menus. `parts` splits a long text between lines, for one tool result each.
"""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urldefrag, urljoin

from fantadamus.web.html import Element

PART = 40_000  # characters a part: about 10,000 tokens
_SKIPPED = frozenset({"nav", "footer", "aside", "form", "svg", "iframe", "noscript", "button", "select"})
_HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
_BLOCKS = frozenset(
    {
        "address",
        "article",
        "blockquote",
        "br",
        "caption",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "figure",
        "header",
        "hr",
        "main",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tbody",
        "tfoot",
        "thead",
        "ul",
    }
)


class _Writer:
    def __init__(self, url: str, follow: Callable[[str], bool]) -> None:
        self.url, self.follow = url, follow
        self.lines: list[str] = []
        self.pending: list[str] = []

    def flush(self, prefix: str = "") -> None:
        text = " ".join("".join(self.pending).split())
        self.pending.clear()
        if text:
            self.lines.append(prefix + text)

    def address(self, link: Element) -> str | None:
        href = link.attr("href")
        if not href:
            return None
        address = urldefrag(urljoin(self.url, href)).url
        return address if self.follow(address) else None

    def walk(self, element: Element) -> None:
        for child in element.children:
            if isinstance(child, str):
                self.pending.append(child)
            elif child.tag in _SKIPPED:
                continue
            elif child.tag == "tr":
                self.row(child)
            elif child.tag in _HEADINGS or child.tag == "li":
                self.flush()
                self.walk(child)
                self.flush("#" * _HEADINGS[child.tag] + " " if child.tag in _HEADINGS else "- ")
            elif child.tag == "a":
                before = len(self.pending)
                self.walk(child)
                has_text = any(piece.strip() for piece in self.pending[before:])
                if has_text and (address := self.address(child)) is not None:
                    self.pending.append(f" ({address})")
            elif child.tag in _BLOCKS:
                self.flush()
                self.walk(child)
                self.flush()
            else:
                self.walk(child)

    def row(self, row: Element) -> None:
        self.flush()
        cells = []
        for cell in row.children:
            if isinstance(cell, Element) and cell.tag in {"td", "th"}:
                inner = _Writer(self.url, self.follow)
                inner.walk(cell)
                inner.flush()
                cells.append(" ".join(inner.lines))
        if any(cells):
            self.lines.append(" | ".join(cells))


def page_text(tree: Element, url: str, follow: Callable[[str], bool]) -> str:
    """The page's readable text; `url` resolves its links, and `follow` says which links to show."""
    writer = _Writer(url, follow)
    writer.walk(tree.find("main") or tree.find("body") or tree)
    writer.flush()
    return "\n".join(writer.lines)


def parts(text: str, size: int = PART) -> list[str]:
    """The text in parts of at most `size` characters, split between lines; a longer line is split too."""
    pieces = [
        line[start : start + size] for line in text.split("\n") for start in range(0, len(line) or 1, size)
    ]
    split: list[str] = []
    current: list[str] = []
    length = 0
    for piece in pieces:
        if current and length + 1 + len(piece) > size:
            split.append("\n".join(current))
            current, length = [], 0
        length += len(piece) + (1 if current else 0)
        current.append(piece)
    split.append("\n".join(current))
    return split
