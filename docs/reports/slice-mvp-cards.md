# Slice report: `mvp-cards`

2026-11-11 · Phase 2, the third slice before going online · **Waiting for the owner's AT-11 on round 12, then sign-off**
(tasks 8.2 and 8.4)

A player can now ask about a match and get it on one screen: the odds as plain chances, the goals and clean sheets, both
likely elevens and how sure they are, who's out, the penalty takers, the likeliest scorers and their own players in it,
first. Or the whole round at a glance. Player figures, names and the cards' numbers for a real round aren't reproduced
here: they stay in private notes.

## What the slice delivered

- **The table's record and form.** Each club's wins, draws, losses and last five results, kept from the table page.
  The form shows as coloured dots that the page's text doesn't carry, so Fantadamus now reads the table itself, daily, as
  it reads the statistics and takers pages of the same site, with Claude as the fallback.
- **The match in numbers.** Each side's chance to win and the draw, expected goals and clean sheets, three goals or more and
  both teams to score where the odds price them, and how far apart the odds pages are. Without odds, team form stands in.
  The season so far is shown beside them and never moves a number.
- **The lineups.** Each side's likely eleven with how sure it is, the official one once it's stored; the disputed starting
  places, naming the outlets on the smaller side; who's out, "listed as out by N outlets".
- **What it means for each player.** His chance of starting and of scoring, his share of his side's goals, a keeper's
  clean sheet, what he's worth; the five likeliest scorers; the penalty takers with their record; rotation risks; and the
  user's players first. Points follow the stored rules, or Classic's without any, so a live-chat viewer needs no setup.
- **`match_card` and `round_overview`.** A card is priced the way `player_outlook` prices each player, so the two agree for
  every player; it's logged for the calibration. The overview is team-level only and logs nothing. Format 5 in
  [`answer-formats.md`](../answer-formats.md) is the card as built; each tool's description carries its rendering rules,
  and the agent prompt gains one line.

## Real data

Round 11's ten matches, as they stood at its deadline, and its overview a second before the lock: from Claude Code, on a
copy of the owner's local data, with no collection and a temporary log (task 8.1).

- **The first run found the cards too big and too noisy, fixed in PR 110.** The outlets give percentages without
  ballottaggi, and they disagreed about some 20 players a match, most of them on the bench. Each became a "disputed
  place", so cards ran to 17 KB, past the 15 KB budget, with up to 14 rotation risks. A disputed place is now a starting
  place, as the requirements' glossary said: a ballottaggio with a likely starter in it, or the likely starters of a role
  the outlets disagree about, set against the next in line. A rotation risk is a usual starter under 60%.
- **After the fix,** every card had both elevens, its penalty takers, five scorers and the odds, and none was logged, as
  a past-deadline card shouldn't be. The match whose official lineups were stored by the lock had no disputed places, as
  it should.
- **The form wasn't there:** nothing has read the table since Fantadamus started reading it (PR 103). It appears after
  the next collection.

| Round 11, in CPU seconds | Before the fix | After |
|---|---:|---:|
| A card | 1.8 to 2.4 s | 1.4 to 1.9 s |
| Its size | 9.3 to 17.3 KB | 8.3 to 13.2 KB |
| Disputed places, both sides | up to 26 | 3 to 6 |
| Rotation risks | up to 14 | 1 to 7 |
| The overview | 0.3 s, 3.4 KB | 0.3 s, 3.4 KB |

The invented round's card takes 0.2 s and its overview 0.07 s (AT-10).

### AT-11: the owner's round 12

Not run yet. Round 12 locks on Saturday 21 November, at 15:00 if the calendar holds. After merging PR 110, restart
Claude Desktop and re-paste the agent prompt; before the deadline, ask your Claude app "Tell me about" a match or two and
"Where are the goals this round?", and check the cards against the round page.

## Numbers

| Measure | Value |
|---|---|
| Tests | 1,281 (1,215 at the end of `mvp-review`) |
| Coverage | 98.7% of lines and 95.5% of branches; the floor is 90% |
| `make check` (19 checks) | about 4 minutes on the owner's Mac |
| CI per pull request | 2 to 4.3 minutes, against a 5-minute budget |
| Code | 13,156 lines of product code, 2,506 of checks and hooks, about 21,900 of tests |
| Agent prompt | 12,911 characters, against a 13,000-character budget |

