# Slice report: `mvp-review`

2026-11-10 · Phase 2, the second slice before going online · **Signed off by the owner on 2026-11-11**, with AT-8 closed
from here on round 11: "let's try to use available data from previous rounds and close them all and move on to the next
slice"
(tasks 8.2 and 8.4)

After a round, a player can ask how it went: what they fielded against the advice, what each choice was expected to cost when
it was made, what it really did, and whether their overrides pay off over the season. Player figures, names, scores and the
owner's lineup aren't reproduced here: they stay in private notes.

## What the slice delivered

- **Three more columns of the statistics page** (fantasy average, saved penalties, red cards), read from the page already read
  daily. Rows stored before them stay valid.
- **One player's round from two reads.** The statistics page read before and after a round gives each player's rating and
  events. The rating comes from the averages, pinned to its half point, with the fantasy average settling it late in the
  season and showing an own goal. A round that can't be worked out says why: two matches between the reads, a corrected
  figure, a rating on no half point.
- **The real score, the way the league scores it:** the league's table, its substitutions on real ratings, its formula rules
  and captain on real votes, and its thresholds. A player who can't be scored makes the score unknown, by name.
- **What the user fielded, and the advice.** The fielded lineup is kept privately, by name or "as advised", and refused with
  the reason when the league couldn't field it. The advice is the last lineup the user was given before the lock; if they asked
  for none, it's replayed at the lock and marked so.
- **Each decision and what it cost:** a player in another's place, the formation, the bench and the captain, each priced over
  one shared simulation at the lock's facts and judged by its expected cost. The real result sits beside it as one round's
  outcome, never in its place.
- **The record:** each review appended to a private log with its snapshots, and whether overrides pay off, saying when it's too
  early to tell and when it's still mostly luck.
- **The answer and the docs:** `review_round`, format 7 in [`answer-formats.md`](../answer-formats.md), a review section in the
  agent prompt, a paragraph in the player guide and a line in method §A8.

## Real data

Round 11 reviewed from Claude Code, on a copy of the owner's local data, with no collection and temporary stores and logs
(task 8.1).

- **The first run found a real bug, fixed in PR 99.** The review couldn't price the squad at all. At the moment it priced, some
  facts were past their freshness targets, and the advisor treats those as unknown. Freshness targets decide when to read a
  page again, not what was known, so a review now takes the newest facts stored before the lock, whatever their age. That also
  restored the design's pricing at the lock: a choice made on news read after the advice is priced on that news.
- **The same run showed the replay was slow:** 3.2 s, against a 3-second budget. It gathered the squad's facts twice, once to
  replay the advice and once to price the choices. Now it gathers them once.
- **After the fix, three reviews of the same round.**
  - *As advised.*
  - *As the owner really fielded it.* The lineup differed from the advice in one place, a defender. The review priced that
    choice as a coin flip, and in the real result it gave nothing either way.
  - *With no advice logged.* The advice is replayed at the lock. It differs a little from the advice the owner was given,
    which came from a server still running older code.

  All three used the statistics read two days before the round and the read the day after its last match, and 50 snapshots
  of the facts stored before the lock. The real score fell inside the forecast's range each time.
- **What round 11 can't count:** red cards, saved penalties and own goals. Its reads were stored before the three new
  columns, as the design expected, and each review names them as not counted.

| Review, in CPU seconds | Time | Size |
|---|---:|---:|
| Round 11 as advised | 1.2 s | 0.6 KB |
| Round 11 as fielded | 1.2 s | 0.8 KB |
| Round 11 with the advice replayed | 1.75 s (3.2 s before the fix) | 0.6 KB |
| The invented round of AT-7, with an advice and replayed | 0.5 s and 1.0 s | under 15 KB |

### AT-8: closed on round 11, from here

At the owner's request (2026-11-11), AT-8 was taken on round 11 rather than waiting for round 12. Round 11 is the only round
with statistics reads on both sides: the lake holds reads from 4 and 9 November only. The review rebuilt the round from
those two reads, the owner's real lineup and the logged advice, three ways (above).

The one part only the owner holds is the league app's total for round 11, which the owner's own notes don't record. That
cross-check stays open: the owner gives the number, and every review asks for the user's total and flags a gap of more
than half a point.

## Numbers

