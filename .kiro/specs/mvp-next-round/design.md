# Design Document: `mvp-next-round` (after Phase 2, before Phase 3)

Status: **Draft, for the owner's approval** · From the approved [requirements](requirements.md) (2026-11-25, all three
decisions as recommended)

## Overview

One number changes: the fixtures' cadence in `web/cadence.py`, from a week to 24 hours. A scheduled run already reads the
round page whenever the fixtures are due, stores what it shows and takes the round it names, so a daily read finds the
next round within a day of the site showing it. From then on the lineups, the odds, the injuries' last two days, the
alerts and the scoring work as they do now. The rest of the slice is its tests, written first, and the docs that
describe the schedule.

## What it builds on

- **The cadence** (`web/cadence.py`; `mvp-collect` C7, `mvp-sources` C9, `mvp-fixes` C3). The fixtures are one of the
  facts in `_ALWAYS`: due at their interval after the round page's last answered read, whatever the matches.
  `what_is_due` gives them no kickoff, so no stored fixture can hold them back, and R1.2 holds without a rule of its own.
- **A scheduled run** (`collect_due`). It reads each page whose facts are due once, through the collector, and logs the
  run. The fixtures' page is the round page (`page_of`). `Collector._store` keeps what changed since the page's last
  stored read. An unchanged page's facts are stored again once that read is older than the answers' 14-day window
  (`FACTS_WINDOW`), so that answers still find them.
- **The next round** (`next_round` in `domains/fixtures/gold.py`): the first stored round whose deadline is ahead. The
  cadence, the alerts' window (`mcp/alerts.py`), the answers and the scoring's bracket (`round_frame`) all go through it.
- **The fetcher and the log** (`mvp-collect` C1, `mvp-fixes` C1 and C2): robots.txt, one request a second per host, a
  block that stops the host for the run, and the log's answered and failed tries. None of them changes.

## Components

### C1. The fixtures daily (`web/cadence.py`; R1, R2)

- `_ALWAYS["fixtures"] = 24 * _HOUR` instead of `7 * 24 * _HOUR`. Nothing else in `due` or `what_is_due` changes.
- The module's table says: "Fixtures | Daily: the round page, so that the next round is found within a day of the site
  showing it (`mvp-next-round` R1.1)".
- What follows, with no code of its own:
  - **R1.2:** no kickoff goes with the fixtures. A locked round's later matches, a postponed match and a round stored by
    hand can't hold the read back.
  - **R1.3:** with a run every 15 minutes, the page is read within 24 hours and one run of its last answered read. The
    first such read once the site shows the next round stores it.
  - **R1.4, R2.4:** the other intervals and `_ON_DEMAND_EVERY` stay as they are. A daily read is a read of the round
    page, so in the last three days before a match the lineups' and odds' intervals count from it, as they count from
    any read of the page today.
  - **R1.5, R2.1 to R2.3:** the same collector, fetcher and log. A run reads the page once whatever is due. A failed try
    is due again at the next run, and one that got the site's answer waits 24 hours.

### C2. Two earlier tests that say weekly (R3.2)

Neither is an acceptance test. Running the whole suite with the change, outside the repository, found these two, and
nothing else:

- `tests/unit/collect/test_cadence.py::test_cadence_table` (`mvp-collect` task 7.1): its three lines for "Fixtures:
  weekly, whatever the matches" say daily, due at 24 hours and not at 23.
- `tests/integration/roles/test_two_pages.py::test_due_reads_only_the_pages_due` (`mvp-roles` task 3.2). It reads both
  pages, then expects only the statistics page a day later, and nothing on the third day from a collector without a
  statistics page. Now the round page is due a day later too. Its expectations stay as they are; its set-up gains a read
  of the round page alone a few hours after the first run and again on the third day, as an answer makes, so that only
  the statistics page is due when it looks.

### C3. The docs (R3.3)

- `mvp-collect` R7.1: the table's row reads "Fixtures | Daily", with an italic note under it, as `mvp-lineup` left one:
  "Amended by `mvp-next-round` R1.1: daily instead of weekly, so that the schedule finds the next round in time."
- `docs/player-setup.md`, step 8: "… and Fantacalcio-Online's round page at least once a day, so that it finds the next
  round as soon as the site shows it."
- The table in `web/cadence.py` (C1).

### C4. The test harness (`tests/next_round_harness.py`)

- An invented round page as the site shows it over time: round 10 until it moves on, then round 11 with its fixtures
  alone (an early page, as on 31 October), then with lineups and odds from 80 hours before its first kickoff.
- `Schedule.run(when)` and `Schedule.runs(start, end, every)`: the schedule's runs, `collect_due` over a `FakeWeb` with a
  set clock; and `Schedule.next_round(at)`.
- AT-5 uses the lineup and alerts harnesses (`tests/lineup_harness.py`, `tests/alerts_harness.py`), with round 11's page
  on a Tuesday.

### C5. The real check (AT-7), from here

On a copy of the owner's lake and collection log, in the worktree's own git-ignored `data/local`:

