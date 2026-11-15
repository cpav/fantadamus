"""Invented pages in the real layouts, for the `mvp-sources` tests: Wikipedia's raw wikitext of a competition,
with each match in a `Football box` template. Clubs and players are invented; real pages can't be committed
to a public repository (design, testing strategy)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
UEFA_PROSE = (
    "Times are {{abbr|CET|Central European Time}}/{{abbr|CEST|Central European Summer Time}},"
    "{{efn|[[Central European Summer Time|CEST]] ([[UTC+02:00|UTC+2]]) for dates up to 24 October 2026, "
    "and [[Central European Time|CET]] ([[UTC+01:00|UTC+1]]) for dates thereafter.}} as listed by UEFA "
    "(local times, if different, are in parentheses).\n"
)
CUP_PROSE = (
    "Times up to 24 October 2026 and from 28 March 2027 are [[Central European Summer Time|CEST]] "
    "([[UTC+02:00|UTC+2]]). Times from 25 October 2026 to 27 March 2027 are [[Central European Time|CET]] "
    "([[UTC+01:00|UTC+1]]).\n"
)


@dataclass(frozen=True)
class Box:
    """One match as the page writes it: a side is a club's link, or any text (a placeholder, two clubs)."""

    team1: str
    team2: str
    date: str
    time: str
    score: str = ""


def link(name: str, target: str | None = None) -> str:
    """A club's link, `[[Target|Name]]` or `[[Name]]`."""
    return f"[[{target}|{name}]]" if target else f"[[{name}]]"


def start_date(day: dt.date) -> str:
    return f"{{{{Start date|{day.year}|{day.month}|{day.day}|df=y}}}}"


def plain_date(day: dt.date) -> str:
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def uefa_box(box: Box) -> str:
    """A league-phase match: the home side's flag after its name, the away side's before."""
    return (
        "{{#invoke:Football box|main\n"
        f"|date       = {box.date}\n"
        f"|time       = {box.time}\n"
        f"|team1      = {box.team1} {{{{fbaicon|ITA}}}}\n"
        f"|score      = {box.score}\n"
        f"|team2      = {{{{fbaicon|AUT}}}} {box.team2}\n"
        "|goals1     =\n"
        "*[[Anna Bianchi|Bianchi]] {{goal|21}}\n"
        "|goals2     =\n"
        "|stadium    = [[Stadio Invented]], [[Nowhere]]\n"
        "|attendance = 30,221<ref>{{cite web |url=https://example.org/report.pdf "
        "|title=Full Time Summary \u2013 A v B |publisher=Example |date=8 September 2026 "
        "|access-date=8 September 2026}}</ref>\n"
        "|referee    = [[Carlo Rossi]] ([[Invented Football Federation|Nowhere]])\n"
        "|report     = Report<ref>{{cite web |url=https://example.org/match/1/ |title=A vs. B}}</ref>\n"
        "}}\n----\n"
    )


def cup_box(box: Box, *, collapsible: bool = True) -> str:
    """A Coppa Italia match: a plain date, the zone after the time, the winner in bold, each side's tier."""
    head = "{{Football box collapsible\n|id = A v B\n" if collapsible else "{{Football box\n"
    return (
        f"{head}"
        f"|date = {box.date}\n"
        f"|time = {box.time}\n"
        f"|team1 = {box.team1}\n"
        f"|score = {box.score}\n"
        "|report = https://example.org/coppa-italia/match/abc/a-vs-b\n"
        f"|team2 = {box.team2}\n"
        "|goals1 =\n*[[Gabriele Verdi|Verdi]] {{goal|25}}\n"
        "|goals2 =\n*[[Marco Neri|Neri]] {{goal|39|pen.}}\n"
        "|stadium = [[Stadio Inventato]], [[Nessuno]]\n"
        "|attendance = 9,000\n"
        "|referee = [[Luca Gialli]]\n"
        "}}\n"
    )


def wiki_page(boxes: Sequence[str], prose: str = UEFA_PROSE) -> str:
    """A competition's raw wikitext: its lead, its prose on times, then its matchdays."""
    return (
        "{{Short description|An invented competition}}\n"
        "{{Infobox football tournament season\n| year = 2026\u201327\n| teams = 36\n}}\n"
        "The '''2026\u201327 league phase''' is invented for tests."
        "<ref>{{cite web |url=https://example.org/ |title=X}}</ref>\n\n"
        f"==Matches==\n{prose}\n===Matchday 1===\n" + "".join(boxes) + "\n==References==\n{{Reflist}}\n"
    )


