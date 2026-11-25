# Slice report: `mvp-cameos`

2026-11-25 · After Phase 2, before Phase 3 · **Signed off by the owner on 2026-11-25** (task 4.4), with all three
decisions

A player who doesn't start can still come on and get a rating. One number, 0.5, stood for two different things: for a
defender or most midfielders, coming on *and* being rated; for a forward or attacking midfielder, coming on at all. Round 12
and the rounds before it show the first is nearer a quarter and the second nearer two thirds. Each kind of cameo now has
its own share. The first is calibrated to 0.239 on 255 players, with the owner's approval; the second waits for more
players. Player names and the owner's league aren't reproduced here: the real-data numbers are counts and scores.

## What the slice delivered

| Task | What | Pull request |
|---|---|---|
| 1 | `CAMEO_SHARE_PRICED` beside `CAMEO_SHARE`, both 0.5, and each player's kind of cameo passed where his chance of coming on is worked out. No number moved: 77 answers on a copy of the owner's lake are identical | #168 |
| 2 | Both shares fitted and checked on their own, each against 200 benched players of its kind; `CAMEO_RATED` held at the method's 60% and listed as waiting | #169 |
| 3 | The real proposal on rounds 10 to 12, and the owner's approval of one share | #170 |
| 4 | 0.239 in the constants, the calibration log's entry, what it moves on round 12, the docs, a mutation run and this report | this one |

What building it found, each settled in its task:

- **The next proposal would have been scored wrongly** (task 4). The check scaled a stored chance by `new share / today's
  share`, which holds only while the stored rounds were made with today's share. Once 0.239 lands, rounds 10 to 12 were
  made with 0.5. The chance is now worked out from the player himself: his chance of starting, and his kind's share of the
  rest. On rounds 10 to 12 that gives back all 779 stored chances exactly. The approved proposal isn't affected.
- **One earlier test said more than its design** (task 4). `mvp-rules` AT-7 says no starter brings more as captain than
  the one advised. The captain comes from the five starters with the highest keys (its design C6). On the calibrated share
  the sixth brings about a hundredth of a point more on the test round. See decision 2.
- **A benched forward's share** was named as the flat one in an earlier test, and 0.5 was written as a number in a few
  others. Each now names the share it means.

## The proposal and the approved value

`fantadamus recalibrate` on rounds 10 to 12, from stored facts only, no page read (2026-11-24):

| Share | Today | Fitted | Players | Where it wasn't fitted (Brier) | Proposed |
|---|---:|---:|---:|---|---|
| `CAMEO_SHARE`, flat cameos | 0.500 | 0.239 (90% 0.198 to 0.286) | 255 | round 11: 0.149 to 0.120; round 12: 0.134 to 0.111 | Yes, approved |
| `CAMEO_SHARE_PRICED`, priced cameos | 0.500 | 0.648 (90% 0.538 to 0.763) | 128 of the 200 it needs | round 11: 0.106 to 0.108; round 12: 0.133 to 0.151 | No |

The owner approved `CAMEO_SHARE` at 0.239 on 2026-11-24 ("Approve both").

**What it moves,** on round 12's stored facts from a copy of the lake, at the owner's last answer without an override, just
before the lock and a second before it:

- **The lineup:** the same formation, captain and eleven each time. 2 of 12 bench places change in the first, none in the
  others. The expected score falls by 0.35 in the first and 0.17 in the others, and each threshold's chance moves by at
  most 2 points: fewer substitutes are expected to be rated.
- **The cards:** of 294 players on the ten cards, no chance of starting moves and 149 values do, by 0.05 on average and 0.27
  at most. One card's likeliest scorers reorder.

## Numbers

| Measure | Value |
|---|---|
| Tests | 1,760, 10 of them skipped without the private data, as in CI (1,724 at the end of Phase 2) |
| Coverage | 98.8% of lines and 96.1% of branches; the floor is 90% |
| `make check` (19 checks) | 5.8 to 9.5 minutes on the owner's Mac, quiet to busy and on battery; one was cut off when the Mac slept |
| CI per pull request | 247 to 388 s over the last ten; **median 350 s against the 300 s budget**, seven over it (257 s and three when the Phase 2 report was written) |
| Code | 17,709 lines of product code (17,660 at the end of Phase 2), 2,506 of checks and hooks, 34,656 of tests |
| Agent prompt | unchanged |
| Dependencies | none added |

