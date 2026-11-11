# Design Document: `mvp-cards` (Phase 2, sixth slice)

Status: **Approved by the owner, 2026-11-10**, with both recommendations · From the approved [requirements](requirements.md)

## Overview

A card is one fixture, worked out from the same facts and the same engine as every other answer: the odds give the match in
numbers, the outlets give the lineups, and each player's value is the one `player_outlook` would give him. Nothing here changes a
number Fantadamus forecasts. The card gathers both clubs' players at once, as a lineup gathers a squad, and keeps to a short list
of who matters, so that it answers within the lineup's budget.

The round overview is the same match block for every fixture, without the players: team-level numbers only, so it costs little.

The only new facts are the table's wins, draws, losses and last five results. The form column is shown as coloured dots, so the
page's text, which Claude reads through `read_page`, doesn't carry it. Fantadamus reads the table itself instead, as it already
reads the statistics and penalty-takers pages of the same site under ADR-0006.

## What it builds on

- `mcp/advisor.py`:
  - `Advisor.gather` gives each player's facts: his season, his club's table row, the penalty order, his match, his
    availability and his team's expected goals;
  - `after_collecting` reads what's missing first, and never collects for a replay;
  - `model_inputs` and `model_value` give his value under a scoring table.
- `domains/odds/gold.py`: `team_xg` gives a match's expected goals, its de-margined chances and the spread between odds pages.
  It falls back to team form without odds.
- `engine/odds.py`: `model` gives the chance of three goals or more and of both teams scoring for a pair of expected goals.
- `engine/keepers.py`: a keeper's clean sheet is e^−xG of the opponent's expected goals. The card's team clean sheets use the
  same formula, so they agree with the keeper's.
- `domains/availability/`: each player's outlets, his ballottaggio rivals, his official status, and whether he's disputed.
  `domains/sources.py` turns those into a confidence: official, agree, disputed or one source.
- `domains/fixtures/gold.py`: the next round, a club's fixture in it, and the round's deadline.
- `web/collector.py`, with `web/readers/fcit_takers.py` as the pattern: a Fantacalcio.it page read on a cadence, stored with its
  URL, time and content hash.
- `lake/decision_log.py`: every answer's published chances, which the calibration report reads (`last_told`).
- `league/rules.py`: `CLASSIC`, the ready-made table, for a user with no rules stored.

## Components

### C1. The table's record and form (`contracts/xy/season.py`, `web/readers/fcit_table.py`, `web/collector.py`; R2.4, R6.3)

- **Contract.** `TeamRow` gains `wins`, `draws`, `losses` and `form`, all optional, so a table Claude submits without them stays
  valid. `form` holds up to five results, each `W`, `D` or `L`, oldest first. `TeamSeasonPayload` becomes 1.1.0, a minor version.
- **Checks.** The record must add up to the matches played. The form can't hold more wins, draws or losses than the record does.
- **Reader.** `read_table(page)` reads Fantacalcio.it's `/serie-a/classifica`:
  - each club's row: G, V, P, S, Gf and Gs, which are played, won, drawn, lost, goals for and goals against;
  - the form from the dots' `data-value`.
  A page whose title or columns aren't the expected ones is unreadable, as the other readers' pages are.
- **Collector.** The collector reads the table daily, like the statistics page, so it's never a round behind; the answers'
  freshness target for the table stays a week. The reading list's new `table` entry can switch it off. Claude stays the fallback: when the page can't be read, the refresh plan lists it as
  it does today, and Claude's submission still validates without the new fields.
- **Order.** Task 1 checks the order of the dots against the results on the recorded calendar page before relying on it.

### C2. The match in numbers (`domains/cards.py`, pure; R2)

`match_numbers(xg, home_row, away_row)` returns a `MatchNumbers`:

- **The chances:** each side's chance to win and the chance of a draw, the de-margined chances `team_xg` already gives. With
  several odds pages, also the spread between them.
- **The goals:** each side's expected goals and its clean sheet, e^−xG of the other side's expected goals. Where the odds showed
  over/under 2.5, also the chance of three goals or more and of both teams scoring, from `odds.model`. Without odds, team form
  gives the expected goals, and the chances only odds can price are left out (R2.3).
- **The season so far:** goals for and against per match. Where the table gave them, also the wins, draws and losses and the last
  five results. They're shown and never used in a number (R2.4).

### C3. The lineups (`domains/cards.py`, pure; R3)

`lineups(sides)` works on the gathered players of one club:

- **The likely eleven.** The official eleven once it's stored. Before that, the eleven likeliest starters by chance of starting,
  with one keeper, the likeliest. Each comes with his role, his chance of starting and its confidence (`of_outlets`).
