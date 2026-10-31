"""`read_page`: Fantadamus fetches a page on the reading list and hands Claude its text, and Claude submits
the facts it finds (mvp-collect design C3.2; R3.2, R3.3).

Only an address that a listed page or pattern matches is fetched, with a placeholder such as `{club}` matching
one path segment; anything else is refused before any request. Fetching follows the polite fetcher's rules
(C1), and nothing is stored here: the text exists only in the tool result (R2.4).
"""

from __future__ import annotations

import datetime as dt
import functools
import re
from dataclasses import dataclass

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel

from fantadamus.mcp.tools.compare import ReadingItem
from fantadamus.web import text as page
from fantadamus.web.fetch import Fetcher, FetchError
from fantadamus.web.html import parse

_PLACEHOLDER = re.compile(r"\{[a-z_]+\}")


class NotOnReadingListError(Exception):
    """The address matches no listed page or pattern, so it isn't fetched."""


class NoSuchPartError(Exception):
    """The page's text has fewer parts than the one asked for."""


class PageFact(BaseModel):
    fact: str
    submit_tool: str


class PageRead(BaseModel):
    """`part` of `parts` of a page's text, and its facts: submit each with `url` and `fetched_at`."""

    url: str
    fetched_at: dt.datetime
    facts: list[PageFact]
    part: int
    parts: int
    text: str


@functools.cache
def _address(entry: str) -> re.Pattern[str]:
    return re.compile("[^/?#]+".join(re.escape(part) for part in _PLACEHOLDER.split(entry)))


@dataclass(frozen=True)
class PageReader:
    reading: dict[str, ReadingItem]
    fetcher: Fetcher

    def facts_at(self, url: str) -> list[PageFact]:
        """The facts whose pages or patterns match `url`."""
        return [
            PageFact(fact=fact, submit_tool=item.submit_tool)
            for fact, item in self.reading.items()
            if any(_address(entry).fullmatch(url) for entry in item.pages + item.patterns)
        ]

    def listed(self, url: str) -> bool:
        return bool(self.facts_at(url))

    def read(self, url: str, part: int = 1) -> PageRead:
        facts = self.facts_at(url)
        if not facts:
            raise NotOnReadingListError(
                f"{url} is not on the reading list: read only the pages a refresh plan lists, or the links "
                "a listed page shows with their address"
            )
        fetched = self.fetcher.fetch(url)
        split = page.parts(page.page_text(parse(fetched.text), fetched.url, self.listed), page.PART)
        if not 1 <= part <= len(split):
            raise NoSuchPartError(f"{url} has {len(split)} parts; ask for part 1 to {len(split)}")
        text = split[part - 1]
        if part < len(split):
            text += f"\n[Part {part} of {len(split)}: call read_page with part={part + 1} for the rest.]"
        return PageRead(
            url=fetched.url,
            fetched_at=fetched.fetched_at,
            facts=facts,
            part=part,
            parts=len(split),
            text=text,
        )


def register(server: MCPServer, reader: PageReader) -> None:
    """Add `read_page` to `server`."""

    @server.tool(
        description="Fetch a page on the reading list and return its text, with the facts it carries and "
        "the submit tool for each. Read the facts from the text, then submit each with `url` as source_url "
        "and `fetched_at` as captured_at. A long page comes in parts: read the next with `part`. Only listed "
        "pages and the links shown with their address can be read; a page that can't be fetched says why, so "
        "move to the next listed page."
    )
    def read_page(url: str, part: int = 1) -> PageRead:
        try:
            return reader.read(url, part)
        except (NotOnReadingListError, NoSuchPartError, FetchError) as error:
            raise ToolError(str(error)) from error