- **The replay:** from round 12's deadline on 21 November, `what_is_due` minute by minute with `main`'s code and with the
  change. The round page is next due on 28 November at 13:14 UTC today, and on 22 November at 13:14 with the change.
  Measured on 25 November with a throwaway copy; the task measures it again on the real code.
- **Every answer:** `python -m tests.real_lake --record` with `main`'s code, then `--compare` with the change. Every
  answer must be identical, since no answer's code changes.

Times and counts only, in the slice report.

## Error handling

| Situation | What happens |
|---|---|
| The page still shows the locked round | The read finds it unchanged; the next read is 24 hours later |
| The page shows the same round for weeks (a break, the summer) | One read a day; the same facts stored again once every 14 days, so that answers find them |
| No answer, a timeout, a server error, or robots.txt that can't be read | Failed: tried again at the next run (`mvp-fixes` R1) |
| robots.txt refuses the page, a block, a page that's gone, an unreadable page | The site's answer: it counts, and the page waits 24 hours |
| The page switched off in the reading list | "Switched off": nothing is asked, and Claude reads it through `read_page` as today |
| The Mac sleeps | The read waits for the first run after waking: a fact due stays due (`mvp-collect` P7) |
| A round stored by hand, or a page Claude submits | Holds nothing back (R1.2) |
| An answer reads the page | It counts as that day's read, as today |

## Correctness properties

| # | Property | Requirement |
|---|---|---|
| P1 | For any answered and failed tries of the round page at any times, with any kickoff or none and any official lineup, the fixtures are due exactly when no answered try is in the last 24 hours | R1.1, R1.2, R2.2, R2.3 |
| P2 | With runs every 15 minutes from any moment, and answers' own reads at any times, the first read at or after the page moves on comes at most 24 hours and 15 minutes after it | R1.3 |
| P3 | For every other fact, `due` gives what its cadence says, written out again in the test from the specs; and an answer may read each page exactly when it may today | R1.4, R2.4 |

## Testing strategy

- **Property:** P1 and P2, pure, in `tests/property/next_round/`. P3 is AT-6.
- **Acceptance,** on invented pages with a set clock, in `tests/acceptance/next_round/`:
  - **AT-1:** round 10 locks; its page moves on 4 hours 21 minutes later, as round 10's did on 31 October; round 11's
    deadline is 6 days 5¾ hours after round 10's, as from round 12 to round 13. Round 11 is stored, its fixtures alone,
    at the first run 24 hours after the last read before the deadline. Then only daily reads until its last three days,
    then today's cadence: lineups at most every 3 hours in the last day, official lineups from 75 minutes before.
  - **AT-2:** the read is due 24 hours after the last one, not a minute sooner, and stores round 11. Three cases: with
    only the locked round stored, with a match postponed from round 8 to December, and with round 20 stored by hand.
  - **AT-3:** three weeks with the locked round on the page, a run every two hours: 20 reads, at least 24 hours apart.
    "Nothing new" is read as the requirements mean it, no fact that wasn't stored before: the payloads' hashes stay
    those of the first read, although the same facts are stored once more after 14 days (the answers' window). The
    first read after the page moves on stores round 11.
  - **AT-4:** seven outcomes. No answer, a server error and robots.txt without an answer are due at the next run.
    robots.txt's refusal, a block, a page that's gone and an unreadable page are due 24 hours later. Each run asks
    robots.txt, then the page a second later, once; with the page switched off, nothing is asked.
  - **AT-5:** a Saturday round, then a Tuesday one: the second is stored before its alert window opens. The first run
    inside the window keeps a baseline; an official lineup that benches a starter sends "Official lineup out".
  - **AT-6 (P3):** Hypothesis over facts, last reads, kickoffs and official lineups, against the cadence written out
    again in the test; and `may_read_after` for every page against `_ON_DEMAND_EVERY` and the 15 minutes after a failed
    try.
  - **AT-7:** from here (C5). **AT-8:** no new dependency, and the docs say daily.
- **Seen failing:** each test was drafted outside the repository on 2026-11-26. With today's weekly fixtures, AT-1 to
  AT-5 and P1 and P2 fail, while AT-4's politeness and switch tests and AT-6 pass, as they should. With the daily
  fixtures all 19 pass, the slowest in about 6 seconds.
- **Mutation:** `_ALWAYS` is data, which `mutmut` doesn't change, and `due` doesn't change. So the deliberate faults are
  made by hand instead: the interval back to a week, then to 25 hours and to 23 hours, and the fixtures given the next
  round's first kickoff, so that a stored round would hold them back. Each must be caught.

## Cost

$0: no dependency, service or account. The schedule reads the round page three or four more times in a normal week, and
ten more in a break like November's.

## Build order (input to tasks.md)

1. The fixtures daily (C1, C2, C3, C4): AT-1 to AT-6, AT-8, P1 to P3. Merged before round 14's alert window opens; then
   `~/Documents/fantadamus` is brought up to `main`. The schedule runs that checkout's code at each run, so it needs no
   restart, and Claude Desktop needs none either: no answer's code changes.
2. The real check (C5), the deliberate faults by hand, the slice report and the owner's sign-off.

## Open points for the owner

None. The three decisions were taken with the requirements, and the two earlier tests that change (C2) were named there.
