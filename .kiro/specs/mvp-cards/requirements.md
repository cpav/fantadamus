# Requirements Document: `mvp-cards` (Phase 2, sixth slice)

Status: **Approved by the owner, 2026-11-10**, with all three recommendations · Workflow: requirements-first · Depends on: `mvp-review` (built; its
sign-off waits for round 12's AT-8) · Abbreviation: `cd` · Method: [`docs/method.md`](../../../docs/method.md) §A4, §A6, §A8 ·
Answers: [`docs/answer-formats.md`](../../../docs/answer-formats.md), format 5

## Introduction

A match card puts one fixture on one screen. It shows:

- who's favoured and by how much, and how many goals to expect;
- who'll start, and where that's disputed;
- who's out and who takes the penalties;
- what all of it means for each player, the user's own first.

It's the third of `product.md`'s three levels of questions, match-up intelligence. It's also the answer a live chat asks for
most after "X or Y?": "what about Inter–Como?".

This slice uses only the facts Fantadamus already collects, through the same engine as every other answer, so a card and an
"X or Y?" never disagree. It changes no numbers, so it can start while round 12 is awaited (`product.md`'s rule).

**Not in this spec:**

- context: coach changes, reported tactical shifts, credible reports and rumours;
- rest days and midweek European fixtures;
- set-piece takers other than penalties, and injury detail (why a player is out, and until when);
- home and away splits, which no approved page has.

The first three need new sources, each with its route approved first: the new-sources slice, after which the card gains their
lines. Also out: live scores (`product.md`, Further notes), alerts (their own slice), and trades, auctions and market values
(out of scope for v1).

## Glossary

| Term | Meaning |
|---|---|
| Card | One fixture of the next round, on one screen: the match in numbers, the lineups, and what they mean for the players |
| Round overview | One line per fixture of the round, team-level only, in kickoff order |
| Likely eleven | A side's eleven likeliest starters, by role |
| Disputed place | A starting place where the outlets disagree, or that a page marks as a ballottaggio |
| Rotation risk | A player who usually starts for his club but whose chance of starting this round is low or disputed |
| Your players | The players of the user's stored squad who play in the match; a league-mate's team when it's named |

## What the facts already give

Read on 2026-11-10 from the code and from the recorded pages in `data/private/pages/`.

- **The round page** (Fantacalcio-Online, read by Fantadamus itself under ADR-0006) gives:
  - the fixtures and their kickoffs;
  - four outlets' probable lineups, with each player's chance of starting and the ballottaggi;
  - the players each outlet lists as unavailable;
  - the official lineups, about an hour before kickoff;
  - the odds: 1X2, over/under 2.5, and both teams to score.
- **From the odds, the engine fits:**
  - each team's expected goals, by Poisson with a Dixon-Coles correction;
  - the de-margined chances of a win, a draw and a loss;
  - the chance of three goals or more, and of both teams scoring;
  - each side's chance of a clean sheet.
- **The statistics page** gives every player's season figures, and **the takers page** each club's penalty takers in order.
- **The table** (Fantacalcio.it's `classifica`, read by Claude from the reading list) gives each club's matches played, goals for
  and goals against.
  - The page also shows wins, draws and losses, and each club's last five results ("Forma"). Fantadamus doesn't keep those today.
  - The page has no home and away split.
- **The engine already works out, for any player:** his chance of starting and of a cameo, his chance of scoring if he starts,
  his share of his team's expected goals, and what he's worth in points. For a keeper, it also gives his clean sheet and the
  goals he's expected to concede.
- **What the facts don't give:**
  - why a player is out, or until when: the page says "unavailable", and doesn't tell an injury from a suspension;
  - rest days and European fixtures;
  - coach changes and news.

## Requirements

### Requirement 1: One card per fixture

**User Story:** As a player or a viewer, I want one fixture on one screen when I ask about a match.

- **R1.1** WHEN a user asks about a match of the next round, by its two clubs or by one of them, THE SYSTEM SHALL answer with its
  card. A club with no match in the round SHALL get that answer, not a guess.
- **R1.2** THE card SHALL open with the context line every answer has: the match, its kickoff in Europe/Rome, the round's
  deadline, and how fresh its facts are.
- **R1.3** THE SYSTEM SHALL gather the facts as the other read tools do: the collector reads what's missing or stale, a refresh
  plan lists what it couldn't, and the card says what's missing and what it assumed.
- **R1.4** WHERE the match has kicked off THE SYSTEM SHALL say so, and give the card as it stood at kickoff: a forecast's job
  ends there.
- **R1.5** A card MAY be replayed at an earlier `as_of`, as the other read tools are, without collecting or logging.

### Requirement 2: The match in numbers

**User Story:** As a player, I want the match's odds in plain chances, and how many goals to expect.

- **R2.1** THE card SHALL give each side's chance to win and the chance of a draw, from the de-margined odds. Where several odds
  pages are stored, it SHALL say how far apart they are.
- **R2.2** THE card SHALL give each side's expected goals and chance of a clean sheet. It SHALL also give the chance of three goals
  or more and of both teams scoring, where the odds show them.
- **R2.3** WHERE no odds are stored THE SYSTEM SHALL use team form, as the other answers do, and say so. It SHALL then leave out
  the chances only odds can price (three goals or more, both teams to score).
- **R2.4** THE card SHALL give each side's season so far from the table: goals for and against per match. Where the table gives
  them, it SHALL also give wins, draws, losses and the last five results. These are context and SHALL NOT move a number.

### Requirement 3: The lineups

**User Story:** As a player, I want to see who'll start for both sides, and how sure that is.

- **R3.1** THE card SHALL give each side's likely eleven by role. Each player SHALL come with his chance of starting and how sure
  it is: official, agree (how many outlets), disputed, or one source.
- **R3.2** THE card SHALL name each disputed place: its contenders, each with his chance, and the outlets that disagree.
- **R3.3** THE card SHALL name who's out: the players an outlet lists as unavailable, with how many outlets say so.
- **R3.4** WHEN the official lineups are stored THE SYSTEM SHALL use them and say so. Until then, it SHALL say when they're due.

### Requirement 4: What it means for the players

**User Story:** As a player, I want to know what the match means for the players I'm choosing between, mine first.

- **R4.1** FOR each likely starter, THE card SHALL give his chance of scoring and his share of his side's expected goals. It SHALL
  also name the match's likeliest scorers, a few, by their chance of scoring in the match.
- **R4.2** FOR each side's keeper, THE card SHALL give his chance of a clean sheet and the goals he's expected to concede.
- **R4.3** THE card SHALL give each side's penalty takers in order, with their penalties scored and taken this season.
- **R4.4** THE card SHALL name the rotation risks: players who usually start for their club but whose chance of starting this
  round is low, or whose place is disputed.
- **R4.5** WHERE the user has a squad stored THE card SHALL put their players in the match first, each with what he's worth this
  round. Given a league-mate's team, it SHALL use that squad instead.
- **R4.6** Points SHALL follow the user's stored league rules, or Classic's where none are stored, saying so. A card SHALL NOT need
  a setup step: a live-chat viewer gets one at once.

### Requirement 5: The round at a glance

**User Story:** As a player, I want the whole round in a few lines, to see where the goals and the clean sheets are.

- **R5.1** WHEN a user asks about the whole round THE SYSTEM SHALL give one line per fixture, in kickoff order. Each line SHALL
  give the favourite and its chance, the expected goals and the clean-sheet chances, and the answer SHALL offer any fixture's
  card.
- **R5.2** THE round overview SHALL be enough to answer a question across fixtures, such as "which keepers are safest this round?"
  or "where are the goals?", from its numbers alone.

### Requirement 6: Logging, the docs and the limits

**User Story:** As the owner, I want cards audited like every other answer, and as quick and cheap.

- **R6.1** THE SYSTEM SHALL log each card's published chances for each player, append-only, with its as-of time and the snapshots
  it used: starting, getting a rating, scoring, and clean sheets. The round's calibration report SHALL then count them with what
  users were told (method §A8).
- **R6.2** THE SYSTEM SHALL answer a card, and the round overview, within `mvp-lineup`'s budget: 3 seconds and 15 KB.
- **R6.3** THE SYSTEM SHALL read no new page and call no paid service. The only new facts are the table's wins, draws, losses and
  last five results, from a page already read under its route.
- **R6.4** THE SYSTEM SHALL update format 5 in `docs/answer-formats.md`, moving its context and rest lines to the new-sources
  slice.
- **R6.5** THE SYSTEM SHALL update the agent prompt within its budget, and the player guide.

## Acceptance tests

| Test | What it proves | Requirements |
|---|---|---|
| AT-1 | A card asked by two clubs and by one, with its context line; a club with no match in the round; a match that has kicked off | R1 |
| AT-2 | The numbers by hand: chances from de-margined odds and the spread between pages, expected goals, clean sheets, three goals or more and both teams to score; without odds, team form, said | R2.1 to R2.3 |
| AT-3 | The table's figures and the last five results shown, and no number moved by them | R2.4 |
| AT-4 | The lineups: a likely eleven with its confidence, a ballottaggio, an outlet that disagrees, the unavailable, official lineups once stored | R3 |
| AT-5 | What it means, by hand: a scorer's chance and share, the likeliest scorers, a keeper's clean sheet and goals conceded, the takers, a rotation risk, the user's players first | R4.1 to R4.5 |
| AT-6 | A card without stored rules uses Classic's points and says so; a league's own rules change the points, not the chances | R4.6 |
| AT-7 | The round overview, one line per fixture in kickoff order, answering a question across fixtures | R5 |
| AT-8 | A card's numbers for a player are the same as `compare_players`' and `player_outlook`'s at the same as-of | R1.3, R4.1 |
| AT-9 | Logged for calibration and counted in the round's report; a replay at an earlier as-of logs nothing | R1.5, R6.1 |
| AT-10 | A card and the overview in their formats, within 3 seconds and 15 KB, from no new page | R6.2 to R6.4 |
| AT-11 | Manual: the owner reads round 12's cards in a Claude app before the deadline and checks them against the round page | R1 to R5 |

## Review of these requirements

An Analyze-Requirements pass, before design.

- **One engine, one answer.** A card prices players the way `player_outlook` does, so the two can't disagree. AT-8 checks it.
- **"Unavailable" isn't injury detail.** The outlets' lists say a player is out, not why or until when. The card says "listed as
  out by 3 outlets", never "injured". The detail waits for the new-sources slice.
- **Form is context, and raw form misleads.** Method §A9 test 3 shows five-game form exaggerating a gap that regressed form
  removes. The last five results are shown as what happened, beside numbers that come from the odds. R2.4 forbids them moving a
  number.
- **Rotation risk needs a definition.** "Usually starts" can come from his season figures: rated games against his club's matches.
  "Low" needs a *(start)* threshold. The design sets both and logs them.
- **Speed.** A card prices everyone the outlets list for both clubs, about 30 to 40 players, against a squad's 25. The lineup's
  gather costs about 0.03 s a player on a real round, so a card should fit in its budget. The design measures it on a real round.
  The overview prices no player: team-level numbers only.
- **Size.** Two sides in full could pass 15 KB. The card lists the likely elevens, the disputed contenders and the user's players;
  everyone else stays out, as a lineup's bench does.
- **The prompt's budget is nearly spent:** 12,754 of 13,000 characters. The card's rendering rules can go in the tool's
  description, which Claude reads with the tool. The prompt then needs only a line naming the tool and saying when to use it.
- **A live chat has no squad and no rules.** R4.5 doesn't apply there, and R4.6 gives Classic's points without a setup step. A
  viewer who later gives their rules gets their own points.
- **Calibration gets more to score.** Cards log players beyond the user's squad, so "what users were told" grows. That's what
  method §A8 asks for. The design checks that the report's two sets stay comparable.
- **Privacy.** A card holds no private data. Only "your players" comes from the user's squad, shown in their own chat.

## Owner decisions

- **2026-11-10:** the owner chose to start the match cards while round 12 is awaited.
- **2026-11-10, these requirements approved,** with the three recommendations below ("Approve all three").

1. **The table's record and form.** Recommendation, approved: keep wins, draws, losses and the last five results. They come from the table
   page Claude already reads, as optional fields (a minor contract version), and are shown as context only (R2.4). The
   alternative is to leave them out until the new-sources slice.
2. **The round overview.** Recommendation, approved: yes, team-level only (R5). It's small and fast, and it answers questions across
   fixtures that one card can't. The alternative is cards only.
3. **Points without league rules.** Recommendation, approved: a card answers anyone at once, with the stored rules or Classic's, saying so
   (R4.6). That makes it the easiest entry for a live chat. The alternative is the setup step first, as `compare_players` does.
