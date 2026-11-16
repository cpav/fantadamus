# Requirements Document: `mvp-store` (Phase 2, tenth slice)

Status: **Draft, for the owner's approval** · Workflow: requirements-first · Depends on: `mvp-alerts` (built 2026-11-15;
its sign-off is decision 1) · Abbreviation: `st` ·
Research: [`docs/reports/review-before-phase-3.md`](../../../docs/reports/review-before-phase-3.md), findings 1 and 2

## Introduction

The review before Phase 3 (2026-11-16) found one thing to fix before the schedule is installed: **storing a read
costs more with every read already stored**, and an answer's reading costs more with every read in its window. This
slice makes both cost what's new, so that the schedule can run every 15 minutes for a whole season.

**No number moves.** Every answer is the same as before; only the time it takes changes.

What happens today:

- **Storing.** Every stored submission rebuilds its whole silver table from every bronze record, and inserts the rows
  one statement of 200 at a time (`domains/facts.py`, `lake/duckdb_store.py`). When one outlet's lineup changes, the
  collector stores all of the page's outlet lineups again: about 2,000 rows, which every later store inserts again.
- **Reading.** Every answer loads every row captured in its 14-day window into Python, then picks each outlet's
  newest lineup, once for each player (`mcp/advisor.py`, `domains/availability/gold.py`).

| Measured | Time |
|---|---|
| **On a copy of the real lake, 2026-11-16** (the review) | |
| Storing one changed read of the round page, with 319 lineups and 17,341 rows stored | 4.3 s |
| The same rows loaded in bulk | 0.15 s |
| Reading for one answer | 364 ms of a 557 ms "X or Y?" |
| **At season size, on generated rows** (for this spec) | |
| Reading a 14-day window with 56 reads of the round page in it (123,200 rows), as today | 1.8 s |
| Reading only each page's newest lineup for each match and outlet (2,200 rows) | 0.25 s |
| Appending one read by writing the table's one file again, with 220,000 rows stored | 0.2 s |
| The same with 2,200,000 rows stored | 2.0 s |
| Writing one read's 60 bronze files, as today | 0.5 s |

The appends say that a table kept as one file would still slow down over a season. The design has to keep an append
to a part of the table, a month's for example. The bronze files are why R1.2's budget is 2 seconds, not 1.

**Not in this spec:**

- storing only the lineups that changed (decision 2);
- the lake on S3, and a lock that works across machines (Phase 3);
- a stored gold table: gold stays computed when asked, as the review found it;
- the review's other recommendations: the application out of `mcp/`, one registry of facts, cheaper tests, the docs;
- any change to a chance, a value or a constant.

## Glossary

| Term | Meaning |
|---|---|
| Stored read | A read of a page whose facts differed from its last stored read, so they were stored (`mvp-collect` R1.4) |
| Silver table | A domain's rows, each with the page, the time and the hash of the submission it came from; it can always be rebuilt from bronze |
| Rebuild | Reading every bronze record of a domain and writing its silver table again from them |
| Window | The 14 days an answer reads back (`FACTS_WINDOW`) |
| Season size | A lake holding what a season stores at the scheduled cadence *(start)*: 1,000 stored reads of the round page (about 26 a round; some 2,000,000 outlet rows), 250 daily statistics reads, two reads of each round's ratings, 3,000 collection runs and 1,000 answers. 60 of the round page's reads fall in the window of the answer timed |

## Requirements

### Requirement 1: Storing costs what's new

**User Story:** As the operator, I want a scheduled run to store what it read in a second or two all season, so that
it can run every 15 minutes without falling behind.

- **R1.1** WHEN a submission is stored THE SYSTEM SHALL add its rows to its silver table, and the table SHALL then hold
  exactly the rows a rebuild would give. This amends `mvp-x-or-y` R7.1, which rebuilt the table each time.
- **R1.2** THE SYSTEM SHALL store one read of the round page, its bronze files and its silver rows, in under 2 seconds
  at season size.
- **R1.3** Bronze SHALL stay as it is: one file for each submission, added and never changed
  (`engineering-foundation` R16.3).
- **R1.4** A reader SHALL see a table as it was before a store or as it is after, never half written, as today.
- **R1.5** A scheduled run with nothing due SHALL finish its check of what is due in under 1 second at season size,
  the time to start the program apart: today it reads three whole tables for it.

### Requirement 2: Silver stays what bronze says

**User Story:** As the owner, I want the stored facts to be right after a crash, after two runs at once and after a
change of code, with nothing to do by hand.

- **R2.1** IF a store finds that a silver table doesn't hold the rows of every bronze record, because an earlier run
  stopped between the two, THEN THE SYSTEM SHALL rebuild that table before it stores.
- **R2.2** WHEN two runs store at the same time, the server's and the schedule's, THE SYSTEM SHALL keep both: once both
  have finished, the table holds the rows of both.
- **R2.3** WHEN the way a domain's payloads become rows has changed since its table was written (its columns, or a
  version the domain declares) THE SYSTEM SHALL rebuild the table at the next store.
- **R2.4** THE SYSTEM SHALL provide `fantadamus rebuild [--table <name>]`, which rebuilds every silver table, or one,
  reads no page, and prints each table's bronze records and rows.
