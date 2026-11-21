# Design Document: `mvp-fixes` (Phase 2, eleventh slice)

Status: **Approved by the owner, 2026-11-21** · From the approved [requirements](requirements.md) (2026-11-21, all three
decisions as recommended) · Abbreviation: `fx`

## Overview

Five small fixes, each in the code that already does the job: no new module, dependency or service. The first changes
how the collection log is read, so that a try that got no answer from the site no longer counts as the page's read.
The other four change words and sources in answers, and one log line. No chance, value or constant moves.

| Fix | Where | Requirement |
|---|---|---|
| A failed try is told apart, and doesn't count | `web/fetch.py`, `web/collector.py`, `lake/collect_log.py`, `web/cadence.py`, `cli/__main__.py` | R1 |
| `collect` takes every fact | `web/collector.py`, `mcp/tools/collect.py` | R2 |
| One list of a player's sources | `mcp/advisor.py`, `mcp/tools/lineup.py`, `mcp/tools/cards.py` | R3 |
| The penalty note says who's out | `mcp/advisor.py` | R4 |
| The review keeps the app's total | `domains/review.py`, `mcp/tools/review.py` | R5 |

## What it builds on

- **The fetcher** (`mvp-collect` C2, `web/fetch.py`): the allowlist, robots.txt cached for the day, one request a
  second per host, a host that blocks stopped for the run. A robots.txt it can't fetch is not cached and today becomes
  "disallow everything" for the run, so every page of the host is reported as disallowed.
- **The collection log and the cadence** (`mvp-collect` C10, `mvp-store` C6): each run appends its report; `due()` and
  `may_read_page()` take a page's newest try from `CollectLog.last_attempt`, whatever its outcome.
- **A player's facts** (`PlayerFacts`, `mcp/advisor.py`), gathered once per answer; `sources_of` in
  `mcp/tools/lineup.py` serves the lineup and the card, and `advisor.py` builds an outlook's and a comparison's own list.
- **The review log** (`mvp-review` C7): one `LoggedReview` line per review; the season record reads the latest of each
  round.

## Components

### C1. A failed try is told apart (`web/fetch.py`, `web/collector.py`; R1.1, R1.3)

- **robots.txt that can't be fetched.** When the robots.txt request raises `FetchFailedError` (a network error or a
  timeout) or answers a server error outside `_BLOCK_STATUSES` (500, 502, 504 and the like), the fetcher remembers the
  cause for the host for the rest of the run and doesn't cache it. Each page of that host then raises
  `RobotsUnreadableError(FetchFailedError)`: "robots.txt couldn't be read (the cause); not requested". robots.txt is
  asked once per host per run, as today (R1.3).
- **Unchanged:** a robots.txt the site serves (200), a 404 or 410 (everything allowed), and any other answer under 500
  are cached for the day as today; 429 and 503, the block statuses, still mean nothing is fetched for the run and the
  pages are reported as disallowed.
- **A page the site says isn't there.** `fetch` raises `FetchFailedError` for any status that isn't 200 or a redirect.
  It now raises `PageMissingError(FetchError)` for a 4xx outside the block statuses, and the collector reports it as a
  new outcome, `missing`. Without it, a page that is gone would count as a failed try and be asked for every 15
  minutes for ever; with it, the site's answer counts, as the requirements' glossary says.
- **Outcomes.** `failed` now means exactly the requirements' failed try: no answer, a timeout, a server error outside
  the block statuses, or robots.txt unreadable. Every other outcome is the site's answer (or the collector's own
  setting: switched off, not on the allowlist).

### C2. The log counts answered tries (`lake/collect_log.py`; R1.2)

- `ANSWERED = every outcome but "failed"`.
- `last_attempt` becomes `last_answered(as_of, page, since)`: the newest run at or before `as_of` whose report for the
  page has an answered outcome. `last_failed(as_of, page, since)` gives the newest failed try.
