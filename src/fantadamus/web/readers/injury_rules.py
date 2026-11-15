"""Rules that turn an injury or ban sentence from Fantacalcio.it into facts (mvp-sources design C4; R3.1; open
point 1, approved 2026-11-12). The sentence itself is never kept: what the rules can't place shows as
"detail on the page", with the link.

- **The kind**, the first that fits, in this order: surgery, a fracture, a ligament, a muscle, a knock,
  illness, an injury with the national team, else "other". "La sosta per le Nazionali", the international
  break, isn't an injury with the national team.
- **The body part**, the most precise that fits: the hamstring and the adductors before the thigh.
- **The return**: a month's part (early, mid, the second half, late) or the whole month, after a word for
  coming back ("rientro dalla fine di novembre", "recuperabile da dicembre"); else a stop of about so long,
  counted from the date the sentence gives or else from the read ("stop di circa sei settimane"); else "to be
  assessed" ("da valutare"). A month before the read's is next year's; a stop that has already run its
  course gives no return.
"""

from __future__ import annotations

import calendar
import datetime as dt
import re
from dataclasses import dataclass

from fantadamus.contracts.xy.unavailable import BodyPart, InjuryKind

MONTHS = {
    name: number
    for number, name in enumerate(
        (
            "gennaio",
            "febbraio",
            "marzo",
            "aprile",
            "maggio",
            "giugno",
            "luglio",
            "agosto",
            "settembre",
            "ottobre",
            "novembre",
            "dicembre",
        ),
        start=1,
    )
}
NUMBERS = {
    "un": 1,
    "uno": 1,
    "una": 1,
    "due": 2,
    "tre": 3,
    "quattro": 4,
    "cinque": 5,
    "sei": 6,
    "sette": 7,
    "otto": 8,
    "nove": 9,
    "dieci": 10,
    "quindici": 15,
    "venti": 20,
}
_KINDS: tuple[tuple[InjuryKind, str], ...] = (
    ("surgery", r"operat[oaie]|operarsi|intervento|chirurg"),
    ("fracture", r"frattur"),
    ("ligament", r"legament|crociat"),
    ("muscle", r"lesion|distrazion|stiramen|elongazion|affaticamen|muscol"),
    ("knock", r"contusion|trauma|botta"),
    ("illness", r"febbr|influenz|virus|viral"),
    ("national team", r"\b(?:in|con la|dalla|nella) nazionale\b"),
)
_PARTS: tuple[tuple[BodyPart, str], ...] = (
    ("hamstring", r"bicipite femorale|flessor|semitendinos|semimembranos|ischiocrural"),
    ("adductor", r"addutt"),
    ("calf", r"polpacci|soleo|gemell"),
    ("thigh", r"coscia|quadricipit"),
    ("knee", r"ginocchi|menisc|rotul"),
    ("ankle", r"caviglia"),
    ("foot", r"piede|metatars|tallon"),
    ("shoulder", r"spalla"),
    ("back", r"schiena|lombar"),
    ("other", r"\bmano\b|polso|costol|testa|naso|zigom|anca|pube|pubalg|inguin|collo|gomito|dito|falange"),
)
_MONTH = "|".join(MONTHS)
_PART_OF = r"(?:(?P<part>inizio|seconda met[aà]|met[aà]|fine)\s+(?:di\s+)?)?"
_BACK = re.compile(
    r"(?:rientr\w*|recuperabil\w*|torn\w*|ritorn\w*|rived\w*|ipotesi|convocabil\w*|arruolabil\w*|disponibil\w*)"
    r"[^.;]{0,40}?\b(?:da|dal|dalla|dall['\u2019])\s*" + _PART_OF + rf"(?P<month>{_MONTH})\b",
    re.IGNORECASE,
)
_STOP = re.compile(
    rf"stop di circa (?P<count>\d+|{'|'.join(NUMBERS)}) (?P<unit>giorn[oi]|settiman[ae]|mes[ei])",
    re.IGNORECASE,
)
_DATED = re.compile(rf"\b(?:il|dal|del|dallo)\s+(?P<day>\d{{1,2}})\s+(?P<month>{_MONTH})\b", re.IGNORECASE)
_ASSESS = re.compile(r"da valutare", re.IGNORECASE)
_ROUND = re.compile(r"\b(\d{1,2})\s*[aª°]\b")


@dataclass(frozen=True)
class Back:
    back_from: dt.date | None = None
    back_until: dt.date | None = None
    to_be_assessed: bool = False


def kind_of(sentence: str) -> InjuryKind:
    text = sentence.lower()
    return next((kind for kind, words in _KINDS if re.search(words, text)), "other")


def body_part_of(sentence: str) -> BodyPart | None:
    text = sentence.lower()
    return next((part for part, words in _PARTS if re.search(words, text)), None)


def back_of(sentence: str, today: dt.date) -> Back:
    """When he's expected back, as of `today`, the date the page was read (in Italy)."""
    if window := _BACK.search(sentence):
        month = MONTHS[window["month"].lower()]
        year = today.year + 1 if month < today.month else today.year
        last = calendar.monthrange(year, month)[1]
        first, end = _part(window["part"], last)
        return Back(dt.date(year, month, first), dt.date(year, month, end))
    if stop := _STOP.search(sentence):
        count = stop["count"].lower()
        amount = int(count) if count.isdigit() else NUMBERS[count]
        unit = stop["unit"].lower()
        days = amount * (1 if unit.startswith("giorn") else 7 if unit.startswith("settiman") else 30)
        dated = _DATED.search(sentence)
        start = _date_before(int(dated["day"]), MONTHS[dated["month"].lower()], today) if dated else today
        back = start + dt.timedelta(days=days) if start is not None else None
        return Back(back, back) if back is not None and back >= today else Back()
    return Back(to_be_assessed=bool(_ASSESS.search(sentence)))


def banned_rounds(sentence: str) -> list[int]:
    """The rounds a ban sentence names ("squalificato nella 12a giornata"); none when it gives a count of
    them."""
    if "giornat" not in sentence.lower():
        return []
    return sorted({int(number) for number in _ROUND.findall(sentence) if 1 <= int(number) <= 38})


def _part(part: str | None, last: int) -> tuple[int, int]:
    """The days of a month's part: early is the 1st to the 10th, mid the 11th to the 20th, the second half
    from the 16th, late from the 21st; no part is the whole month."""
    match " ".join((part or "").lower().split()).replace("meta", "metà"):
        case "inizio":
            return 1, 10
        case "metà":
            return 11, 20
        case "seconda metà":
            return 16, last
        case "fine":
            return 21, last
        case _:
            return 1, last


def _date_before(day: int, month: int, today: dt.date) -> dt.date | None:
    """A date the sentence gives, in the past: this year's, or last year's if it would be after `today`."""
    for year in (today.year, today.year - 1):
        try:
            when = dt.date(year, month, day)
        except ValueError:  # no such day
            return None
        if when <= today:
            return when
    return None
