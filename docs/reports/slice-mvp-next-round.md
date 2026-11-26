# Slice report: `mvp-next-round`

2026-11-26 · After Phase 2, before Phase 3 · **For the owner's sign-off**

From a round's deadline until something reads the round page again, the schedule knows no next round. Only the
fixtures' weekly cadence brought it back to that page, so after round 12 it would have looked again only after round 13
had locked: no lineups, no odds and no alerts for round 13, and quite possibly no round 13 at all. The fixtures are now
due once a day, whatever is stored, so the schedule stores the next round within a day of the site showing it. One
number changed in the product's code. Player names and the owner's league aren't reproduced here: the real-data numbers
are times and counts.

## What the slice delivered

| Task | What | Pull request |
|---|---|---|
| Spec | The requirements, approved 2026-11-25; the design and tasks, approved 2026-11-26 | #172, #173 |
| 1 | The fixtures daily in `web/cadence.py`; the tests written first; two earlier tests that said weekly; `mvp-collect` R7.1 marked as amended; the player guide | #174 |
| 2 | The check on a copy of the owner's lake, the faults made by hand, and this report | this one |

What building it found, each settled in its task:

- **An unchanged page is stored again after 14 days** (the design). `mvp-store` keeps an unchanged page's facts inside
  the answers' 14-day window by storing them once more. So AT-3's "nothing new" means no fact that wasn't stored before,
  and its test checks the payloads' hashes, not the number of stores.
- **One read a run needs a run with several facts due** (task 1). In the two hours before a deadline only the official
  lineups are due, so AT-4's test runs through the whole last day before round 10's, where the lineups, the odds and the
  fixtures fall due together.
- **The first full gate failed one timing budget** (task 1): `mvp-rules` AT-12, 3.33 s against 3.0. I was running the
  deliberate faults beside it on four workers. This slice doesn't touch the code it times, and it passed alone and in a
  second full run.

## Real data

Round 13, before the slice:

- The schedule last read the round page on 21 November at 14:13 Rome, 47 minutes before round 12's deadline. Its next
  read was due on 28 November at 14:14, after round 13's deadline (27 November, 20:45).
- On 26 November at 19:48 Rome, on the owner's yes, `fantadamus collect` was run by hand in the owner's folder. It
  stored round 13's 10 fixtures, the odds of all 10 matches and 1,641 outlet views, and the schedule knew round 13 from
  then on, 57 minutes before its alert window opened.

AT-7, on a copy of the owner's lake and collection log in this worktree's git-ignored `data/local`, nothing fetched and
nothing written to the owner's folder:

- **The replay.** On the copy as it stood before the read by hand (26 November, 18:00 UTC), `what_is_due` minute by
  minute from round 12's deadline. With `main`'s code from before the slice, the round page is next due on Saturday
  28 November at 13:14 UTC, 17 hours 29 minutes after round 13's deadline. With task 1's, on Sunday 22 November at
  13:14, five days and six and a half hours before it.
- **Every answer.** The 77 questions of `tests/real_lake.py`, recorded with `main`'s code from before the slice and asked
  again with task 1's: 77 identical, field by field. That covers every logged question at its own time; the lineup, the
  overview, two cards, two comparisons and four outlooks at five times; an alerts' check; and the reviews of rounds 11
  and 12. As expected: no answer's code changed.

The copies were deleted afterwards.

## Numbers

| Measure | Value |
|---|---|
| Tests | 1,782: 1,772 passed and 10 skipped without the private data, as in CI (1,760 before the slice) |
| Coverage | 98.8% of lines and 96.1% of branches; the floor is 90% |
| `make check` (19 checks) | About 8 minutes on the owner's Mac, 19 of 19. A first run, with the deliberate faults beside it, failed one timing budget (see above) |
| CI per pull request | This slice's: 377 and 391 s for the requirements, 291 s for the design, 388 s for task 1. **Median of the last ten 364 s, against the 300 s budget**, six over it |
| Code | 17,709 lines of product code, unchanged: one line and the module's table changed. 637 lines of new tests, and two earlier tests changed |
| Agent prompt | unchanged |
| Dependencies | none added |

## Faults made by hand

`_ALWAYS` is data, which `mutmut` doesn't change, and `due` itself didn't change, so the check is faults made by hand, in a
scratch copy, each run against the slice's tests:

| Fault | Caught by |
|---|---|
| The fixtures back to a week | 16 tests: AT-1 to AT-5, P1, P2 and the cadence table |
| 25 hours | the same 16 |
| 23 hours | 7: AT-1, AT-2's three cases, AT-4's switch, the cadence table and the two-pages test |
| The rule not chosen: a stored round ahead puts the fixtures back to weekly | AT-1, and AT-2's case with a later round stored by hand |

## Acceptance tests

| Test | Proves | Result |
|---|---|---|
| AT-1 | Across a deadline, the next round is stored at the first run 24 hours after the last read, its fixtures alone, and its lineups and odds then keep today's cadence | Passed |
| AT-2 | No stored fixture holds the read back: the locked round's later matches, a postponed match, a later round stored by hand | Passed |
| AT-3 | Three weeks of the same round: read each day, never twice in 24 hours, nothing new; the next round once the page moves on | Passed |
| AT-4 | A failed read is due at the next run, the site's answers wait 24 hours; once a run, robots.txt first, a second apart; nothing when switched off | Passed |
| AT-5 | A Saturday round, then a Tuesday one: the second is known before its alert window, and an official lineup sends its alert | Passed |
| AT-6 | Every other fact's cadence and an answer's own reads, against the specs written out again | Passed |
| AT-7 | On a copy of the owner's lake: the read due on 22 November, not on the 28th; every answer identical | Passed: 22 November at 13:14 UTC instead of the 28th; 77 of 77 identical |
| AT-8 | No new dependency; the docs say daily | Passed |

P1 and P2 hold: the fixtures are due exactly when no answered read is in the last 24 hours, and the next round is read
within a day and a run of the page showing it.

## Cost

$0: no dependency, service or account. The schedule reads the round page three or four more times in a normal week, and
ten more in a break like November's, to some 45 a round.

## Open risks

- **A Mac that sleeps through a day** still reads the page only at its next run; Phase 3 moves the schedule off the Mac.
- **A later round stored by hand** (`fantadamus collect --round 20`, or a page Claude submits) is taken for the next round
  by an answer until the daily read stores the real one: at most a day. Not in this spec.
- **CI is over its time budget**: a 364 s median against 300. Making the gate faster is Phase 3's first step.

## Decisions for the owner

1. **Sign off this slice?** Recommendation: yes. Every acceptance test passes. On the copy of your lake the read is due
   five days before round 13's deadline instead of after it, and no answer changed. Your checkout already runs it.

## Next

Phase 3, in a new session, starting with the gate (the Phase 2 report's decision 1).
