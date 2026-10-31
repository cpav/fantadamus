"""Readers: code that turns one specific page into facts (mvp-collect design C3.1). There is one, for
Fantacalcio-Online's round page; every other page is read by Claude through `read_page` (C3.2)."""

from __future__ import annotations


class UnreadablePageError(Exception):
    """The page lacks what the reader relies on, so nothing from it may be stored (R3.4)."""
