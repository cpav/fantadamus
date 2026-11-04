"""Synthetic pages with the real pages' structure (class names, captions, attributes) and invented clubs and
players, for the reader's tests. Real pages can't be committed to a public repository (mvp-collect design)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from tests.xy_harness import WORDS

OUTLETS = ("Fantacalcio.it", "Gazzetta", "SOS Fanta", "Sky")


def squad(club: str) -> list[str]:
    """Fourteen invented players, `<Club> Uno` to `<Club> Quattordici`: 11 starters, 2 on the bench, 1 out."""
    return [f"{club} {word}" for word in WORDS]


def fco_name(name: str) -> str:
    """Fantacalcio-Online writes the surname in capitals, then the initial: `NOVE<small>A</small>`."""
    first, surname = name.split(" ", 1)
    return f"{surname.upper()}<small>{first[0]}</small>"


@dataclass
class FcoMatch:
    home: str
    away: str
    kickoff: str = "31/10/2026 15:00"
    odds: tuple[str, str, str] | None = ("2,10", "3,30", "3,60")  # None: no odds shown yet
    over3: str = "53%"
    updated: str = "quote aggiornate il 30 ottobre alle 18:13"
    percents: Mapping[str, tuple[int | None, ...]] = field(default_factory=dict)  # None: the outlet's dash
    confirmed: bool = False  # True: the 11 probable starters are the real ones, all marked
    marked: tuple[str, ...] = ()  # players marked as real starters, whichever table lists them
    lineups: bool = True  # False: the teams' sections are there, their tables not published yet
    reversed: bool = False  # True: each table lists its players in the opposite order
    pending: tuple[str, ...] = ()  # outlets that haven't published: a note on the column, dashes in its cells


def _role(letter: str) -> str:
    return f"<span class='role role-{letter.lower()}'>{letter}</span>"


def _fco_row(name: str, percents: tuple[int | None, ...], confirmed: bool) -> str:
    cells = "".join(
        f'<td class="prb-cella"><span data-original-title="Probabilita&#039; x">{p}%</span></td>'
        if p is not None
        else '<td class="prb-cella prb-cella--vuota">\u2013</td>'
        for p in percents
    )
    given = [p for p in percents if p is not None]
    average = round(sum(given) / len(given))
    return (
        f'<tr><th scope="row" class="prb-tabella__chi">{_role("A")} '
        f'<span class="prb-nome">{fco_name(name)}</span></th>{cells}'
        f'<td class="prb-cella prb-cella--media"><span>{average}%</span></td>'
        f'<td class="prb-cella prb-tabella__conferma">{"&#10003;" if confirmed else " "}</td></tr>'
    )


PENDING_NOTE = " \u2014 non ha ancora pubblicato per questa giornata"  # as on the live page, 2026-11-03


def _fco_table(caption: str, rows: str, pending: tuple[str, ...] = ()) -> str:
    sources = "".join(
        f'<th scope="col" class="prb-tabella__fonte " '
        f'title="{outlet}{PENDING_NOTE if outlet in pending else ""}">{outlet[:3]}</th>'
        for outlet in OUTLETS
    )
    average = (
        '<th scope="col" class="prb-tabella__fonte prb-tabella__fonte--media " '
        'title="Tutte le fonti">Media*</th>'
    )
    confirmed = (
        '<th scope="col" class="prb-tabella__fonte prb-tabella__conferma">'
        '<span class="sr-only">Confermato</span><span aria-hidden="true">Uff.</span></th>'
    )
    return (
        f'<table class="prb-tabella"><caption class="sr-only">{caption}</caption>'
        f'<thead><tr><th scope="col">Titolare</th>{sources}{average}{confirmed}</tr></thead>'
        f"<tbody>{rows}</tbody></table>"
    )


def _fco_team(club: str, side: str, match: FcoMatch) -> str:
    heading = f'<section class="prb-squadra prb-squadra--{side}"><h2 class="prb-squadra__nome">{club}</h2>'
    if not match.lineups:
        return f"{heading}</section>"
    players = squad(club)

    def shown(percents: tuple[int | None, ...]) -> tuple[int | None, ...]:
        return tuple(
            None if outlet in match.pending else p for outlet, p in zip(OUTLETS, percents, strict=True)
        )

    order = reversed if match.reversed else iter
    starters = "".join(
        _fco_row(
            name, shown(match.percents.get(name, (90, 90, 95, 90))), match.confirmed or name in match.marked
        )
        for name in order(players[:11])
    )
    bench = "".join(
        _fco_row(name, shown(match.percents.get(name, (10, 30, 5, 30))), name in match.marked)
        for name in order(players[11:13])
    )
    out = (
        '<div class="prb-fuori"><p class="prb-fuori__titolo">Indisponibili</p>'
        f'<ul class="prb-fuori__elenco"><li class="prb-fuori__riga">{_role("A")} '
        f'<span class="prb-nome">{fco_name(players[13])}</span> '
        '<span class="fco-etichetta">Infortunato</span></li></ul></div>'
    )
    return (
        f"{heading}{_fco_table('Probabili titolari: percentuale per redazione', starters, match.pending)}"
        f"{_fco_table('Probabile panchina: percentuale per redazione', bench, match.pending)}{out}</section>"
    )


def _fco_header(match: FcoMatch) -> str:
    return (
        '<header class="prb-incontro"><div class="prb-incontro__lato">'
        f'<span class="prb-incontro__nome">{match.home}</span></div>'
        '<div class="prb-incontro__centro"><p class="prb-incontro__punteggio">0<span>:</span>0</p>'
        '<p class="prb-incontro__stato">Non iniziata</p>'
        f'<p class="prb-incontro__data">{match.kickoff}</p></div>'
        '<div class="prb-incontro__lato prb-incontro__lato--ospite">'
        f'<span class="prb-incontro__nome">{match.away}</span></div></header>'
    )


def _fco_summary(match: FcoMatch) -> str:
    labels = (f"1 · {match.home}", "X · pareggio", f"2 · {match.away}")
    boxes = "".join(
        f'<div class="stp-qbox"><div class="stp-qlab">{label}</div><div class="stp-qval">{odd}</div></div>'
        for label, odd in zip(labels, match.odds or (), strict=False)
    )
    return (
        f'<div class="prb-sintesi"><div class="prb-sintesi__quote">{boxes}</div>'
        '<ul class="prb-sintesi__mercati">'
        f"<li><span>Gol attesi</span> <b>3 o più</b> <i>{match.over3}</i></li>"
        f'<li class="prb-sintesi__ora">{match.updated}</li></ul></div>'
    )


def fco_round_page(*matches: FcoMatch, round: int | None = 10) -> str:
    """Fantacalcio-Online's round page: its title naming the round, the match tabs, one tab pane per match."""
    tabs = "".join(
        f'<li class="nav-item"><a class="prb-partita nav-link" href="#lineup-{i}">{m.home} - {m.away}</a>'
        "</li>"
        for i, m in enumerate(matches)
    )
    panes = "".join(
        f'<div class="tab-pane" id="lineup-{i}">{_fco_header(m)}{_fco_summary(m)}'
        f'<div class="prb-squadre">{_fco_team(m.home, "home", m)}{_fco_team(m.away, "away", m)}</div></div>'
        for i, m in enumerate(matches)
    )
    title = f"<title>Probabili Formazioni Serie A 2026/2027 - {round}ª Giornata</title>" if round else ""
    return (
        f"<html><head>{title}</head><body>"
        f'<ul class="nav">{tabs}</ul><div class="tab-content">{panes}</div></body></html>'
    )


