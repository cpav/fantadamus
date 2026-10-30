# ADR-0006: In the MVP, Fantadamus fetches the round's facts itself from approved pages; Claude collects only as a fallback

- **Status:** Proposed, 2026-10-30
- **Deciders:** the owner
- **Amends:** ADR-0005 (each user's Claude collects): for the pages below, our server fetches them instead.
  Claude's collection stays as the fallback. ADR-0004's fetching rules apply from now, not from v1.
- **Specs affected:** `mvp-collect` (new); `mvp-x-or-y` (its refresh plan becomes the fallback)

## Context

In the first real round and four test runs (2026-10-26 to 2026-10-30), collecting through Claude failed in a
different place each time:

- Claude's page reader saw only a stale cache of Wikipedia, so the round's fixtures couldn't be read.
- Claude guessed the shape of nested payloads and every submission was rejected (fixed: schemas served whole).
- The betting previews had no odds for a match, or only 1X2, so answers fell back to team form.
- In a Claude Code session, the auto-mode safety check blocked one submission and let the next through, with
  no reason given.

Each problem was fixed, but the design multiplies risk: an answer needs Claude to browse several pages and make
several correct tool calls in an environment we don't control. Ten steps that each work nine times out of ten
give a complete answer about a third of the time.

Meanwhile the facts this slice needs sit on a few approved pages, as plain HTML, at stable addresses, and their
sites allow fetching (checked 2026-10-30):

- **Fantacalcio-Online's round page** (`/it/serie-a/{season}/probabili-formazioni/{n}-giornata`) lists every
  match of the round with its kickoff, the 1X2 odds with implied percentages, the chance of 3 or more goals,
  and for every player the start percentage from four outlets side by side: Fantacalcio.it, Gazzetta, SOS
  Fanta and Sky. A column confirms the official lineup once it's out. Its robots.txt allows all crawlers
  except `/*/auth/`.
- **Fantacalcio.it** serves the calendar, the table (`/serie-a/classifica`), the penalty takers
  (`/rigoristi-serie-a`), each club's squad page with links to every player's profile, and the profiles
  themselves. Its robots.txt disallows `/probabiliformazioniseriea`, `/ricerca` and a few test paths, none of
  which we need. Its terms risk was accepted by the owner for the MVP (source registry, 2026-10-24).
- **Wikipedia's season page** is readable directly from a server, unlike through Claude's cache, and serves as
  a cross-check for fixtures and the table.

## Options

| Option | For | Against |
|---|---|---|
| A. Keep Claude collecting, keep fixing each failure | No new code paths; no fetching by us | Every answer still depends on Claude's browsing and permissions; reliability stays low |
| B. Fantadamus fetches the approved pages itself, on demand and on a schedule; Claude falls back | One tool call per answer; deterministic and testable; many sources per fact; works the same for every player | Parsers break when a page's layout changes; we take on ADR-0004's fetching duties now |
| C. Licensed APIs now (The Odds API, API-Football) | The most robust data | Accounts and keys; API-Football's free tier is small; doesn't cover outlets' probable lineups |

## Decision

**Option B.** In the MVP, Fantadamus fetches the round's facts itself from the approved pages listed in the
`mvp-collect` spec, under ADR-0004's rules:

1. robots.txt is honoured on every fetch;
2. no logins, paywalls, blocks or bot checks are circumvented;
3. at most one request per second per host, with a user agent that names Fantadamus;
4. only facts are stored, with each page's URL, capture time and content hash, never the page text
   (ADR-0005, guardrail 4).

Claude's collection through the refresh plan stays as the fallback when a page can't be read or parsed, and
the failure is reported rather than hidden. Licensed APIs (option C) stay for v1, as the source registry
decided.

## Consequences

- **Easier:**
  - an answer is one `compare_players` call;
  - every fact can come from several sources, compared, as the product's principles ask;
  - the collector can run on a schedule, so forecasts are already fresh when people ask;
  - v1 reuses the same readers, moving them to AWS.
- **Harder:**
  - each page needs a reader (a parser) and tests;
  - a site redesign breaks its reader until fixed, so the collector must report reader failures loudly and
    fall back to Claude.
- **To do:**
  - the `mvp-collect` spec;
  - the source registry's MVP reading list notes which pages the server now fetches;
  - recorded pages stay out of the public repository, so reader tests use synthetic pages shaped like the
    real ones, plus optional checks against pages saved under `data/private/`.

## Sources

- [Fantacalcio-Online robots.txt](https://www.fantacalcio-online.com/robots.txt), read 2026-10-30: `Allow: /`,
  `Disallow: /*/auth/`
- [Fantacalcio-Online round 10 probable lineups](https://www.fantacalcio-online.com/it/serie-a/2026-2027/probabili-formazioni/10-giornata),
  read 2026-10-30: per-match kickoffs, 1X2 odds and percentages, chance of 3+ goals, and per-player start
  percentages from Fc, Gaz, SOS and Sky in the page HTML
- [Fantacalcio.it robots.txt](https://www.fantacalcio.it/robots.txt), read 2026-10-30: disallows
  `/probabiliformazioniseriea`, `/ricerca`, `/homesheet` and test paths
- [Fantacalcio.it calendar](https://www.fantacalcio.it/serie-a/calendario) and
  [table](https://www.fantacalcio.it/serie-a/classifica), read 2026-10-30: round fixtures with kickoffs, and
  played, goals for and against per club, in the HTML
- [Fantacalcio.it Inter squad page](https://www.fantacalcio.it/serie-a/squadre/inter), read 2026-10-30: 24
  profile links of the form `/serie-a/squadre/inter/{player}/{id}`
- [ADR-0004](0004-mvp-on-demand-web-ingestion.md) (the fetching rules) and
  [ADR-0005](0005-mvp-claude-collects-tools-decide.md) (Claude collects)
- The test runs of 2026-10-26 and 2026-10-30: `docs/reports/phase-1-report.md` and PRs #17, #20, #21 and #22