- **Disputed places.** Starting places only (refined in task 8, from a real round):
  - each ballottaggio with a likely starter in it is one place, its contenders joined whichever side named whom;
  - for each role, the likely starters the outlets disagree about (`disputed`) share one place, with as many places as there
    are of them, set against as many of the next in line: the likeliest of that role outside the eleven.

  A bench player the outlets disagree about, or a ballottaggio between bench players, is no starting place. Each contender
  comes with his chance of starting; a disputed one names the outlets on the smaller side of the consensus, and none in an even
  split, so "Sky has him out" reads plainly (refined in task 3).
- **Out.** Each player at least one outlet lists as unavailable, with how many outlets do.
- **The official lineups:** used and said once stored. Until then, the card says they're due about an hour before kickoff.

### C4. What it means for the players (`domains/cards.py`, pure, on the engine's values; R4)

For each player in the likely elevens, the contenders and the user's players, a `CardPlayer` gives:

- his name, role and club;
- his chance of starting and its confidence;
- for an outfield player:
  - his chance of scoring in the match, if he starts and from a cameo together (p_start × p_scores + p_cameo × p_scores_cameo);
  - his chance of scoring if he starts;
  - his share of his side's expected goals (`goal_share`);
- for a keeper: his clean sheet and the goals he's expected to concede;
- what he's worth, his key, under the scoring table.

From those:

- **The likeliest scorers:** the five players of either club with the best chance of scoring in the match. A player who's likely to
  come off the bench counts, so a late striker isn't missed.
- **The penalty takers:** each club's order, as `penalty_order` gives it, with each taker's penalties scored and taken this season.
- **Rotation risks:** a player who usually starts, whose chance this round is low. A disputed starter who's still likely to
  start is in his disputed place instead (amended in task 8).
  - *Usually starts:* his rated games are at least `USUAL_SHARE` of his club's matches played.
  - *Low:* his chance of starting is under `ROTATION_P_START`.
  - Both are new *(start)* constants: 0.7 and 0.6.
- **Your players:** the stored squad's players in either club, first, each with what he's worth. Given a league-mate's team, that
  squad is used instead.
- **The scoring table.** The user's stored rules give the table. With none stored, Classic's does, and the card says so (R4.6).
  Formula rules don't apply to one player's value: as in `player_outlook`, the card names them as left out of its numbers.

### C5. The card tool (`mcp/tools/cards.py`; R1, R6.1)

`match_card(club, other_club=None, team=None, as_of=None)` returns a `CardResult`:

| Status | When |
|---|---|
| `card` | The card, with whatever is missing named, and `improve` listing what could make it better, as a lineup's does |
| `refused` | A club the clubs list doesn't know, or two clubs that don't meet in the round |
| `no_match` | The club has no match in the next round |
| `refresh` | The round's fixtures aren't known: nothing can be said yet |

The steps:

1. **The clubs:** resolved through `Clubs.key`, which knows every accepted spelling. The fixture is the club's match in the next
   round, or the two clubs' match when both are given.
2. **Past the deadline.** One club's match is always the next round's, whose deadline is still ahead. Two clubs whose match is in
   the round before it, past its deadline, get the card as it stood at that deadline: a replay of the facts stored by then
   whatever their age, said so (R1.4, amended in task 5).
3. **The facts:** gathered through `after_collecting` for every known player of both clubs, as a lineup gathers a squad. Missing
   lineups or odds don't stop a card: it gives the team numbers and says what's missing. The plan's items go in `improve`.
4. **The numbers:** each player's value from `model_inputs` and `model_value`, the same calls `player_outlook` makes. AT-8 checks
   the two agree.
5. **The log.** A card at the clock's time logs one decision line of a new kind, `card`, with a `LoggedPlayer` for each player the
   card shows. The calibration's `last_told` already reads every kind, so cards join what users were told. A replay logs nothing.
   The win, draw and loss chances are the market's own, so they aren't logged for scoring.

### C6. The round overview (`mcp/tools/cards.py`, `domains/cards.py`; R5)

`round_overview(as_of=None)` gives a `RoundOverview`: the round, its deadline, and one `FixtureLine` per fixture in kickoff order.
Each line holds:

- the kickoff;
- the favourite and its chance, and the draw;
- both sides' expected goals and clean sheets;
- the chance of three goals or more, where the odds give it.

It gathers only the fixtures, the odds and the table, never the players, so it costs little and logs nothing. A question across
fixtures, such as which keepers are safest, is answered from its clean sheets.

### C7. The answer, the docs and the limits (`docs/`; R6.2 to R6.5)

- **Format 5** in `docs/answer-formats.md` becomes the card as built:
  - the context line;
  - the match in numbers;
  - the season so far;
  - the lineups, disputed places and who's out;
  - the takers;
  - the likeliest scorers;
  - the rotation risks;
  - your players;
  - the sources.
  Its context and rest lines move to "Later, in their own specs".