STATS_TITLE = "Statistiche Fantacalcio Serie A - Stagione 2026/27"
STATS_COLUMNS = (
    ("sq", "Squadra", "Sq"),
    ("pg", "Partite a voto", "PV"),
    ("mv", "Media voto", "MV"),
    ("mfv", "Fantamedia", "FM"),
    ("gol", "Gol segnati", "Gol"),
    ("gs", "Gol subiti", "GS"),
    ("rig", "Rigori segnati / tirati", "Rig"),
    ("rp", "Rigori parati", "RP"),
    ("ass", "Assist", "Ass"),
    ("amm", "Ammonizioni", "Amm"),
    ("esp", "Espulsioni", "Esp"),
)
_STATS_CELL_CLASS = {
    "sq": "player-team",
    "pg": "player-match-playeds",
    "mv": "player-grade-avg",
    "mfv": "player-fanta-grade-avg",
    "ass": "player-assists",
    "amm": "player-yellows",
    "esp": "player-reds",
}


def _decimal(value: float | None) -> str:
    """The page's decimals: a comma, and `0,0` without a rating."""
    return "0,0" if value is None else f"{value:g}".replace(".", ",")


def stats_cells(row: Mapping[str, Any]) -> dict[str, str]:
    """A player's cells as the statistics page writes them, from his figures as the contract has them. The
    fantamedia, penalties saved and red cards are made up: nothing reads them."""
    return {
        "sq": row["club"][:3].upper(),
        "pg": str(row["rated_appearances"]),
        "mv": _decimal(row["average_rating"]),
        "mfv": "7,5",
        "gol": str(row["goals"]),
        "gs": str(row.get("goals_conceded") or 0),
        "rig": f"{row['penalties_scored']} / {row['penalties_taken']}",
        "rp": "1",
        "ass": str(row["assists"]),
        "amm": str(row["yellow_cards"]),
        "esp": "1",
    }