- **R2.5** THE SYSTEM SHALL bring a lake stored before this slice to the new layout by itself, at its first store or
  with `fantadamus rebuild`, without touching a bronze file.

### Requirement 3: An answer reads what it uses

**User Story:** As a player asking minutes before the deadline, I want the answer as quickly in May as in November.

- **R3.1** THE SYSTEM SHALL answer within 3 seconds at season size: the budget `best_lineup`, `player_outlook`,
  `match_card`, `round_overview` and `review_round` already have, and from now `compare_players` too. An alerts' check
  SHALL stay within `ALERT_SECONDS`.
- **R3.2** Reading the lake for one answer SHALL take under 1 second at season size, however many times a page was
  read in the window.
- **R3.3** THE SYSTEM SHALL read the season's ratings only for an answer that shows a rater's claim
  (`compare_players`, `player_outlook` and `match_card`), and only the rows of the clubs it is about.
- **R3.4** THE SYSTEM SHALL read each log at most once for an answer, and the collection log only as far back as the
  answer looks.
- **R3.5** THE SYSTEM SHALL give the same answer as before this slice from the same stored facts: every chance, value,
  note, source and time. That includes a replay of an earlier time, a review and an alerts' check.

### Requirement 4: Nothing new to run or to pay for

- **R4.1** THE SYSTEM SHALL need no new dependency, service or account: DuckDB and the standard library, as today.
- **R4.2** Stored facts SHALL stay under `data/local/`, and nothing about a squad or a league SHALL reach the
  repository, a test or a log outside it.

### Requirement 5: The proof, and a gate that gets no slower

- **R5.1** Each time in this document SHALL be measured as the existing budgets are: CPU seconds, in a process of its
  own, the fastest of three (`tests/lineup_speed.py`).
- **R5.2** The existing budget tests and this slice's SHALL share one process, each asserting its own number, so that
  the pull-request gate takes no longer than before the slice.
- **R5.3** The wall-clock assertion in `tests/integration/lineup/test_reads.py` SHALL give way to a time measured as
  R5.1 says: it failed at 1.02 seconds in the review's run.
- **R5.4** THE SYSTEM SHALL update `tech.md`'s storage row, the README's commands and the lake's own descriptions,
  and the slice report SHALL give the real lake's times before and after.

## Acceptance tests

| Test | Proves | Requirement |
|---|---|---|
| AT-1 | For any order of submissions, the table after each store holds the rows a rebuild gives (a property) | R1.1 |
| AT-2 | At season size one read of the round page is stored in under 2 seconds, and a run with nothing due checks in under 1; no bronze file changes; a reader in between sees the table before or after | R1.2 to R1.5 |
| AT-3 | A run stopped between bronze and silver, two runs at once, and a domain whose rows changed each end with the table a rebuild gives | R2.1 to R2.3 |
| AT-4 | `fantadamus rebuild` rebuilds every table, or one, and sends no request; a lake in today's layout answers after it, its bronze untouched | R2.4, R2.5 |
| AT-5 | At season size every answer and an alerts' check stay within their budgets, and the reading within 1 second, timed as R5.1 says | R3.1, R3.2, R5.1, R5.3 |
| AT-6 | The ratings are read only for the three answers that show a claim, and each log once for an answer | R3.3, R3.4 |
| AT-7 | Reading everything and reading what an answer uses give the same answer, for generated histories of submissions (a property); every earlier acceptance test passes unchanged | R3.5 |
| AT-8 | From here, on a copy of the owner's lake: the answers at five past times are identical before and after; only times and counts go in the slice report | R2.5, R3.5, R4.2, R5.4 |
| AT-9 | No new dependency; the suite's time before and after, in the slice report | R4.1, R5.2 |
| AT-10 | The docs updated | R5.4 |

## Review (Analyze-Requirements style)

- **Ambiguity:** "season size" and "stored read" are in the glossary, with their numbers. "The same answer" is the
  tool's structured result, byte for byte.
- **Conflict:** reading less against the same answers (R3.2, R3.5). A read may leave out only rows that can't change
  an answer; AT-7 checks it on generated histories and AT-8 on real ones. Storing faster against silver being right
  (R1, R2): a store checks before it appends, and a rebuild stays one command away.
- **Testability:** every requirement has a test. The season is generated, since a real one doesn't exist yet. AT-8
  runs from here on a copy, with nothing for the owner to do.
- **Dependencies:** `mvp-collect` (the collector and `submit_many`), the answer slices' budgets, `mvp-alerts` (the
  scheduled run and its check).

## Decisions for the owner

1. **The order.** Recommendation: install the schedule after this slice, and close `mvp-alerts` without it.
   `fantadamus alerts --test` shows that notifications get through. `fantadamus collect --due --user owner`, run by
   hand in a round's last day, sends a real alert if the call has changed; its AT-5 accepts a replayed one too.
2. **Should the collector also stop storing the lineups that didn't change?** It stores a page's every outlet lineup
   again when one changes. Storing only the changed ones would cut what's stored about tenfold, but an unchanged
   lineup would then count as fresh on the collection log's word alone, which changes `mvp-collect` R1.5 and could
   change an answer. Recommendation: not in this slice. Decide it with Phase 3's storage design, once this slice has
   shown what a season costs.