Each code task broke its own code on purpose before its report: mutation runs on the pure parts, and faults by hand on the
tools and the collector. Every gap the first runs found got a test, and the only survivors left are equivalent.

## Mutation testing

`make mutate` on the core modules (`engine/*`, calibration, the review and now the cards), on fast tests only, within its
10-minute limit: **3,620 of 3,721 mutants killed (97.3%)**, against 3,166 of 3,266 (96.9%) at the end of `mvp-review`.

- The engine, calibration and review keep the same 100 survivors, all read in earlier slices and harmless.
- The cards module adds about 450 mutants and one survivor: a `<=` against `<` on two counts already known to differ, so
  it can't change a result.
- Each of tasks 2 to 6 and the fix first ran its own new functions. Those runs found real gaps every time, each now
  tested: a line's numbers with no fast test, interleaved ballottaggi, a rival written another way, rotation at its edges,
  a player out everywhere as next in line.

## Acceptance tests

| Test | Proves | Result |
|---|---|---|
| AT-1 | A card by two clubs or one, with its context line; a club with no match; a round past its deadline | Passed |
| AT-2 | The numbers by hand, the spread between odds pages, and team form without odds | Passed |
| AT-3 | The table's figures and last five results shown, and no number moved by them | Passed |
| AT-4 | The lineups: a likely eleven, disputed starting places, who's out, the official lineups | Passed |
| AT-5 | What it means, by hand: scorers, keepers, takers, rotation risks, the user's players first | Passed |
| AT-6 | Classic's points without stored rules; a league's own rules change the points, not the chances | Passed |
| AT-7 | The round overview in kickoff order, answering a question across fixtures | Passed |
| AT-8 | Every player's numbers on a card are `player_outlook`'s | Passed |
| AT-9 | Logged for the calibration and counted; a replay logs nothing | Passed |
| AT-10 | Within 3 seconds and 15 KB, from no new page | Passed; on a real round too, after PR 110 |
| AT-11 | Manual: the owner reads round 12's cards before the deadline | Waiting for round 12 |

## Cost

$0. Nothing runs on AWS and no paid service was added. The table is read daily by Fantadamus instead of weekly by
Claude, one page a day. A card is one gather of two clubs and no simulation.

## Open risks

- **The prompt's budget is nearly spent:** 12,911 of 13,000 characters. The next slice that needs words in it must find
  them elsewhere first, or move a tool's rules into its description, as this slice did.
- **A card's size on a busy round.** The largest real card was 13.2 KB. A round with more disputes, or a club with more
  players listed, could come close to 15 KB.
- **The outlets disagree a lot.** With four percentage outlets, a spread of 0.30 marks many players disputed. The cards now
  show only starting places, but the threshold itself is a *(start)* constant for the recalibration.
- **The next in line is a guess.** Without a ballottaggio, a disputed starter is set against the likeliest of his role
  outside the eleven, which may not be who the coach would pick.
- **Rest days, European fixtures, context and injury detail** wait for the new-sources slice; the card has their place.
- **CI is creeping up:** 4.3 minutes on the slowest run, against a 5-minute budget.
- **A random property failure, fixed in PR 111.** While this report's `make check` ran, Hypothesis found a case where a
  calibration bucket's mean chance fell a hair under the bucket's floor, by float rounding. It's an older module's, now
  fixed and pinned as an example; others like it may still be found the same way.
- **Players must paste the new agent prompt and restart Claude Desktop.** A running server keeps its old code until then.

## Decisions for the owner

1. **Merge PRs 110 and 111, the two fixes?** Recommendation: yes. Round 12's cards need the first, and the second keeps
   `make check` from turning red at random.
2. **Sign off this slice after AT-11?** Recommendation: yes, after you've read round 12's cards before its deadline on
   Saturday 21 November. The lineup review's AT-8 follows the same round, after it's played.
3. **What comes next?** Recalibration waits for round 12 to be scored, about Tuesday 24 November. Recommendation: start the
   new-sources slice's research meanwhile (rest days and European fixtures, set-piece takers, injury detail, context),
   since every source needs its route approved before any code.

## Next

The slices left before going online, in `product.md`'s order: recalibration, new sources, alerts, and the rules that need
the opponent's team. Then Phase 3: online, with nothing to install.