def _stats_row(index: int, row: Mapping[str, Any], cells: Mapping[str, str]) -> str:
    club, mantra = row["club"].lower(), [row["mantra_role"].lower()] if row["mantra_role"] else []
    if row["role"] == "A" and mantra != ["a"]:
        mantra.append("a")  # forwards often have a second Mantra role; the first is the one read
    slug = row["name"].lower().replace(" ", "-")
    roles = "".join(
        f'<span class="role role-mantra" data-value="{code}" title="{code}"></span>' for code in mantra
    )
    tds = "".join(
        f'<td class="{_STATS_CELL_CLASS.get(key, "player-scoreds")}" data-col-key="{key}"> {text} </td>'
        for key, text in cells.items()
    )
    return (
        f'<tr class="player-row" data-index="{index}" data-filter-keywords="{row["name"]}" '
        f'data-filter-role-classic="{row["role"].lower()}" data-filter-role-mantra="{"|".join(mantra)}">'
        '<th class="player-championship"> </th>'
        '<th class="player-role-classic player-role">'
        f'<span class="role" data-value="{row["role"].lower()}"></span></th>'
        '<th class="player-role-mantra player-role">'
        f'<div class="pill role-pill theme-dark">{roles}</div></th>'
        '<th class="player-name"><a class="player-name player-link" '
        f'href="https://www.fantacalcio.it/serie-a/squadre/{club}/{slug}/{row["player_id"]}" target="_self">'
        f'<span>{row["name"]}</span></a></th>{tds}<td class="tail"> </td></tr>'
    )


def stats_page(
    rows: Sequence[Mapping[str, Any]],
    *,
    title: str = STATS_TITLE,
    columns: Sequence[tuple[str, str, str]] = STATS_COLUMNS,
    cells: Mapping[int, Mapping[str, str | None]] | None = None,
) -> str:
    """Fantacalcio.it's statistics page: its title, then `table#stats`, with a header naming each column and
    one row per player. `cells` rewrites a player's cells by ID, and None leaves that cell out."""
    changed = cells or {}
    keys = [key for key, _, _ in columns]
    head = "".join(
        f'<th data-col-key="{key}" data-sorter-type="numeric"><a href="#" title="{name}">{short}</a></th>'
        for key, name, short in columns
    )
    body = ""
    for index, row in enumerate(rows):
        written: dict[str, str | None] = {**stats_cells(row), **changed.get(row["player_id"], {})}
        kept = {key: text for key in keys if (text := written.get(key)) is not None}
        body += _stats_row(index, row, kept)
    return (
        f"<html><head><title>{title}</title></head><body><main>"
        '<table id="stats" class="pills-table sticky-header-col"><thead class="compact"><tr>'
        '<th class="sticky-header player-championship"><a class="overflow-label" href="#">Calciatore</a></th>'
        '<th class="sticky-header player-role player-role-classic"></th>'
        '<th class="sticky-header player-role player-role-mantra"></th>'
        '<th class="sticky-header player-name"></th>'
        f'{head}<th class="tail"></th></tr></thead><tbody>{body}</tbody></table></main></body></html>'
    )
