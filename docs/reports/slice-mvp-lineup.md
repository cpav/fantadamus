# Slice report: `mvp-lineup`

2026-11-07 · Phase 2, slice (c) · **For the owner's sign-off** (task 9.6): merging this report's pull request records it

The owner decided not to wait for round 11 to be scored. Phase 2's gate asks for a calibration report on at least one real
round, and [round 10's](calibration-round-10.md) exists, so no gate is weakened. Player figures, names and the answers' numbers
aren't reproduced here: they stay in private notes.

## What the slice delivered

- **Squads and the league's full rules,** set from a blank league profile any player can fill in: thresholds, bench,
  substitutions and formations. A league-mate's squad is kept apart under its team name.
- **`best_lineup`:** the eleven, the bench in order for each role and the formation, simulated to give the expected score and
  the chance of each threshold.
- **Overrides and calls:** forcing a player or a formation returns that lineup with what it costs. A choice is labelled by
  what it's worth, so "clear" means clear.
- **A round scores itself:** the decision log, then both scored sets (what users were told, and the model on everyone),
  with what couldn't be scored and why.
- **Corrections to the model, found while testing:** a forward's cameo priced by the method's three outcomes; a taker's
  penalties counted once; and a penalty taker's credit following who will really take them.
- **Penalty takers watched:** the collector reads the page daily, and answers name a changed order and a list that
  disagrees with who has really taken them.
- **`make mutate`:** a mutation run in under 4 minutes, replacing runs that took far too long.

## The real round

Round 11, on a real squad and real rules.

**AT-13.** The owner's own eleven matched the advice in 10 of 11 places, with the same formation. The one difference was a
defender the tool itself called a coin flip. The bench order matched too, apart from that swap and two forwards almost level.

**Each kind of answer,** on the real data:

| Answer | Time | Size |
|---|---:|---:|
| A draft, or a check after the first match's official lineup, on fresh facts | about 2 seconds | about 12 KB |
| The same on stale facts, with every warning showing | about 3 seconds | about 15 KB |
| An override, on stale facts | about 3 seconds | about 15.5 KB |
| A league-mate's squad, on stale facts | about 3 seconds | about 15 KB |

Each used the round page, the statistics page, the penalty takers and the table. AT-9's budget is 3 seconds and 15 KB, so the
worst case sits at the limit, a little over it on size.

### Checked against the owner's playbook

The owner's private playbook works the same method by hand, so round 11 could be compared with an independent run of it,
as things stood at the lock:

- **The same formation and 10 of the same 11 starters,** with the same coin flip for the third forward falling the same way.
- **Expected score within 0.1 of a point,** and the chance of the second threshold within about 1 point. Fantadamus is about 5
  points lower on the chance of the first threshold, because its simulated spread is wider.
- **The one different starter** is a defender Fantadamus credited with a first taker's penalties, which is the term the
  calibration report questions.

The playbook also confirms the stored league rules. Its forecasts against results are in the calibration report.

### Not tested on real data

- **Official lineups,** beyond the round's first match: the others weren't out when this was written.
- **Scoring, ratings and clean sheets:** round 10 can only score the chance of starting.
- **The new takers read and the shared log reader in Claude Desktop,** rather than through the tools from Claude Code.
- **A second player's Mac:** that gap was accepted in the last slice, and Phase 3 removes the need for it.
- **The scheduled run:** it isn't installed on the owner's Mac.

## What testing on real data found

Each has its own failing test and fix, listed under task 9.1 or as tasks 10 to 12.

- The round page names whichever side of 3 goals is likelier, and the reader knew only one wording. That lost the over/under
  for about two matches a round, and answers said the page didn't carry it.
- A first taker who was out took his club's penalties with him; a change to the list went unreported; and the list could
  disagree with who had taken them.
- A taker's penalties were counted twice, in his goal share and in his penalty term.
- A forward's cameo with no rating was priced as a low score, although his substitute comes in.
- One line a log couldn't read stopped every answer, as did a line from a newer version.
- A long pause between reads, and several writers at once, could leave an answer without facts or damage a file.
- A failed or damaged robots.txt read could stop the collector for a day.
- The formation call could contradict the keys without saying why.
- Calibration counted a page stored again as the read after a round, and a what-if as an override.

## Numbers

| Measure | Value |
|---|---|
| Tests | 1,039 (631 at the end of the last slice) |
| Coverage | 98.7 95.4% of lines and % of branches; the floor is 90% |
| `make check` (19 checks) | about 3 to 4 minutes on the owner's Mac |
| CI per pull request | 2 to 3 minutes, against a 5-minute budget |
| Code | 9,558 lines of product code, 2,506 of checks and hooks, about 16,700 of tests |
| Answer | at most about 15 KB, or about 5,000 tokens of the user's Claude plan |

## Mutation testing

`make mutate` on the core modules (`engine/`, `domains/calibration.py`), on fast tests only: **1,658 of 1,702 caught (97.4%)**, in
under 4 minutes. All 44 survivors were read, and none is a real gap:

| Survivors | Why they're harmless |
|---:|---|
| 11 | `<` against `<=` on a random draw or a bound, where a tie doesn't arise |
| 12 | `strict=` on a `zip` of lists that are always the same length |
| 10 | A default that can't be reached, one falsy value swapped for another, or a condition another already covers |
| 5 | Odds arithmetic normalised right after, or a tail too small to matter |
| 6 | A zero that's overwritten, or multiplied by zero before use |

The run found one real gap, now closed: two keepers who are both out had no test. Another survivor looked like a gap, but
the rows are already sorted.

## Acceptance tests

| Test | Proves | Result |
|---|---|---|
| AT-1 | Method §A9 test 1: sorting by the key is optimal over every ordering of random squads | Passed |
| AT-2 | Method §A9 test 5: a goal against your own keeper nets what it should, and the link narrows the spread | Passed |
| AT-3 | The league's substitution rules | Passed |
| AT-4 | Thresholds convert to fantasy goals; a hand-worked chance | Passed |
| AT-5 | The formation falls out of the marginal players | Passed |
| AT-6 | The bench in key order; two keepers of one club | Passed |
| AT-7 | `set_squad`, and a league-mate's squad | Passed |
| AT-8 | The setup step for just the missing settings | Passed |
| AT-9 | The same facts give the same lineup; 3 seconds and 15 KB | Passed on the test squad; see above for real data |
| AT-10 | An override's cost; a rule left out is named | Passed |
| AT-11 | A choice labelled by what it's worth | Passed |
| AT-12 | A round scores itself, with both sets | Passed |
| AT-13 | Manual: a real lineup compared with the owner's own | Passed: 10 of 11 places |
| AT-14 | A lineup without over/under, with a warning | Passed |
| AT-15 | The blank league profile | Passed |
| AT-16 | A forward's cameo | Passed |
| AT-17 | A taker's penalties counted once | Passed |
| AT-18 | The next taker gets what the first leaves | Passed |
| AT-19 | The collector reads the takers | Passed |
| AT-20 | A changed order, and the list against the record | Passed |
| AT-21 | The note follows the official lineup | Passed |

**Method §A9 is complete:** tests 1 and 5 pass here, and tests 2, 3, 4 and 6 passed in earlier slices.

## Cost

$0. Nothing runs on AWS and no paid service was added. A question uses the player's own Claude plan.

## Open risks

- **The penalty term looks too generous** (calibration report). It can move a marginal starter until it's fixed.
- **Only the chance of starting has been scored on real data,** and that only if a finished page keeps the outlets' last
  percentages, which round 11 can show.
- **Round 11 needs a nudge.** With no schedule installed, a question or `fantadamus collect --due` has to run after it finishes
  and before round 12 starts.
- **A player unlikely to start can rise on his key alone.** The method allows it, because the bench covers him, and the tool
  calls it a coin flip. Worth watching in the calibration reports.
- **A running server keeps its old code until Claude Desktop restarts.** On round 11, one answer came from code older than
  the latest fix. It didn't change the lineup. Phase 3 removes this for players.
- **The answer is at its size limit on stale facts.**

## Decisions for the owner

1. **Sign off this slice?** Recommendation: yes. The gate is met, and the playbook agrees with the tool on all but one starter.
2. **Keep the defence modifier and captain before going online?** The owner's league uses neither, and the second player's
   rules aren't known. Recommendation: move them to the further notes unless the second player's league needs them.
3. **Which slice comes next?** Recommendation: recalibration first, starting with the penalty term, because it can change
   next round's lineup. The lineup review and the match cards change no numbers, so they lose nothing by following it.

## Next

The owner took live forecasts and pundit consensus out of scope (`product.md`, Further notes). The slices left before going
online are the lineup review, match cards, recalibration, the defence modifier and captain, new sources, alerts, and the rules
that need the opponent's team with Mantra. Then Phase 3: online, with nothing to install.
