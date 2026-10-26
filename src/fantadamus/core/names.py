"""Name matching that ignores case, accents, spacing and punctuation (R1.2)."""

from __future__ import annotations

import unicodedata


def name_key(text: str) -> str:
    """NFKD without combining marks, case-folded, letters and digits only: `A.C. Milan` → `acmilan`."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed.casefold() if c.isalnum() and not unicodedata.combining(c))
