# Requirements Document: `mvp-collect` (Phase 2, first slice)

Status: **Draft for the owner's review** · Workflow: requirements-first · 2026-10-30 · Depends on:
[ADR-0006](../../../docs/adr/0006-mvp-fantadamus-collects-round-facts.md) (proposed with this document)

## Introduction

Testing `mvp-x-or-y` showed that answers are only as reliable as Claude's browsing: four runs failed in four
different places. This spec makes Fantadamus collect the round's facts itself, from the approved pages, on
demand and on a schedule. Claude's collection stays as the fallback.

The owner's vision shapes the answer too: **a weather app for fantasy decisions**. Every probability comes
first, with the reason behind it, how sure it is, how it has moved, when it was last updated, and its sources.
The numbers keep moving as news arrives, up to the deadline.

It builds on `mvp-x-or-y`: the same contracts, quality rules, bronze → silver flow, as-of reads, forward model
and `compare_players`. Only how facts arrive changes, plus what the answer says about them.

**Not in this spec:** live in-match forecasts (a later spec; the data stays as timestamped snapshots, so it's
possible); licensed APIs (The Odds API, API-Football: v1); search-based sources; keepers, defenders and the
full lineup (the next slices); committing recorded pages (the repository is public).

## Glossary

Spec-wide terms are in `product.md`; `mvp-x-or-y`'s terms apply. Here:

| Term | Meaning |
|---|---|
| Collector | The part of Fantadamus that fetches approved pages, reads them and stores the facts |
| Reader | The code that turns one kind of page into facts, for example Fantacalcio-Online's round page |
| Outlet view | One outlet's start percentage for one player, for example Gazzetta's 90% |
| Cadence | How often a fact is refreshed, tightening as the match nears |
| Confidence | How sure a probability is: how many sources gave it and how far apart they were |
| Movement | How a probability changed since the user's previous answer, or since 24 hours earlier |

## Sources

All on the MVP reading list and the allowlist, with robots.txt allowing these paths (checked 2026-10-30,
ADR-0006).

| Fact | Pages the collector reads | Independent sources |
|---|---|---|
| Fixtures and kickoffs | Fantacalcio.it calendar; Fantacalcio-Online round page; Wikipedia season page | 3 |
| Probable lineups, as outlet views | Fantacalcio-Online round page (Fantacalcio.it, Gazzetta, SOS Fanta and Sky side by side); Fantacalcio.it's own probable-lineups page | 4 outlets, 2 pages |
| Official lineups | Fantacalcio-Online round page, once it confirms them | 1 |
| Match odds | Fantacalcio-Online round page: 1X2 odds and the chance of 3+ goals | 1 (more in v1) |
| League table | Fantacalcio.it table; Wikipedia season page | 2 |
| Penalty takers | Fantacalcio.it penalty-takers page | 1 |
| Players' season figures | Fantacalcio.it profiles, found through each club's squad page | 1 |

## Requirements

### Requirement 1: The collector

**User Story:** As a player, I want Fantadamus to gather what it needs by itself, so that an answer doesn't
depend on Claude managing to browse a dozen pages.

- **R1.1** THE SYSTEM SHALL provide a collector that fetches the pages in the Sources table, reads them into
  the existing contracts and stores the facts through the same bronze → silver flow as a submission, with
  `submitted_by` set to `collector`.
- **R1.2** THE SYSTEM SHALL offer the collector as an MCP tool `collect` (everything due, one kind of fact or
  one round) and as the command `fantadamus collect`, each reporting, per page: fetched, read, rows stored, or
  why it failed.
- **R1.3** WHEN `compare_players` finds a fact missing or stale THE SYSTEM SHALL run the collector for it first,
  within 60 seconds, and answer from what it collected. Only what the collector couldn't get SHALL go into the
  refresh plan for Claude.
- **R1.4** THE SYSTEM SHALL NOT fetch a fact that is still fresh, and a page whose content hasn't changed SHALL
  store nothing new.

### Requirement 2: Polite fetching

