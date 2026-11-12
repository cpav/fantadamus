# Slice report: `mvp-recalibrate`

2026-11-12 · Phase 2, the seventh slice · **Signed off by the owner on 2026-11-12**

Fantadamus now learns from the rounds it has scored. Each round keeps its evidence player by player, a proposal fits the
starting values on it and checks each one on a round or half-round it wasn't fitted on, and the owner approves what
changes. The first approved change, on rounds 10 and 11, calibrates the chance of starting and the yellow-card prior.
Player figures and the owner's league aren't reproduced here: the numbers below are aggregates.

## What the slice delivered

- **Calibration sets.** Each scored round keeps, privately beside its report, every player's raw consensus, each chance
  the model gave and what happened. A rebuild gives the same set, whatever order the facts were stored in.
- **A map for the chance of starting.** Fitted on the sets: ten buckets, each shrunk toward no change by its sample, then
  pooled where it goes down, so the map is monotone. It's applied where the outlets' consensus is formed, so every answer
  uses it alike, and an official lineup still settles the chance.
- **The cameo rates and the season's own rates.** `CAMEO_SHARE` from the benched defenders and midfielders, `CAMEO_RATED`
  from the attackers; the penalties per match, conversion and saves, and the yellow and red cards, from a statistics read
  and the table that count the same matches. Each with its sample and a 90% interval.
- **Checked where it wasn't fitted.** Each round held out in turn, or half a round's matches where only one round has the
  evidence, with the Brier score and the reliability gap before and after. A value is proposed only with its minimum
  sample and only if it helps everywhere it was held out.
- **What waits.** Every other starting value is listed with the evidence it needs and how much there is.
- **The market beside ours.** Each round's report also scores the match chances the cards show, from the odds before
  kickoff, against the score its keepers' rows give.
- **`fantadamus recalibrate`.** It prints the proposal and keeps it privately; it reads no page and never touches the
  constants. An approved value lands as a pull request with an entry in [the calibration log](../calibration-log.md).

## Real data

From Claude Code on `main`, from stored facts only, no page read:

- **The sets.** Rounds 10 and 11 rebuilt in 1.7 and 6.5 seconds, 538 players each, about 200 KB each. Their reports came
  out exactly as before, chance for chance.
- **The proposal** ran in about 2 seconds. Its first run showed five faults, fixed in PR 122 with a test each: the
  cameos had no held-out check, the statistics read was a round ahead of the table, a cameo rate pinned at its bound, the
  penalties' minimum counted matches instead of penalties, and a rate's own count was hidden.
- **Approved on 2026-11-12** (AT-10, "Approve both"):

  | Value | Today | Approved | Evidence | Where it wasn't fitted |
  |---|---|---|---|---|
  | `START_MAP` | no change | 25% → 8.5%, 33% → 19.6%, 44% → 37.6%, 91% → 92.5% | 1,033 players | Brier 0.117 → 0.116 and 0.104 → 0.099; reliability gap 0.069 → 0.048 and 0.089 → 0.064 |
  | `YELLOW_PRIOR` | 0.150 | 0.116 | 2,682 outfield appearances | a count: 90% between 0.106 and 0.126 |

- **What it moves,** on round 11's facts at its lock: a lineup keeps its formation and captain, one starter changes and
  the bench order with it, and the expected score rises by about a tenth of a point; on the ten cards, chances of
  starting move by 0.03 on average, none crosses 50%, and three cards reorder their likeliest scorers.
- **Not changed:** `CAMEO_SHARE` (0.248 fitted on 183 of the 200 players it needs; better where held out), the penalties
  (22 of the 30 they need), and the saved penalties and red cards, which the stored statistics reads don't count yet.
- **The market on round 11,** scored on its ten matches: a home win 0.178 against 0.240 for always guessing the average,
  an away win 0.142 against 0.210, a draw 0.205 against 0.210, a side's clean sheet 0.159 against 0.160; three goals or
  more and both teams scoring did worse than the average, 0.284 and 0.285 against 0.250 and 0.240. Ten matches say
  little; it's the yardstick for later rounds. Round 10 has no market set: no odds were stored before its kickoffs.

## Numbers

| Measure | Value |
|---|---|
| Tests | 1,340 (1,281 at the end of `mvp-cards`) |
| Coverage | 98.8% of lines and 95.8% of branches; the floor is 90% |
| `make check` (19 checks) | 4 to 5 minutes on the owner's Mac |
| CI per pull request | 2.7 to 4.6 minutes, median 4.3 over the last ten, against a 5-minute budget |
| Code | 14,105 lines of product code, 2,506 of checks and hooks, about 23,800 of tests |
| Agent prompt | unchanged |