- **The overview** gets a short example of its own under format 5.
- **The prompt's budget is nearly spent** (12,754 of 13,000). The prompt gains one line in "Where answers come from", naming
  `match_card` and `round_overview` and when to call them. Each tool's description carries its own rendering rules: Claude reads
  it with the tool, and it isn't counted against the prompt.
- **The player guide** gains the questions to ask ("Tell me about Inter–Como", "Where are the goals this round?").
- **Budget.** A card prices about 50 to 60 players, every known player of two clubs, against a squad's 25. `tests/lineup_speed.py`
  gains `--card` and `--overview`, and AT-10 holds both under 3 seconds. Should a real round go over, the card gathers only the
  players the outlets list.
- **Size.** The card lists only the likely elevens, the contenders, the scorers and the user's players. Each named player is in
  `players` once, and the sides and the user's players refer to him by ID; numbers are rounded to three decimals. The invented
  round's card is under 10 KB.

## Error handling

| Condition | Behaviour |
|---|---|
| An unknown club, or two clubs that don't meet in the round | `refused`, naming the clubs the list knows |
| A club with no match in the round | `no_match`, saying so |
| No fixtures stored for the next round | `refresh`, with the fixtures' plan item |
| No odds for the match | Team form gives the expected goals, the card says so, and over/under and both-teams-to-score are left out |
| No lineups published yet | The team numbers, and the lineups named as missing in `improve` |
| A player in no read of the statistics page | Left out of the card, and named as missing |
| The table page can't be read | The refresh plan lists it for Claude, as today; the card shows the table figures it has |
| Two clubs whose round is past its deadline | The card as it stood at the deadline, said so; nothing logged |

## Correctness properties

These Hypothesis tests are required:

| # | Property | Requirements |
|---|---|---|
| P1 | The chances of a win, a draw and a loss sum to one, each clean sheet is e^−xG of the other side's expected goals, and each chance is between 0 and 1 | R2.1, R2.2 |
| P2 | A likely eleven has eleven players and one keeper, all of his club, and once the official lineup is stored it's the official eleven | R3.1, R3.4 |
| P3 | The record and the form never move a number: changing them leaves every chance and every value the same | R2.4 |
| P4 | Each player's chance of starting and of scoring on the card is the one `player_outlook` gives at the same as-of | R4.1, AT-8 |
| P5 | The overview's lines are in kickoff order whatever order the fixtures were stored in, and a card replayed at an earlier as-of logs nothing | R5.1, R1.5 |

## Testing strategy

- **Unit, in `tests/unit/cards/`:** C2 to C4 by hand, on invented odds, tables and availabilities.
- **Property, in `tests/property/cards/`:** P1 to P5.
- **Contract:** the table reader against a synthetic page with the record and the form, and a page whose columns changed.
- **Integration, in `tests/integration/cards/`:** both tools end to end on the invented round of `tests/lineup_harness.py`, with
  the table page added to its routes.
- **Acceptance, in `tests/acceptance/cards/`:** AT-1 to AT-10 automated, AT-11 by hand.

Clubs, players, odds and tables in tests are invented. A real page or card never reaches the repository.

## Cost

$0. No paid service and nothing on AWS. The table is a page already on the reading list, read once a day by Fantadamus instead
of once a week by Claude. A card is one gather of two clubs and no simulation; the overview is a few reads of the lake.

## Build order (input to tasks.md)

1. **The table's record and form:** contract, reader, collector, silver, the reading list. This spec becomes the current one.
2. **The match in numbers:** pure, with P1 and P3.
3. **The lineups:** pure, with P2.
4. **What it means for the players:** pure, on the engine's values, with the rules' fallback.
5. **The card tool:** the clubs, the fixture, the kickoff, the gather, the log; P4 and P5.
6. **The round overview.**
7. **The docs:** format 5, the tools' descriptions, the prompt's line, the guide, the budget.
8. **A real check and sign-off:** a real round from Claude Code, the owner's AT-11, a mutation run, the slice report.

## Open points for the owner

Approved with the design on 2026-11-10 ("Approve both").

1. **Who reads the table.** The approved requirements have Claude reading it, but `read_page`'s text can't show the form's dots.
   Recommendation: Fantadamus reads the table itself, as it reads the statistics and penalty-takers pages of the same site (C1).
   That also takes the weekly table off Claude's refresh plans. Approved. The alternative is to make `read_page` write each dot as a letter,
   and keep Claude reading it.
2. **The rotation thresholds.** Recommendation: start at 0.7 (usually starts) and 0.6 (low chance), as *(start)* constants, and
   recalibrate them with the rest. Approved.
