# Slice report: `mvp-collect` and `mvp-roles`

2026-11-04 · Phase 2, slices (a) and (b) · **For the owner's sign-off** (task 8.3 of each spec)

The owner deferred `mvp-collect`'s real round on 2026-11-03, so that both slices are tested together. This is
one report for both.

## What the two slices delivered

**`mvp-collect`: Fantadamus collects the round's facts itself.**

- A polite fetcher: the allowlist, robots.txt, one request a second per host, stopping when a host blocks.
- The round-page reader: fixtures, the outlets' chances of starting, official lineups and odds.
- `read_page` for every other page, which Fantadamus fetches and the user's Claude reads.
- `collect`, `fantadamus collect --due` and the launchd schedule, with a collection log.
- Forecast answers: confidence per chance, how it moved, when it was updated, and sources.

**`mvp-roles`: every role.**

- The statistics page, read by a second reader into one record per read: every player's season, once a day.
- The outfield model with each role's priors, and the method's keeper model (§A6).
- `compare_players` for any two players of one role. Two roles get two outlooks and no verdict; two keepers of one
  club come out as covered.
- `player_outlook`: one player's forecast for any role.
- The agent prompt, answer formats and guides for all of this.

## The real round

Round 11, before its lineups were official. Player figures and the answers' numbers aren't reproduced here: they
derive from third-party pages, and this repository is public.

| Who | How | What was asked | Result |
|---|---|---|---|
| Owner | Claude Desktop | "X or Y?" for keepers, defenders and midfielders | Answered; "successful" in the owner's words |
| The agent | The same MCP server, called directly from a Claude Code session | Every role; a covered pair; two roles; a player in the deadline match; a compound surname; a full name; a first name; a name matching two players | Answered as designed, apart from the findings below |

The record in the logs, for this round:

| Measure | Value |
|---|---|
| Decision log | 13 entries: 9 comparisons, 3 outlooks, 1 two-role answer |
| Collection log, all runs | 11 page reads by the collector: 6 stored, 3 unchanged, 2 unreadable (both fixed: PRs #39, #42) |
| Statistics page | Read and stored once; every player of 20 clubs, none left out |

### Not tested in a real round

These are covered only by automated tests:

- **An official lineup.** None is out until Friday 6 November (AT-5 of `mvp-x-or-y` and AT-1 of `mvp-collect`).
- **The second player's Mac.** `mvp-collect` AT-10 asks for it; it hasn't been run.
- **`player_outlook` in Claude Desktop.** The outlooks were asked from the agent's session.
- **The scheduled run.** No launchd run appears in the collection log.

## What testing on real data found

| Found by | Problem | Fix |
|---|---|---|
| Reading the saved real pages (task 2) | With every player known, an outlet's initial paired with another player's whole name, so 45% of a round page's names resolved | Whole words match whole words; 96.6% resolve, none ambiguously |
| Asking on the saved real pages (task 5) | A first-choice midfielder, whose compound surname the outlets write in part, came out as nobody-mentions at the low default, with a confident verdict against him | R4.4: a last resort among club-mates, disclosed in the answer |
| Calling the real tools (this report) | An unknown name, or a match whose odds show no over/under, read the same page again on every question | An answer leaves a page alone for 15 minutes (round page) or a day (statistics page) |
| Calling the real tools (this report) | `rivals` was always empty on percentage sheets, though the answer format names a rival | Inferred: two of one role, between 31% and 69%, making 100. A sheet's defaults don't count |

Breaking the code on purpose also found tests that couldn't fail. Those tests were strengthened (tasks 4 and 5).

## Numbers

| Measure | Value |
|---|---|
| Tests | 631 (487 at the end of Phase 1) |
| Coverage | 98.3% of lines and 94.0% of branches; the floor is 90% |
| `make check` (19 checks) | about 2 minutes on the owner's Mac |
| CI per pull request | 1 to 2 minutes, against a 5-minute budget |
| Code | 6,167 lines of product code, 2,506 of checks and hooks, 10,594 of tests |

## Acceptance tests

`mvp-roles`:

| Test | Proves | Result |
|---|---|---|
| AT-1 | Method §A9 test 3, at the method's own weights | Passed |
| AT-2 | The same skill behind different defences gives the same expected vote | Passed |
| AT-3 | The clean-sheet chance comes from the same fit as the odds | Passed |
| AT-4 | Each role's priors; forwards keep their numbers | Passed |
| AT-5 | Method §A9 test 6 for defenders | Passed |
| AT-6 | The statistics page collected, unchanged on a second read, and left for Claude when incomplete | Passed |
| AT-7 | Two roles get two outlooks and no verdict | Passed |
| AT-8 | Two keepers of one club are covered | Passed |
| AT-9 | `player_outlook` in one call | Passed |
| AT-10 | Manual: real questions in Claude Desktop | Passed for the three roles; the outlook was asked from the agent's session |

`mvp-collect`: AT-1 to AT-9 and AT-11 pass. **AT-10** (a real question on each Mac, before and after an official
lineup) is only partly done: the owner's Mac, before the lineups.

Method §A9: tests 2, 3, 4 and 6 pass. Tests 1 and 5 belong to the full lineup.

## Open risks

- **A surname match could be the wrong player**, such as a youth player the statistics page doesn't list. The answer
  says when it was used.
- **Rivals are inferred.** The page names no ballottaggi, so a player can show more than one rival.
- **Answers are large:** about 12 KB for two players, mostly repeated sources. A full lineup can't repeat them like
  this, so its design must be compact.
- **Two of round 11's ten matches show no over/under** on the round page, so a question about their players needs
  Claude to search, or the 1X2 alone.
- **The presentation pages are out of date.**

## Decision for the owner

**What a verdict's label means.** Across clubs, the key can put a backup keeper who is unlikely to start ahead of a
likely starter in a harder match. The order follows the method: the bench covers him. But the label says "clear", and
that overstates the choice. It matters only when both players get a rating, so what it's worth is the margin times
both chances of a rating, often far smaller than the margin.

**Recommendation:** keep the order, and give and label the margin by what the choice is worth. Method §A9 test 6
would then read "lean" rather than "clear". This changes `mvp-x-or-y` R10.2, so it needs your approval; it would be
the first step of the next slice.

## Next

The full-lineup slice: the user's squad, the league's full rules, the eleven, the bench order and the formation,
simulated to give the expected score and the chance of each threshold, with method §A9 tests 1 and 5. Phase 2's gate
also needs a calibration report on at least one real round, and a mutation-testing run on the core modules.