- Lines logged before this slice are read as they are: Saturday 21 November's unreadable robots.txt was logged as
  `disallowed` then, and still counts. History isn't rewritten.

### C3. The cadence and the answers try again (`web/cadence.py`; R1.2, R1.3)

- `what_is_due` gives `due()` the page's `last_answered`. A failed try doesn't hold the page back: it is due again at
  the next scheduled run, 15 minutes later while the Mac is awake. A run reads each due page once, so a page that keeps
  failing is tried at most once a run.
- `may_read_page` lets an answer read a page when its last answered try is older than the page's shortest interval
  (`_ON_DEMAND_EVERY`, as today) **and** its last failed try is older than `RETRY_AFTER = 15 minutes` (decision 1).
- A block still counts: a site that said stop isn't asked again before the page's cadence (R1.4).

### C4. The report says so (`cli/__main__.py`, the refresh plan's note; R1.5)

- `_page_lines` prints a failed page as "failed (the cause): tried again at the next run".
- The refresh plan's note on what the collector tried (`tried_notes` in `mcp/advisor.py`, one place) says, for a failed
  page, that the collector couldn't reach it and tries again at its next run, so Claude doesn't take it for a refusal.

### C5. `collect` takes every fact (`web/collector.py`, `mcp/tools/collect.py`; R2)

- `CollectFact = Literal[…]`, the 11 facts, beside `FACTS` in `web/collector.py`. A unit test asserts that the
  `Literal`'s values are exactly `FACTS` (R2.2): adding a fact to one and not the other fails.