Each task broke its own code on purpose, or showed its tests red, before its report.

## Mutation testing

`make mutate` on the functions this slice added or changed, with its pure tests added to the mutation set's selection, on
2026-11-25:

- **The first run killed 183 of 186.** The survivors showed two gaps and one clamp that a valid share can't reach: a
  filter for who counts as having a priced cameo was written twice and tested once; nothing tested a share whose first
  round has nothing to score; and a chance was held at 1 by a bound nothing reached. The filter is now written once,
  and a test asks for each.
- **The second killed 182 of 182 (100%).** The second run has four mutants fewer, because the filter is written once.
- The functions that pass a player's share on (`combine`, `availability()` and their callers) aren't in the mutation set:
  they reach the lake or the tools, which `mutmut` can't fork. AT-1 and AT-2 are their check, and AT-2 was broken on
  purpose.

## Acceptance tests

| Test | Proves | Result |
|---|---|---|
| AT-1 | Each kind of cameo by hand, through `best_lineup`, before and after a share changes, and on an official bench | Passed |
| AT-2 | With both shares at 0.5, every answer on a copy of the owner's lake identical | Passed: 77 of 77; broken on purpose, 21 differ |
| AT-3 | Both shares fitted by hand, with samples and intervals; `CAMEO_RATED` held | Passed |
| AT-4 | Held out by round and by half a round; a share below its minimum isn't proposed and says how far it is; rounds made with another share | Passed |
| AT-5 | The proposal lists both shares and changes nothing | Passed; the real one above |
| AT-6 | Manual: the owner reads the proposal and approves or turns down each share | Passed: `CAMEO_SHARE` approved on 2026-11-24, `CAMEO_SHARE_PRICED` left to wait |
| AT-7 | An approved share is in the constants and the log, and what it moves on a round keeps every answer's shape | Passed |
| AT-8 | No new dependency; the method and the constants say what each share means | Passed |

P1 to P4 hold, with P3 restated for the changed check.

## Cost

$0. No dependency, service or account, and no page read. A proposal takes about two seconds.

## Open risks

- **The forwards' share isn't settled.** Even on these rounds one number for all of them makes the forecasts slightly worse, so
  the fix isn't only more players: a forward unlikely to start probably comes on less often than one who's nearly sure to.
  That is a question for a later recalibration.
- **The captain's pool** is the five starters with the highest keys, so a sixth can bring slightly more (decision 2).
- **CI is over its budget** (a 350 s median against 300). The five docs-only runs among the ten, on the same test suite,
  took 250, 270, 330, 353 and 387 s: that spread is the runners', so a single run says little, but the median of ten
  is over all the same. Making the gate faster is Phase 3's first step.
- **The owner's numbers change on the next restart:** the expected score is 0.2 to 0.35 lower than before, because
  substitutes were overrated. Claude Desktop runs the old code until it's quit with ⌘Q and opened again.

## Decisions for the owner

All three decided by the owner on 2026-11-25, as recommended ("Sign off, accept all"): the slice is signed off, the
earlier tests are accepted, and the captain's pool stays as it is.

1. **Sign off this slice?** Recommendation: yes. Every acceptance test passes, and round 12's lineup keeps its eleven.
2. **Accept the earlier tests that change with the value?** Recommendation: yes. The design lists all of them. The one
   you've already accepted is `mvp-recalibrate` AT-8's log entry. Four more keep every assertion and only name the share
   or hold a starting value: `mvp-collect` AT-12 (a forward's share by its own name), `mvp-recalibrate` AT-2 and AT-9, and
   `mvp-x-or-y` P2. The sixth, `mvp-rules` AT-7, keeps its share at 0.5 because its claim is wider than its design.
3. **The captain's pool: leave it, or widen it?** The captain and vice come from the five starters with the highest keys
   (`mvp-rules` C6), so a sixth can bring slightly more: about a hundredth of a point on the test round. Recommendation:
   leave it. Widening it to all eleven changes an approved design and costs time in each answer, for a gain too small
   to see. Say so if you'd rather have AT-7's claim hold for every starter.

## Next

Phase 3, in a new session, starting with the gate (the Phase 2 report's decision 1).