def _club_card(number: int, club: str, columns: str) -> str:
    return (
        f'<div id="team-{number}" class="card team-card"><header class="team-info">'
        f'<figure class="team-badge"><img class="team-badge" alt="Stemma {club}" title="{club}" /></figure>'
        f'<span class="team-name">{club}</span></header><hr />'
        f'<div class="row row-responsive">{columns}</div></div>'
    )


def _page(title: str, cards: str) -> str:
    return (
        f"<html><head><title>{title}</title></head><body><main>"
        '<ul class="team-list"><li class="team-item">Alfa</li></ul>'
        f"{cards}"
        '<div class="match-pill"><span class="team-home">Alfa</span></div>'
        "</main></body></html>"
    )


def injured_page(
    clubs: Mapping[str, Sequence[tuple[str, str]]], *, title: str = "Infortunati Serie A"
) -> str:
    """Fantacalcio.it's injured page: a card per club, each player's name and a sentence on his injury."""
    cards = "".join(
        _club_card(
            number,
            club,
            '<div class="col"><ul class="unstyled">'
            + "".join(
                f'<li> <strong class="item-name">{name}</strong> '
                f'<div class="item-description"><p>{sentence}&nbsp;</p></div> </li>'
                for name, sentence in players
            )
            + "</ul></div>",
        )
        for number, (club, players) in enumerate(clubs.items(), start=1)
    )
    return _page(title, cards)


def _listed(label: str, heading: str, rows: str) -> str:
    body = f'<ul class="unstyled">{rows}</ul>' if rows else '<div class="empty-list-message">Nessuno</div>'
    return f'<div class="col"><header><strong class="label {label}">{heading}</strong></header>{body}</div>'


def suspended_page(
    clubs: Mapping[str, tuple[Sequence[tuple[str, str]], Sequence[str]]],
    *,
    title: str = "Squalificati e diffidati Serie A",
) -> str:
    """Fantacalcio.it's suspended-and-diffidati page: a card per club, who's banned with a sentence on the
    round he misses, and who's one booking from a ban; an empty list says "Nessuno"."""
    cards = "".join(
        _club_card(
            number,
            club,
            _listed(
                "label-danger",
                "Squalificati",
                "".join(
                    f'<li> <strong class="item-name">{name}</strong> '
                    f'<p class="item-description">{why}</p> </li>'
                    for name, why in banned
                ),
            )
            + _listed(
                "label-warn",
                "Diffidati",
                "".join(f'<li> <strong class="item-name">{name}</strong> </li>' for name in warned),
            ),
        )
        for number, (club, (banned, warned)) in enumerate(clubs.items(), start=1)
    )
    return _page(title, cards)


DESKS = ("Fantacalcio.it", "Roma", "Torino")
NOT_PUBLISHED = "\u2013"


@dataclass(frozen=True)
class Rated:
    """One player's row on the round ratings page: each desk's rating as the page shows it ("6,50", "s.v.", or
    a dash for a desk that hasn't published), and how he played."""

    surname: str
    initial: str
    role: str
    ratings: tuple[str, str, str] = ("6,00", "6,00", "6,00")
    came_on: int | None = None
    """Minutes played after coming on."""
    off_after: int | None = None
    unused: bool = False


