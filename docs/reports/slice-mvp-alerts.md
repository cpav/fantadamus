# Slice report: `mvp-alerts`

2026-11-15 · Phase 2, the ninth and last slice before going online · **Signed off by the owner on 2026-11-18**,
with all three recommendations; AT-5 closes with round 12

When the news changes your lineup in the last day before a round, your Mac now says so, unasked. After a
scheduled run that stores a new official lineup, a probable lineup or an injury or ban, Fantadamus works the lineup
out again on the facts then, as `best_lineup` would, and compares its call (the eleven, the formation, the captain
and vice, each role's first bench place) with the one you last saw. A change sends one notification through
macOS's own `osascript`: what to change first, then why. Nothing is installed, no account is created, and no
number moves. Player names and the owner's league aren't reproduced here: the real-data numbers are counts.

## What the slice delivered

| Task | What | Pull request |
|---|---|---|
| 1 | The call, what changed, why, and the alert's text, as pure functions | #139 |
| 2 | The check after a scheduled run, the alert log under `data/local/alerts/`, `make_advisor` shared with `serve` | #140 |
| 3 | Sending through `/usr/bin/osascript`, `collect --due --user`, `fantadamus alerts` and `--test`, the switch in the private configuration, the budget | #141 |
| 4 | The docs, the real check, a mutation run, nine tests for its gaps, and this report | #142 |

Two things the tests found, fixed in their tasks:

- **A cause must explain the move.** The first end-to-end run explained a benched forward by "the official lineup
  starts him". Now a player who lost his place is explained only by being benched, out or less likely to start, and
  the one who took it only by starting or likelier to.
- **A mistyped switch** (`enabled = "false"`) stayed on silently. It still stays on, and the run's log now says why.

## Real data

From Claude Code on `main`'s code on 2026-11-15, reading the owner's lake and writing nothing:

- **Round 11's last day, replayed.** The window opened 24 hours before the lock. Five runs in it stored lineups or
  news, and the check, replayed at each, would have sent **4 alerts**:

  | When (before the lock) | Subtitle | Changes, by cause |
  |---|---|---|
  | 23 h 36 min | Probable lineups moved | a swap (probable lineups), a first-bench place |
  | 5 h 34 min | Probable lineups moved | a first-bench place (probable lineups) |
  | 1 h 46 min | Your call changed | a swap and a first-bench place, neither explained by one player's news |
  | 27 min | Official lineup out | a swap (official lineup), a first-bench place |

  Each was 53 to 159 characters, within the 240. The last is what the slice is for: an official lineup out 27 minutes
  before the lock, changing the eleven. No formation changed in round 11; on the synthetic round, whose four
  formations sit within 0.15 points, small news flips it, so a real round with near-tied formations would alert more.
- **Round 10:** the collection log has no run in its last day, so there was nothing to replay.
- The replay uses today's squad and rules.

## Numbers

| Measure | Value |
|---|---|
| Tests | 1,569 (1,479 at the end of `mvp-sources`) |
| Coverage | 98.8% of lines and 96.0% of branches; the floor is 90% |
| `make check` (19 checks) | 5½ to 7 minutes on the owner's Mac |
| CI per pull request | 3.1 to 5.1 minutes, median 5.0 over the last nine, against a 5-minute budget |
| Code | 16,837 lines of product code, 2,506 of checks and hooks, 28,437 of tests |
| A check after a scheduled run, all 10,000 simulated rounds | 0.73 to 0.99 CPU-seconds, the fastest of three on a quiet or busy Mac, against 10 |
| Agent prompt | unchanged: alerts don't go through Claude |

Each code task broke its own code on purpose before its report: 38 faults in all, every one caught in the end. One
survived at first: a switch written as text, now reported.

## Mutation testing

`make mutate ONLY='fantadamus.domains.alerts*'`, with the alerts' pure module and its fast tests added to the mutation
set, on 2026-11-15:

- **The first run killed 385 of 413 mutants.** Its 28 survivors showed eight gaps, each now with a test: the round in
  a call from a logged answer and in an alert's title; "2 more changes"; a lone change and the captain carrying their
  cause, the formation, vice and bench never; the text filling its limit exactly, with and without its cause; a cut
  first change still counting the rest; a fact read, or a squad saved, at the call's own instant.
- **After them, 403 of 413 are killed (97.6%).** The 10 left change nothing: `zip`'s default `strict`, a `<` where
  the two values can't be equal, and fallbacks for cases that can't happen (a swap without its two players, a bench
  change without its role).
- The check, the alert log and the command line go through the lake or the shell, which `mutmut` can't fork; their
  deliberate faults by hand are their check: 25 of 25 caught.

## Acceptance tests

| Test | Proves | Result |
|---|---|---|
| AT-1 | A scheduled run that stores an official lineup inside the window, benching a starter of the call, sends one alert naming him and his cover | Passed |
| AT-2 | Nothing sent: outside the window, after the deadline, without a squad, with the switch off, with no baseline, when only the chances moved, when nothing new was stored, or when the squad was saved since | Passed |
| AT-3 | The same change isn't sent twice; a change back is sent; another round's, user's or team's calls aren't compared | Passed |
| AT-4 | A check within its time: under a second with all 10,000 simulated rounds, against 10; nothing installed, no account | Passed |
| AT-5 | Manual: a notification on the owner's Mac | Half done: from `main`, `fantadamus alerts --test` was taken by macOS (exit 0); whether it showed, and a real alert in round 12's last day, are the owner's to see (decision 2) |
| AT-6 | The docs updated: answer formats, the player guide, `product.md` | Passed |

P1 to P5 hold: no alert outside the window or without the league; a call compared with itself has no changes, and
changes are empty both ways or neither; one alert for the same facts; a change back alerts again; every change named
or counted within 240 characters.

## Cost

$0, as estimated:

- No paid service, no account, nothing installed: macOS's own `osascript` shows the notification.
- A check is a lineup replayed on stored facts, under a CPU-second, and runs only after a run that stored lineups or news
  in the last day before a round: five times in round 11's.
- Nothing runs on AWS.

## Open risks

- **Alerts need the schedule.** The scheduled run (player guide, step 8) isn't installed on the owner's Mac, and an
  alert only follows a scheduled run. Until it is, nothing is checked.
- **Near-tied formations.** On the synthetic round, whose formations sit within 0.15 points, a small change of one
  chance flipped the formation and sent an alert. Round 11 had none, but a round with near-tied formations would
  alert more often, each time with a correct but small change.
- **The bench's first places** were 4 of the 7 changes in round 11's replay, and one alert was for the bench alone.
- **macOS names the sender Script Editor**, and a click on the notification opens Script Editor rather than Claude.
  `terminal-notifier` would fix both but needs Homebrew (decision 3 of the requirements).
- **CI is at its budget.** The median of the last nine runs is 298 seconds against 300. This slice added about
  twenty tests that go through the whole synthetic round, and AT-4 times a check with all its simulated rounds. The
  full review with Fable 5.2 is the moment to look for the slowest tests.
- **The Mac must be awake.** launchd skips the runs a sleeping Mac misses; an official lineup that comes out while it
  sleeps is read at the next run after it wakes, if the lock hasn't passed.

## Decisions for the owner

All three decided by the owner on 2026-11-18, as recommended ("Sign off all three").

1. **Sign off this slice?** Signed off on 2026-11-18. Every automated acceptance test passes, the real replay of round 11
   shows what the alerts would have said, and macOS took the sample notification. Only your own look at it (AT-5)
   is left, and it can close with round 12.
2. **Install the schedule and let the notifications through,** before round 12's window opens, 24 hours before its
   deadline. Only you can do it, since it changes your Mac's settings:
   - the player guide's step 8, with your name, `owner` as in Claude Desktop, and the folder your copy lives in
     wherever the block says `~/fantadamus`;
   - then `fantadamus alerts --test`, and allow Script Editor in System Settings → Notifications if the sample
     doesn't show.
3. **Keep alerting on the bench's first places?** Recommendation: yes for round 12, then look at the alert log. In
   round 11's replay they were four of seven changes, and one alert was for the bench alone.

## Next

Phase 2's slices are done. The review before Phase 3 ([`review-before-phase-3.md`](review-before-phase-3.md),
2026-11-16) led to `mvp-store`, signed off on 2026-11-18, after which the schedule can be installed. Still open with
the owner from the review: the gate changes (its decision 2) and Phase 3's platform (its decision 3).