- `PAGE_NAMES: dict[PageKind, str]` beside `PAGE_FACTS` names each page for people ("Fantacalcio.it's injured
  players page"); the tool's description is built from it, and a test asserts every page kind that carries a fact has
  a name (R2.1).
- The tool's `fact` parameter takes a `CollectFact`. The ratings are read for the round just played, as
  `collector.collect(round, [fact])` already does (R2.3). The prompt is unchanged.

### C6. One list of a player's sources (`mcp/advisor.py`, `mcp/tools/lineup.py`, `mcp/tools/cards.py`; R3)

- `PlayerFacts.sources(rested: Rested | None = None) -> list[Source]`: the season figures, the table, the takers, the
  match, the outlets, the official lineup, the odds, the injured or suspended page when the player has news, and the
  other competitions' pages when rest days are shown.
- The lineup (`sources_of`), the card and the answer builder for an outlook and "X or Y?" all call it, in place of their
  own lists (the review's R7, for this list only). A lineup that says why a player is out now names the injured or
  suspended page, with when it was read.
- The review's sources (the statistics reads before and after, the fixtures) are already its own and complete; a test
  checks them too (R3.2).

### C7. The penalty note says who's out (`mcp/advisor.py`; R4)

- In the penalty notes, when the taker has names listed ahead and his share is 1 (none of them can start): "X, first on
  the club's list, is out, so Y takes the penalties: counted in full", or with several, "X and Z, listed ahead, are
  out, …".
- Otherwise the note is today's: "Y takes the club's penalties if X misses the start: they count at 63%."

### C8. The review keeps the app's total (`domains/review.py`, `mcp/tools/review.py`, `docs/answer-formats.md`; R5)

- `LoggedReview` gains `app_total: float | None = None` and `app_differs: bool | None = None`. The defaults read every
  line logged before (R5.3).
- `logged(…)` takes both from the tool, which already works out `app_differs` against `APP_GAP` for its answer.
- `Record` gains `app_rounds` (latest reviews of a round with an app total) and `app_matched` (of those, not differing).
  The answer's record gives "your app's total matched in n of m rounds" from the first round with one (decision 3).
- A total given in a second call, as on 18 November, is a new review of the round, and the latest takes over, as
  today.

### C9. The docs (R6.3)

- `docs/player-setup.md`: the schedule section and "If something goes wrong": a page it couldn't reach is tried again
  at the next run, so a closed lid costs only the time it was closed.
- `README.md`: `collect --fact` takes any of the facts the collector reads.
- `docs/answer-formats.md`, format 7: the app's-total line in the record.

## Error handling

| Situation | What happens |
|---|---|
| The network is down for hours | Each run tries each due page once (robots.txt once per host) and logs them as failed; nothing is stored, so no alerts' check runs; the next run that has a network reads them |
| A run is suspended by sleep and resumes offline (21 November) | The pages after the pause fail and are tried again at the next run, instead of 12 to 24 hours later |
| A site answers 500 for hours | Tried at most once a run, four times an hour, until it answers |
| A site blocks (403, 429, 503, a bot check) | As today: counted, and not asked again before the page's cadence |
| A page answers 404 | `missing`: counted, so it isn't asked again before its cadence |
| A server still running code from before the slice reads a log line with `missing` | It skips the line it can't read, as `read_lines` does with any unreadable line; restarting Claude Desktop after the merge ends it |

## Correctness properties

Each is a Hypothesis test (`quality.md`: required).

- **P1 (R1.2, R1.4).** For any sequence of tries of a page, with any outcomes and times, the page is due exactly when
  its newest answered try is older than its cadence: failed tries never hold it back, and answered ones always do.
- **P2 (R1.3).** Over any sequence of runs in which a host's robots.txt fails, the fetcher asks for robots.txt at most
  once per host per run and requests none of the host's pages, and an answer never tries a page sooner than
  `RETRY_AFTER` after a failed try.
- **P3 (R3).** For any player's facts, with any of them present or missing, `PlayerFacts.sources()` holds the source of
  every fact present.
- **P4 (R5).** For any logged reviews, with or without an app total and with rounds reviewed more than once, the
  record's `app_rounds` and `app_matched` count the latest review of each round, and a line without the new fields
  reads.

## Testing strategy

- **Unit:** the fetcher on a fake transport (a network error, a timeout, 500, 502, 503, 429, 404 and 200 for
  robots.txt and for a page); the collection log's `last_answered` and `last_failed`; `due` and `may_read_page`; the
  penalty note; `record`.
- **Integration:** the collector on a fake transport writing the log, then `what_is_due` at the next tick (AT-1 to
  AT-3); the `collect` tool through the protocol for a fact of each page (AT-4); the lineup, card, outlook and review
  through their tools (AT-5 to AT-7).
- **Real check (AT-8), from here on a copy of the owner's lake:** Saturday 21 November's run is run again on the copy
  with a transport that can't reach the two hosts, then `what_is_due` at the next tick finds their pages due. Every
  answer of `tests/real_lake.py` is then compared field by field before and after: only sources and penalty notes may
  differ, and each difference is listed by kind. Times and counts only in the report.
- **Mutation:** `make mutate ONLY=…` on `lake/collect_log.py` and `web/cadence.py`'s pure parts; the rest by breaking it
  on purpose by hand, as `mvp-store` did, since DuckDB and the fetcher's I/O can't be forked.

## Cost

$0: no dependency, service or account.

## Build order (input to tasks.md)

1. **R1, a failed try doesn't count** (C1 to C4), with AT-1 to AT-3, P1, P2 and AT-8's replay: its own pull request,
   merged before round 13's alerts window, then Claude Desktop restarted.
2. **R2, `collect` takes every fact** (C5), AT-4.
3. **R3, one list of sources** (C6), AT-5, P3.
4. **R4, the penalty note** (C7), AT-6.
5. **R5, the app's total** (C8), AT-7, P4.
6. **The docs and the gate** (C9): AT-8's full comparison, AT-9, the mutation run, the slice report and the owner's
   sign-off.

## Open points for the owner

None: the three decisions were taken with the requirements. One choice made here, within them: a page's 4xx outside the
block statuses becomes a new outcome, `missing`, that counts as the site's answer (C1), so a page that's gone isn't
asked for every 15 minutes.