**User Story:** As the owner, I want our fetching to be the kind the sites allow, so that the MVP stays on
approved routes.

- **R2.1** THE SYSTEM SHALL read each host's robots.txt (at most once a day per host) and SHALL NOT fetch a
  disallowed path.
- **R2.2** THE SYSTEM SHALL make at most one request per second per host, with a user agent that names
  Fantadamus and links to the repository.
- **R2.3** THE SYSTEM SHALL fetch only pages on the allowlist. IF a host answers with a login, a block, a bot
  check or "too many requests" THEN the collector SHALL stop fetching from that host for the run and report it,
  never trying to get around it.
- **R2.4** THE SYSTEM SHALL store only the facts read from a page, with the page's URL, capture time and content
  hash, never the page text.
- **R2.5** THE SYSTEM SHALL let the owner switch a source off in configuration, without changing code.

### Requirement 3: Readers

**User Story:** As the owner, I want each page read the same way every time, so that facts are correct and a
changed page is noticed.

- **R3.1** THE SYSTEM SHALL read Fantacalcio-Online's round page into:
  - the round's fixtures and kickoffs;
  - each match's 1X2 odds and its chance of 3 or more goals, the latter used as P(over 2.5);
  - each listed player's start percentage per outlet (Fantacalcio.it, Gazzetta, SOS Fanta, Sky) for both
    teams;
  - the official lineup, once the page confirms it.
- **R3.2** THE SYSTEM SHALL read Fantacalcio.it's calendar (fixtures), table (played, goals for and against),
  penalty-takers page, each club's squad page (each player's profile address) and player profiles (the season
  figures of `mvp-x-or-y` R6.1).
- **R3.3** THE SYSTEM SHALL read Fantacalcio.it's own probable-lineups page as a second, independent lineup
  source, and Wikipedia's season page as a cross-check for fixtures and the table.
- **R3.4** IF a reader doesn't find what it expects on a page THEN it SHALL store nothing from that page and
  report the page as unreadable, so that a changed layout fails loudly instead of loading wrong facts.
- **R3.5** THE SYSTEM SHALL map the clubs and players a reader finds through `config/clubs.toml` and name
  resolution, as submissions are.

### Requirement 4: Outlets' own percentages

**User Story:** As a player, I want each outlet's own number for a player, so that his chance of starting
reflects what they actually say.

- **R4.1** WHERE an outlet gives a start percentage for a player THE SYSTEM SHALL use it as that outlet's view
  of his p_start, in place of `mvp-x-or-y` R3.2's mapping (starter 0.90, bench 0.05), which stays for sources
  that publish lineups without percentages.
- **R4.2** THE SYSTEM SHALL count each outlet on a page that shows several as its own outlet, with that page as
  its source, and SHALL NOT count the page's own average again. The same outlet read from two pages SHALL count
  once, from the most recent read.
- **R4.3** THE SYSTEM SHALL keep `mvp-x-or-y`'s consensus: p_start is the mean of the outlets' views, the spread
  marks a disputed place, p_cameo is 0.5 × (1 − p_start), and an official lineup overrides everything.

### Requirement 5: Many sources, compared

**User Story:** As a player, I want to know when sources disagree, so that I know how far to trust a number.

- **R5.1** WHEN fixtures or the table differ between sources THE SYSTEM SHALL use Fantacalcio.it's figure and
  say in the answer which sources disagreed and how.
- **R5.2** THE SYSTEM SHALL average match odds across the sources that give them, de-margined, and say when a
  match's odds come from one source only.
- **R5.3** THE SYSTEM SHALL give every published probability a confidence: how many sources gave it and how
  far apart they were, or "one source" when there was only one.

### Requirement 6: The forecast answer

**User Story:** As a player, I want answers that read like a good weather forecast, so that I see the chance,
why, how sure, how it has moved and how fresh it is, at a glance.

- **R6.1** THE SYSTEM SHALL return, for each player's p_start, P(scores) and his team's chance to win, its value
  at the user's previous answer for that player (from the decision log) or, without one, 24 hours earlier (an
  as-of read), and which fact changed it.