| Measure | Value |
|---|---|
| Tests | 1,215 (1,129 at the end of `mvp-rules`) |
| Coverage | 98.7% of lines and 95.5% of branches; the floor is 90% |
| `make check` (19 checks) | about 4 minutes on the owner's Mac |
| CI per pull request | 2 to 4 minutes, against a 5-minute budget |
| Code | 11,936 lines of product code, 2,506 of checks and hooks, about 20,300 of tests |
| Agent prompt | 12,754 characters, against a 13,000-character budget |

Each code task broke its own code on purpose before its report:

- **Tasks 2 to 6** used targeted mutation runs: 1,086 of 1,123 mutants killed, every survivor read and found harmless.
- **Task 7 and the gate's fix** were broken by hand: 20 faults, all caught once the three gaps the first run found were filled.

## Mutation testing

`make mutate` on the core modules (`engine/*`, calibration and now the review), on fast tests only, within its 10-minute
limit: **3,166 of 3,266 mutants killed (96.9%)**, against 2,138 of 2,205 (97.0%) at the end of `mvp-rules`. The engine and
calibration have 67 survivors, as many as before; the review module adds 33, all read in its tasks.

Every survivor was read, and none changes a result:

| Survivors | Why they're harmless |
|---:|---|
| 37 | `strict=` on a `zip` of lists that are always the same length |
| 19 | `<` against `<=` on a random draw, a bound or a float tolerance, where a tie doesn't arise |
| 11 | A starting value reset each round, marks built and then dropped, or a cache made weaker |
| 10 | Conditions on fields that are always set together, or a guard that's always true where it's reached |
| 8 | A default that can't be reached, or rows that always come in order |
| 6 | The captain's path: an argument it never reads, or a vice without a captain |
| 5 | Odds arithmetic normalised right after, or a tail too small to matter |
| 4 | A keeper's term multiplied by zero, since a keeper has no cameo |

## Acceptance tests

| Test | Proves | Result |
|---|---|---|
| AT-1 | A fielded lineup by name or as advised, one the league couldn't field refused, and saving again replacing it | Passed |
| AT-2 | One round from two reads, by hand, and each reason a round can't be worked out | Passed |
| AT-3 | A real score by hand: substitutions, the table, formula rules and the captain on real votes, the thresholds | Passed |
| AT-4 | Each decision with its expected cost and its real result, judged by the cost | Passed |
| AT-5 | Following the advice, against the expected score and its range; the advice replayed when none was asked | Passed |
| AT-6 | The record over several rounds, append-only, saying when it's too early to tell | Passed |
| AT-7 | The review in its format, within 3 seconds and 15 KB, from no new page | Passed; on a real squad too (above) |
| AT-8 | Manual: the owner's real round reviewed, and its real score checked against the league's app | Passed on round 11 from here; the app's total still to compare |

## Cost

$0. Nothing runs on AWS, no paid service was added, and no new page is read. A review uses the player's own Claude plan.

## Open risks

- **The league's app may score differently.** A substitution the app makes another way, an own goal the reads can't pin, a
  late correction. AT-8 is the first check; the user's app total beside every review keeps checking.
- **Some events can't be read.** A decisive goal and a set-piece assist have no column; an own goal shows only where the
  fantasy average pins it. Each review names what it couldn't count.
- **The record needs many rounds.** One review a week gives a wide margin for most of a season, so the record will mostly say
  "too early" or "mostly luck". That's honest: one round is mostly luck.
- **A squad that changed since the round.** The advice's players are still priced, but a fielded player nobody knew before
  the lock can't be, and the review says so. A keeper listed for the first time after the round makes his club's goals
  against unknown for that review.
- **Players must paste the new agent prompt and restart Claude Desktop.** A running server keeps its old code until then.

## Decisions for the owner

1. **Merge PR 99, the fix?** Recommendation: yes. Round 12's review needs it.
2. **Sign off this slice after AT-8 on round 12?** Signed off on 2026-11-11, with AT-8 taken on round 11 from here.
3. **What comes next?** Recalibration waits for round 12 to be scored, and AT-8 waits for round 12 too. Recommendation: start
   the match cards' requirements meanwhile, since they change no numbers, and take recalibration once round 12 is scored.

## Next

The slices left before going online, in `product.md`'s order: recalibration, match cards, new sources, alerts, and the rules
that need the opponent's team. Then Phase 3: online, with nothing to install.
