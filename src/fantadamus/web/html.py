"""A small HTML tree for the readers (mvp-collect design C2), built with the standard library's `html.parser`.

Enough to read a page by its structure (tags, classes, captions, title attributes) rather than its raw text:
void tags close themselves, an unclosed tag ends with its parent, and script and style contents are skipped.
"""

from __future__ import annotations

from collections.abc import Iterator
from html.parser import HTMLParser

_VOID = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)
_SKIPPED = frozenset({"script", "style", "template"})


class Element:
    def __init__(self, tag: str, attrs: dict[str, str], parent: Element | None) -> None:
        self.tag, self.attrs, self.parent = tag, attrs, parent
        self.children: list[Element | str] = []

    def attr(self, name: str) -> str | None:
        return self.attrs.get(name)

    def has_class(self, name: str) -> bool:
        return name in self.attrs.get("class", "").split()

    def descendants(self) -> Iterator[Element]:
        """Every element below this one, in document order. A stack, not nested generators, so each element
        is visited once however deep the page nests."""
        stack = [child for child in reversed(self.children) if isinstance(child, Element)]
        while stack:
            element = stack.pop()
            yield element
            stack.extend(child for child in reversed(element.children) if isinstance(child, Element))

    def _matching(self, tag: str | None, class_: str | None) -> Iterator[Element]:
        return (
            element
            for element in self.descendants()
            if (tag is None or element.tag == tag) and (class_ is None or element.has_class(class_))
        )

    def find_all(self, tag: str | None = None, class_: str | None = None) -> list[Element]:
        """Every element below this one with the tag and the class, in document order."""
        return list(self._matching(tag, class_))

    def find(self, tag: str | None = None, class_: str | None = None) -> Element | None:
        """The first such element, found without walking the rest."""
        return next(self._matching(tag, class_), None)

    def text(self) -> str:
        """All the text below this element, with whitespace collapsed to single spaces."""
        pieces: list[str] = []

        def walk(element: Element) -> None:
            for child in element.children:
                if isinstance(child, str):
                    pieces.append(child)
                else:
                    walk(child)

        walk(self)
        return " ".join(" ".join(pieces).split())


class _Builder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Element("#document", {}, None)
        self._current = self.root
        self._skipping: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._skipping:
            return
        if tag in _SKIPPED:
            self._skipping = tag
            return
        element = Element(tag, {name: value or "" for name, value in attrs}, self._current)
        self._current.children.append(element)
        if tag not in _VOID:
            self._current = element

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if not self._skipping and tag not in _SKIPPED:
            self._current.children.append(
                Element(tag, {name: value or "" for name, value in attrs}, self._current)
            )

    def handle_endtag(self, tag: str) -> None:
        if self._skipping:
            if tag == self._skipping:
                self._skipping = None
            return
        open_element: Element | None = self._current
        while open_element is not None and open_element.tag != tag:
            open_element = open_element.parent
        if open_element is not None and open_element.parent is not None:  # a stray end tag is ignored
            self._current = open_element.parent

    def handle_data(self, data: str) -> None:
        if not self._skipping:
            self._current.children.append(data)


def parse(page: str) -> Element:
    """The page's tree; its root is a `#document` element."""
    builder = _Builder()
    builder.feed(page)
    builder.close()
    return builder.root