- **R6.2** THE SYSTEM SHALL return when the answer's facts were last updated: the newest and oldest capture
  time, so the answer can say "updated 12 minutes ago".
- **R6.3** THE SYSTEM SHALL return, for each player, the pages his facts came from, for a Sources list at the
  bottom of the answer.
- **R6.4** THE SYSTEM SHALL tell Claude, in the agent prompt, to answer as a forecast in the owner's "X or Y?"
  shape: the probability first, the reason in one line, the confidence, the movement, the last update, and the
  Sources at the bottom.

### Requirement 7: The schedule

**User Story:** As a player, I want the forecast fresh before I ask, so that a question minutes before the
deadline is answered at once.

- **R7.1** THE SYSTEM SHALL provide `fantadamus collect --due`, which fetches only what is past its cadence:

  | Fact | Cadence |
  |---|---|
  | Probable lineups | Twice a day from 72 hours before the match; every 3 hours in the last 24 |
  | Official lineups | Every 15 minutes from 75 minutes before each kickoff until confirmed |
  | Match odds | Daily from 72 hours before the match; every 3 hours in the last 24 |
  | Table, penalty takers, players' season figures | After each round, and at least weekly |
  | Fixtures | Weekly |

- **R7.2** THE SYSTEM SHALL document how a player sets up their Mac to run `collect --due` every 15 minutes
  (launchd). The player installs it themselves; the collector does nothing when nothing is due.

### Requirement 8: Failures are visible, and Claude falls back

**User Story:** As the owner, I want to see what the collector couldn't get, so that a broken page is fixed
rather than silently skipped.

- **R8.1** IF a page can't be fetched, is disallowed or can't be read THEN the facts it carries SHALL go into the
  refresh plan for Claude, as in `mvp-x-or-y`, and the answer SHALL say which source failed.
- **R8.2** THE SYSTEM SHALL keep a log of each collection run (the pages, what happened, the rows stored) that
  the owner can read with `fantadamus collect --report`.

## Acceptance tests

| ID | Acceptance test | Proves |
|---|---|---|
| AT-1 | From synthetic pages served by a local test server (no internet), one collection stores the fixtures, table, takers, profiles, four outlets' views and the odds, each with its page's URL; a second run stores nothing new | R1, R2.4, R3 |
| AT-2 | A path that robots.txt disallows is never requested, and the report says so | R2.1 |
| AT-3 | Two requests to the same host are at least one second apart; a "too many requests" stops that host for the run | R2.2, R2.3 |
| AT-4 | Fantacalcio-Online's views of 90%, 90%, 55% and 90% give a p_start of 0.8125, disputed (spread 0.35), and the page's own average isn't counted | R4 |
| AT-5 | From a lake with only the league rules, `compare_players` answers in one call: the collector runs, no submit tool is used, and the answer carries sources and update times | R1.3, R6.2, R6.3 |
| AT-6 | A page with an unexpected layout stores nothing; the report names it, and the refresh plan lists its facts for Claude | R3.4, R8.1 |
| AT-7 | When the calendar and Wikipedia disagree on a kickoff, the answer uses Fantacalcio.it's and says so | R5.1 |
| AT-8 | After an outlet moves a player to the bench, the next answer shows his p_start falling from the previous answer's value and names the change | R6.1 |
| AT-9 | At a given time, `collect --due` fetches exactly the facts past their cadence | R7.1 |
| AT-10 | Manual: the owner, and the second player on his Mac, ask a real "X or Y?"; only `compare_players` is called, before and after an official lineup | All |

## Owner decisions

- **2026-10-30:** after four failed test runs, the owner approved:
  - fetching from the approved pages ourselves under ADR-0004's rules, with Claude as the fallback (ADR-0006);
  - odds from Fantacalcio-Online's round page;
  - this work as its own spec, before the rest of Phase 2;
  - the collector as its own tool, called by `compare_players` and on a schedule;
  - many sources per fact, compared, with Sources listed at the bottom of every answer;
  - forecast-style answers (the "weather app"), with live in-match forecasts later in their own spec.
