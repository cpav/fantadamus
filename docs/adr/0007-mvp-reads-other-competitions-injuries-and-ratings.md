# ADR-0007: In the MVP, Fantadamus also reads the other competitions' fixtures, the injury and suspension pages and the round ratings

- **Status:** Accepted by the owner, 2026-11-12 ("Approve all", with the `mvp-sources` design)
- **Deciders:** the owner
- **Amends:** ADR-0006 (Fantadamus fetches the round's facts itself): five more pages, on the same rules
- **Specs affected:** `mvp-sources`
- **Note, 2026-11-13:** Wikipedia's robots.txt turns away `/w/`, where the MediaWiki API is, so our fetcher would refuse it.
  The same raw wikitext is served at `/wiki/{title}?action=raw`, which robots.txt allows; the pages are read there
  (checked with the fetcher's own rules: all four pages returned their wikitext, every match in a `Football box`).

## Context

`mvp-sources` needs three new facts: every Serie A club's matches in the other competitions, so that a match card can
say how rested each side is; why a player is out and for how long, and who's one booking from a ban; and each
round's ratings from three desks, as evidence for the rating constants and for the raters' bias. The owner chose on
2026-11-12 to read them from pages now ("Wikipedia now"), with API-Football's licensed feed in v1.

Every candidate page sits on a site the owner has already approved (`docs/source-registry.md`). The official sources
were checked first and can't be used: UEFA's General Terms (clause 6.2) forbid robots, spiders and scripts that collect
its content, and Lega Serie A's terms forbid extracting it. A site whose terms forbid our use is dropped, as Sky and Goal
were in October.

## Options

| Option | For | Against |
|---|---|---|
| A. Claude reads the new pages through `read_page` and submits the facts (ADR-0005) | No new code that fetches | One more chore for every player, every round; the injury prose and the rating tables are long to read by hand |
| B. Fantadamus reads them itself, under ADR-0006's rules, with Claude as the fallback | One read serves both players; deterministic and testable | More readers to keep up when a page's layout changes |
| C. API-Football's free tier now | Licensed; every competition and injuries in one feed | An account and a key in the owner's name; approved for v1 only |

## Decision

**Option B.** Fantadamus reads these pages itself, with its polite fetcher (robots.txt honoured, one request a second
per host, an identifying user agent), and each has a switch that hands it back to Claude through `read_page`:

| Page | Route | robots.txt (read 2026-11-12) | Data | Cadence |
|---|---|---|---|---|
| Wikipedia's 2026–27 Champions League, Europa League and Conference League league-phase pages, and the 2026–27 Coppa Italia page, read as raw wikitext at `/wiki/{title}?action=raw` (see the note) | CC BY-SA, with attribution | Allowed under `/wiki/`; `/w/`, the API's, is not | Each match as a `Football box` template: its date, its kickoff in Italian time, both clubs and the score; matches to come already listed | Weekly, and daily in a week with a match |
| Fantacalcio.it's injured page, `/infortunati-serie-a` | The terms risk the owner accepted for the MVP (ADR-0004) | Allowed | In the HTML, by club: each player with a sentence on his injury and his expected return | Daily; twice a day in the last 48 hours before a round |
| Fantacalcio.it's suspended-and-diffidati page, `/squalificati-e-diffidati-campionato-serie-a` | As above | Allowed | In the HTML, by club: who's banned and for which round, and who's one booking from a ban | As above |
| Fantacalcio-Online's round ratings page, `/it/serie-a/2026-2027/voti/{n}-giornata` | Personal use with attribution, per its terms | Allowed for everyone; its header warns that Cloudflare may block AI agents at the edge, which the fetcher treats as blocked | In the HTML: each player's base rating from three desks (Fantacalcio.it, Roma, Torino), and when he came on or off | The morning after each round, and when a round is scored |

The pages' text is never stored: each reader keeps structured facts only, with the page's address (ADR-0005,
guardrail 4). The injury sentences become a kind, a body part and a return window; what a reader can't place is kept as
"detail on the page", with the link.

## Consequences

- **Easier:** rest days and injury detail on every card and outlook, at no cost to the players; the rating constants
  get their evidence; the raters can be compared.
- **Harder:** four more readers to keep up. Wikipedia's pages are written by volunteers: a kickoff may be missing or
  late, and a knockout round's page appears only after its draw, so its title is added to the reading list then.
- **To do:** the source registry and the reading list record the pages; each reader is tested on invented pages with
  the same layout, since the real ones can't be committed.

## Sources

- [UEFA's General Terms and Conditions](https://www.uefa.com/termsconditions/), clause 6.2: no automated collection
- [Fantacalcio-Online's robots.txt](https://www.fantacalcio-online.com/robots.txt): no blocking, by design
- [2026–27 UEFA Champions League league phase](https://en.wikipedia.org/wiki/2026%E2%80%9327_UEFA_Champions_League_league_phase), its raw wikitext at `/wiki/{title}?action=raw`
- [2026–27 Coppa Italia](https://en.wikipedia.org/wiki/2026%E2%80%9327_Coppa_Italia): dated matches; later rounds "TBD"
- `docs/source-registry.md`: the terms read on 2026-10-24, and the checks of 2026-11-12