def _rated_row(player: Rated) -> str:
    if player.unused:
        mark = '<span class="prb-non-entrato" title="Non è mai entrato in campo">non entrato</span>'
    elif player.came_on is not None:
        mark = (
            f'<span class="prb-segno" title="Entrato dalla panchina — {player.came_on} minuti giocati">'
            '<span class="fantaicon-t-shirt-in" aria-hidden="true"></span>'
            '<span class="sr-only">subentrato</span>'
            f'</span> <span class="prb-minuti" title="minuti giocati">{player.came_on}\'</span>'
        )
    elif player.off_after is not None:
        mark = (
            f'<span class="prb-segno" title="Sostituito dopo {player.off_after} minuti">'
            '<span class="fantaicon-t-shirt-out" aria-hidden="true"></span>'
            '<span class="sr-only">sostituito</span>'
            "</span>"
        )
    else:
        mark = ""
    cells = []
    for desk, shown in zip(DESKS, player.ratings, strict=True):
        if shown == NOT_PUBLISHED:
            title, kind = f"{desk} non ha pubblicato i voti di questa giornata", "muta"
        elif shown == "s.v.":
            title, kind = f"{desk}: senza voto", "fuori"
        else:
            title, kind = f"{desk}: voto senza bonus e malus", "probabile"
        cells.append(
            f'<td class="prb-cella prb-cella--{kind}"> <span data-toggle="tooltip" '
            f'data-original-title="{title}">{shown}</span> </td>'
        )
    row = "prb-riga--non-entrato" if player.unused else ""
    return (
        f'<tr class="{row}"> <th scope="row" class="prb-tabella__chi"> '
        f"<span class='role role-{player.role.lower()}'>{player.role}</span> "
        f'<span class="prb-nome">{player.surname}<small>{player.initial}</small></span> '
        f'<span class="prb-tabellino"> {mark} </span> </th> {"".join(cells)} </tr>'
    )


def _rated_table(caption: str, players: Sequence[Rated]) -> str:
    heads = "".join(
        f'<th scope="col" class="prb-tabella__fonte" title="{desk}">{desk[:3]}</th>' for desk in DESKS
    )
    return (
        f'<table class="prb-tabella"> <caption class="sr-only"> {caption}: voto di ogni redazione </caption> '
        f'<thead> <tr> <th scope="col" class="prb-tabella__chi">In campo</th> {heads} </tr> </thead> '
        f"<tbody> {''.join(_rated_row(player) for player in players)} </tbody> </table>"
    )


def ratings_page(round: int, matches: Sequence[tuple[str, str, Sequence[Rated], Sequence[Rated]]]) -> str:
    """Fantacalcio-Online's round ratings page: a tab per match, its clubs and score in the header, then a
    section per club with the players who started and those on the bench, each desk's rating in a column."""
    panes = []
    for number, (home, away, home_players, away_players) in enumerate(matches):
        sections = "".join(
            f'<section class="prb-squadra"> <h2 class="prb-squadra__nome">{club}</h2> '
            + _rated_table(
                "Scesi in campo",
                [player for player in players if player.came_on is None and not player.unused],
            )
            + _rated_table(
                "In panchina", [player for player in players if player.came_on is not None or player.unused]
            )
            + "</section>"
            for club, players in ((home, home_players), (away, away_players))
        )
        panes.append(
            f'<div class="tab-pane" id="lineup-{number}" role="tabpanel"> <header class="prb-incontro"> '
            f'<div class="prb-incontro__lato"> <a class="prb-incontro__nome" href="#">{home}</a> </div> '
            '<div class="prb-incontro__centro"> <p class="prb-incontro__punteggio">1<span>:</span>0</p> '
            '<p class="prb-incontro__stato prb-incontro__stato--chiusa">Terminata</p> '
            '<p class="prb-incontro__data">08/11/2026 20:45</p> </div> '
            '<div class="prb-incontro__lato prb-incontro__lato--ospite"> '
            f'<a class="prb-incontro__nome" href="#">'
            f'{away}</a> </div> </header> <div class="prb-squadre"> {sections} </div> </div>'
        )
    return (
        f"<html><head><title>Voti Fantacalcio Serie A 2026/2027 - {round}ª Giornata</title></head><body>"
        f'<div class="tab-content">{"".join(panes)}</div></body></html>'
    )


def season_ratings(round: int, read: int) -> dict[str, object]:
    """A round's ratings payload for the four invented clubs, 60 players a match, each rated by the three
    desks: as many rows as a real round gives, for timing a season (mvp-sources R7.2)."""
    matches = []
    for home, away in (("Alfa", "Beta"), ("Gamma", "Delta")):
        players = [
            {
                "club": club,
                "name": f"GIOCATORE{number} {club[0]}.",
                "role": "C",
                "ratings": [{"desk": desk, "rating": 6.0 + (number + read) % 3 / 2} for desk in DESKS],
            }
            for club in (home, away)
            for number in range(30)
        ]
        matches.append({"home": home, "away": away, "players": players})
    return {"round": round, "matches": matches}