Each code task broke its own code on purpose before its report: 7 to 14 faults by hand each, all caught in the end, and a
targeted mutation run on its new functions. Every gap those found got a test.

## Mutation testing

`make mutate` on the core modules (`engine/*`, calibration, the review, the cards and now the recalibration), on fast tests
only: **4,712 of 4,820 mutants killed (97.8%)**, against 3,620 of 3,721 (97.3%) at the end of `mvp-cards`. The run reached
4,549 mutants in its 10-minute limit; the last module, the simulation, was run again on its own, fresh, in 3 minutes.

- **This slice's code** adds about 1,100 mutants and 5 survivors, each equivalent: pooling equal rates or not, the last of
  a two-knot tuple read from either end, two rates exactly equal, the two goal chances always set together, and a default
  of 1 for 0 that only matters when it isn't `None`.
- **The rest** are the survivors read in earlier slices, in the simulation, the review, the older calibration code and the
  engine, all harmless.

## Acceptance tests

| Test | Proves | Result |
|---|---|---|
| AT-1 | A round's set rebuilt the same way, whatever order its facts were stored in; its counts match the report; ratings without starting counted | Passed |
| AT-2 | The starting map by hand: monotone, shrunk where a bucket is thin, applied where the chance is formed; an official lineup still settles it | Passed |
| AT-3 | The cameo rates by hand, with their samples; one share that doesn't fit both kinds of cameo is named | Passed |
| AT-4 | The season's rates by hand; a read without the newer columns or a table names what it can't count | Passed |
| AT-5 | A value below its minimum isn't proposed, and says how far it is; what waits, for every constant | Passed |
| AT-6 | Held out by round, by half a round's matches, and where the evidence is; a change that doesn't help isn't proposed | Passed |
| AT-7 | The market's match chances by hand, beside the players'; old reports still read | Passed |
| AT-8 | The command changes nothing and lists each value with its evidence; an approved change and its log entry | Passed |
| AT-9 | What an approved change moves on a round's lineup and cards, with the shape of every answer the same | Passed; on round 11's facts too |
| AT-10 | Manual: the owner reads the proposal and approves or turns down each value | Passed: both values approved on 2026-11-12 |

## Cost

$0. Nothing runs on AWS, no paid service was added, and the slice's code reads no page. A proposal takes about two
seconds; a round's set adds about 200 KB to the private calibration folder.

## Open risks

- **Two rounds is little.** The map's held-out gain on round 10 is small (Brier 0.117 to 0.116), though its reliability
  gap improves more. Round 12 adds a third round to fit on and check against.
- **One share doesn't fit both kinds of cameo.** Benched attackers got a rating about twice as often as benched defenders
  and midfielders, so `CAMEO_RATED` can't be fitted. Rated games alone can't separate it from the share; a separate share
  for attackers' cameos would. The owner hasn't decided.
- **The statistics reads lack saved penalties and red cards.** The last stored read, on 9 November, came before those
  columns were read. The next read brings them.
- **Nothing has been collected since 9 November.** The table was last stored on 4 November, so the season's rates are
  counted on round 10. Fantadamus reads the table itself from `mvp-cards` on, at a question or a scheduled run, once
  Claude Desktop is restarted on the new code.
- **Replays use today's values.** A review of round 11 is now worked out on the calibrated map, so it can differ a little
  from what was told then. The method and the player guide say so, and the decision log keeps what was told.
- **Hand-worked tests pin the starting values.** Twenty test modules opt into a `start_values` fixture; the calibrated
  values are tested against the log and through the tools. The next calibrated constant must join the fixture, or the
  tests that assume its starting value fail, loudly.
- **The answers' thresholds now read calibrated chances.** A doubtful starter (below 80%) or a rotation risk (below 60%) is
  judged on the mapped chance: on round 11 one player fewer was flagged as doubtful.
- **CI is creeping up:** 4.6 minutes on the slowest run, median 4.3, against a 5-minute budget.
- **Claude Desktop must be restarted** for the calibrated values to reach the owner's answers.

## Decisions for the owner

1. **Sign off this slice?** Signed off on 2026-11-12. Every acceptance test has passed, AT-10 with the approved values.
2. **A share for each kind of cameo?** Recommendation: yes, as the first change of the next recalibration: amend R3.1
   to fit attackers' cameos with their own share in place of `CAMEO_RATED`, and propose both once round 12 is scored,
   about Tuesday 24 November, when the cameos also pass their minimum.
3. **What comes next?** Recommendation: the new-sources slice, research first (rest days and European fixtures, injury
   detail, per-match ratings and rater bias, anytime-scorer odds), since every source needs its route approved before any
   code.

## Next

The slices left before going online, in `product.md`'s order: new sources, then alerts on the Mac. Then the full review
with Fable 5.2, and Phase 3: online, with nothing to install.
