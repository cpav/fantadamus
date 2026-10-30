# Requirements Document: `mvp-x-or-y` (Phase 1)

Status: **Approved by the owner, 2026-10-26**; amended after the first real round (R10.7, R13.4) and the first test
round on 2026-10-30 (R5.4, R10.8, R11.4) · Workflow:
requirements-first · Last updated: 2026-10-26

## Introduction

The first thin slice of the advisor answers one question end to end: **"X or Y?" for two forwards**, asked
in the owner's own Claude Desktop. It covers three things:

- **the facts that question needs:** collected by the owner's Claude from the approved sites (ADR-0005);
- **the method for forwards:** [`docs/method.md`](../../../docs/method.md) §A2 to §A4;
- **one read tool:** `compare_players`, which answers or, when facts are missing, returns a refresh plan;
- **the user's league rules:** set once, in Claude, the first time the user asks (R12).

The slice replaces nothing in Spec 0. It reuses the contracts, the bronze → silver → gold lake on DuckDB, the
quality rules and the MCP server, and adds real data domains next to the walking skeleton. It's done when the
method's own tests for forwards pass and the owner gets a real answer for a real round.

**Not in this slice:** keepers, defenders and midfielders; a full lineup or formation; the simulation; the
second player and the online server (Phase 3); xG and player betting markets (MVP gaps, ADR-0005); news and
context; FantaCreator opinions; calibration reports (the log they need starts here, R14).

## Glossary

Spec-wide terms are in `product.md`. Here:

| Term | Meaning |
|---|---|
| Round | The Serie A matchday being asked about: the next one whose deadline hasn't passed |
| Player ID | Fantacalcio.it's numeric player ID, from the player's profile URL (`/serie-a/squadre/{club}/{player}/{id}`); the same ID as the official list's `Id` (`tech.md`) |
| Mantra role | Fantacalcio.it's finer role on a profile: `Pc` (centre-forward), `A` (second striker), `W` (wide forward) |
| Key | Method §A3: (p_start × E_start + p_cameo × E_cameo) / (p_start + p_cameo) |
| Fact | A structured value read from one page, submitted with that page's URL, its publication time and when it was read |
| Refresh plan | What `compare_players` returns instead of an answer: the facts missing or stale, the pages to read, and the submit tool for each |
| League rules | A user's bonus and malus values, set once with `set_league_rules` and used for every answer to that user |
| *(start)* | A starting value from the method, to be calibrated later (method §A8) |

## Sources

Every fact comes from a page on the MVP reading list (`docs/source-registry.md`, "What we read for each
need"). The submit tools reject any other host (ADR-0005, guardrail 1).

| Fact | Primary page | Cross-check | Need |
|---|---|---|---|
| Fixtures and kickoffs of the round | Fantacalcio.it's Serie A calendar | Wikipedia's Serie A season page | N2 |
| Probable lineups, with ballottaggio shares and unavailable players | `fantacalcio.it/probabili-formazioni-serie-a` | Fantacalcio-Online; SOS Fanta | N3, N8 |
| Official lineups | Fantacalcio.it "formazioni ufficiali" article | SOS Fanta | N4 |
| Match odds: 1X2, over/under 2.5, goal/no goal | livetipsportal and Jamma previews; Fantacalcio-Online's odds | Each against the others | N14 |
| A player's season: appearances, average rating, goals, assists, yellow cards, penalties, Mantra role | The player's Fantacalcio.it profile | — | N1, N5, N6 |
| Team goals for and matches played | Fantacalcio.it's Serie A table | Wikipedia's Serie A table | N5 |
| Penalty takers | `fantacalcio.it/rigoristi-serie-a` | Profile notes | N9 |

## Requirements

### Requirement 1: Player identity

**User Story:** As the owner, I want to ask with the names I use, so that "Beto o Laurienté?" finds the right
two players.

- **R1.1** THE SYSTEM SHALL identify every player by his Player ID, and store his name, club, Classic role and
  Mantra role as submitted from his profile.
- **R1.2** WHEN `compare_players` receives two names THE SYSTEM SHALL resolve each to one Player ID, ignoring
  case, accents and spacing, and accepting a surname alone when it is unique among known players.
- **R1.3** IF a name matches no known player or more than one THEN THE SYSTEM SHALL return the candidates (or
  a refresh plan for the profile) instead of guessing.
- **R1.4** IF either player's Classic role isn't `A` THEN THE SYSTEM SHALL say that this slice only compares
  forwards.

### Requirement 2: Fixtures

**User Story:** As the owner, I want each player's next match known, so that the answer prices the right
fixture.

- **R2.1** THE SYSTEM SHALL provide `submit_fixtures` for the round: round number, home and away clubs, and
  kickoff time (stored in UTC).
- **R2.2** THE SYSTEM SHALL take the round's deadline as the kickoff of its first match, and show times in
  `Europe/Rome`.
- **R2.3** IF a player's club has no fixture in the round THEN THE SYSTEM SHALL say so, and treat him as not
  playing.

### Requirement 3: Probable lineups

**User Story:** As the owner, I want each player's chance of starting from more than one outlet, with their
disagreement shown, so that I know how sure the answer is.

- **R3.1** THE SYSTEM SHALL provide `submit_probable_lineups` for one match from one outlet: for each team,
  the expected starters, each ballottaggio with its percentage shares, and the players listed as unavailable.
- **R3.2** THE SYSTEM SHALL turn each outlet's view into a starting probability *(start)*: a listed starter
  0.90; a ballottaggio its share; listed but not starting 0.05; unavailable 0.
- **R3.3** THE SYSTEM SHALL take p_start as the mean over the outlets read, and keep each outlet's value and
  the spread. IF the spread is 0.30 or more THEN THE SYSTEM SHALL mark the player as disputed and say so in
  the answer.
- **R3.4** THE SYSTEM SHALL take p_cameo *(start)* as 0.5 × (1 − p_start) for an available forward, and 0
  for an unavailable one.

### Requirement 4: Official lineups

**User Story:** As the owner, I want the official lineup to win once it's out, so that a late answer uses what
actually happened.

- **R4.1** THE SYSTEM SHALL provide `submit_official_lineup` for one match: both teams' starters and benches.
- **R4.2** WHEN an official lineup exists for a player's match THE SYSTEM SHALL use it over every probable
  lineup: p_start 1 for a starter; p_start 0 and the R3.4 p_cameo for a substitute; 0 and 0 for a player
  not in the squad.

### Requirement 5: Match odds and team xG

**User Story:** As the owner, I want goal chances priced from the betting market, so that bonuses aren't
guessed.

- **R5.1** THE SYSTEM SHALL provide `submit_match_odds` for one match from one page: decimal odds for 1X2 and,
  when shown, over/under 2.5 and goal/no goal, with the bookmaker named on the page.
- **R5.2** THE SYSTEM SHALL remove the bookmaker's margin, and fit each team's expected goals with a
  Poisson model and a Dixon–Coles low-score correction (method §A4), from the mean of the pages read.
- **R5.3** IF a match has no odds THEN THE SYSTEM SHALL fall back to regressed team form, with weight
  n / (n + 12) *(start)* (method §A5), and say so in the answer.
- **R5.4** WHILE a match's fresh odds show no over/under 2.5, THE SYSTEM SHALL keep asking for them in the refresh
  plan, because they price goals, assists and clean sheets. WHEN the collector reports that none can be found,
  THE SYSTEM SHALL answer from the 1X2 alone and say so.

### Requirement 6: Player and team season figures

**User Story:** As the owner, I want each player's record read the league's way, so that his form counts,
shrunk to its real weight.

- **R6.1** THE SYSTEM SHALL provide `submit_player_season` from a player's profile: appearances, appearances
  with a rating, average rating, goals, assists, yellow cards, penalties scored and taken, and Mantra role.
- **R6.2** THE SYSTEM SHALL provide `submit_team_season` from the league table: for each club, matches played
  and goals for and against.
- **R6.3** THE SYSTEM SHALL provide `submit_penalty_takers` from the penalty-takers page: each club's
  designated taker, in order.

### Requirement 7: Storage, provenance and freshness

**User Story:** As the owner, I want every number traceable to the page it came from, so that I can trust or
challenge an answer.

- **R7.1** WHEN a fact is submitted THE SYSTEM SHALL validate it against its versioned contract and store it
  in bronze with the Spec 0 envelope (source URL, publication time, `captured_at`, `received_at`, content
  hash, submitter), then rebuild the affected silver and gold tables.
- **R7.2** THE SYSTEM SHALL keep facts from different outlets side by side, never overwriting one outlet with
  another.
- **R7.3** THE SYSTEM SHALL treat a fact as stale when it is older than its target *(start)*:

  | Fact | Fresh for |
  |---|---|
  | Probable lineups | 12 h; 3 h within 24 h of the match |
  | Match odds | 24 h; 6 h within 24 h of the match |
  | Player and team season figures, penalty takers | 7 days |
  | Fixtures | 7 days |

- **R7.4** WHEN facts are read for an answer THE SYSTEM SHALL use only facts captured before the answer's
  as-of time, so that a replay sees what was known then.

### Requirement 8: Data quality

**User Story:** As the owner, I want collection mistakes caught before they reach an answer.

- **R8.1** IF a probable lineup or official lineup has other than 11 starters for a team THEN THE SYSTEM SHALL
  reject it with the reason.
- **R8.2** IF a ballottaggio's shares don't sum to between 95 % and 105 % THEN THE SYSTEM SHALL reject it.
- **R8.3** IF a set of odds implies a bookmaker margin outside 0 % to 15 % THEN THE SYSTEM SHALL reject it.
- **R8.4** IF a season figure is impossible (more goals than appearances × 5, an average rating outside 3 to
  10, ratings on more appearances than played) THEN THE SYSTEM SHALL reject it.

### Requirement 9: The forward model

**User Story:** As the owner, I want the method's arithmetic, not the model's judgement, so that answers are
consistent and testable.

- **R9.1** THE SYSTEM SHALL compute E_start = expected vote + goal × E[goals] + assist × E[assists] +
  yellow card × P(yellow), using the signed values of the user's league rules (R12), so a
  yellow card at −0.5 lowers the score.
- **R9.2** THE SYSTEM SHALL compute the expected vote as 6.0 + n / (n + 10) × (average rating − 6.0) +
  0.3 × (P(win) − P(loss)), where n is appearances with a rating and the win and loss chances come from the
  fitted odds *(start)*.
- **R9.3** THE SYSTEM SHALL compute E[goals] = team xG × goal share × 0.85, and E[assists] = team xG × assist
  share × 0.85, where 0.85 is a forward's minutes share if he starts *(start)*.
- **R9.4** THE SYSTEM SHALL shrink the goal share toward a role prior: (prior × 15 + goals) / (15 + team goals
  in his games), with priors 0.30 for `Pc`, 0.20 for `A` and 0.15 for `W`, and 0.20 when the Mantra role is
  unknown; and the assist share likewise toward 0.11 *(start)*. Team goals in his games are estimated as the
  club's goals per match × his appearances (no per-minute data in the MVP, ADR-0005).
- **R9.5** WHERE a player is his club's first penalty taker THE SYSTEM SHALL add 0.15 × 0.78 × 0.85 to his
  E[goals] *(start)*.
- **R9.6** THE SYSTEM SHALL take P(yellow) from his yellow cards per appearance, shrunk toward 0.15 with a
  weight of 10 appearances *(start)*.
- **R9.7** THE SYSTEM SHALL value a forward's cameo with a minutes share of 0.28: P(scores in a cameo) × 9.8 +
  (1 − P(scores in a cameo)) × 0.6 × 5.75 *(start)*, with P(scores) = 1 − e^(−E[goals]).
- **R9.8** THE SYSTEM SHALL rank the two players by the key, and keep every intermediate value for the
  answer's breakdown.

### Requirement 10: The answer

**User Story:** As the owner, I want a verdict first and a short breakdown, so that a deadline decision takes
seconds.

- **R10.1** WHEN both players resolve and their facts are fresh THE SYSTEM SHALL return the verdict "start X,
  put Y first on the bench", with X the higher key.
- **R10.2** THE SYSTEM SHALL return the margin in points with its label: coin flip (under 0.15), lean (0.15 to
  0.5) or clear (over 0.5).
- **R10.3** THE SYSTEM SHALL return, for each player: p_start with each outlet's value and the disputed flag,
  P(scores), the expected vote, team xG, the fixture, and the facts' sources and capture times.
- **R10.4** THE SYSTEM SHALL return what would flip the verdict: the p_start or team xG at which the order
  changes.
- **R10.5** THE SYSTEM SHALL return what to check before the deadline: either player whose match is the
  round's first (it sets the deadline), because his official lineup is out about an hour before the lock
  (method §A7).
- **R10.6** THE SYSTEM SHALL return the verdict without bench cover too: ranked by p_start × E_start + p_cameo ×
  E_cameo (the chance of no rating then costs points, method §A3), and say when it differs.
- **R10.7** IF a player has no chance of a rating (p_start + p_cameo = 0: unavailable, not in the squad or
  without a match) THEN THE SYSTEM SHALL say he won't play instead of putting him first on the bench: "start
  X; Y won't play, so put a fit forward first on the bench", or, if neither can play, that neither will.
- **R10.8** THE SYSTEM SHALL also return, for each player: his Classic role; his match's context (the opponent,
  his team's chances to win, draw and lose, and both sides' expected goals); each outlet's ballottaggio rivals
  by name; whether he is his club's first penalty taker, with his penalties scored and taken; and his form
  (appearances, rated appearances, average rating, goals, assists), so the answer can give reasons, not just
  numbers.

### Requirement 11: The refresh plan

**User Story:** As the owner, I want my Claude told exactly what to read, so that collection is quick and
stays on the approved sites.

- **R11.1** IF any fact the answer needs is missing or stale THEN `compare_players` SHALL return a refresh plan
  instead of an answer: each missing or stale fact, the page to read (a fixed URL, or a search hint from the
  source registry), and the submit tool that takes it.
- **R11.2** THE SYSTEM SHALL order the plan so that the facts which decide most come first: lineups, then
  odds, then season figures.
- **R11.3** WHEN the refreshed facts have been submitted and `compare_players` is called again THE SYSTEM
  SHALL answer, or return only what is still missing.
- **R11.4** THE SYSTEM SHALL give every fact in a refresh plan more than one way to read it, best first: at least
  two pages or search hints, including at least one search hint, so that no fact depends on a single page.
  Wikipedia is never the first choice, since the collector may only see it through a stale cache.

### Requirement 12: League rules

**User Story:** As a player, I want to set my league's rules once, the first time I use Fantadamus, so that
every answer scores players the way my league does.

- **R12.1** THE SYSTEM SHALL keep one set of league rules per user: the bonus and malus table of a Fantacalcio
  Classic league. It holds goal (one value, or one per role P, D, C and A), assist, penalty scored, penalty
  missed, penalty saved, own goal, yellow card, red card, and, for keepers, goal conceded and clean sheet.
- **R12.2** THE SYSTEM SHALL provide `set_league_rules`, which validates and stores a user's rules, and which
  the user can call again to change them. IF a value is out of range (a bonus below 0 or above 10, a malus
  above 0 or below −10) THEN it SHALL reject it with the reason.
- **R12.3** IF a user has no league rules THEN `compare_players` SHALL return the setup step instead of an
  answer: the values to ask the user for, offering the Classic values as the starting choice (goal +3,
  assist +1, penalty scored +3, penalty missed −3, penalty saved +3, own goal −2, yellow card −0.5, red card
  −1, goal conceded −1, clean sheet +1).
- **R12.4** THE SYSTEM SHALL store each user's rules privately, keyed by their pseudonymous user ID, never in
  the repository; and every answer SHALL name the rules it used.
- **R12.5** This slice uses goal, assist, penalty scored (as a goal) and yellow card. The rest of the table
  is kept for later slices, and the rules beyond bonuses and maluses (goal thresholds, modifiers, bench size,
  substitutions, formations) are added with the full-lineup slice.

### Requirement 13: In the owner's Claude Desktop

**User Story:** As the owner, I want to ask from my own Claude app, so that nothing new needs installing for
the conversation.

- **R13.1** THE SYSTEM SHALL serve `compare_players`, `set_league_rules` and the submit tools from the
  existing MCP server over stdio, with tool descriptions that name each submit tool's source pages.
- **R13.2** THE SYSTEM SHALL serve the agent prompt (`docs/agent-prompt.md`, with its MVP collection section)
  as the server's instructions.
- **R13.3** THE SYSTEM SHALL document, in the README, how to add the server to Claude Desktop.
- **R13.4** THE SYSTEM SHALL provide a step-by-step setup guide for a second player, including a Claude Project
  whose instructions are the agent prompt, so that Claude uses the tools without being told to; and the
  agent prompt SHALL name only the tools that exist.

### Requirement 14: The decision log

**User Story:** As the owner, I want every answer kept, so that the method can be checked against what
happened (method §A8).

- **R14.1** WHEN `compare_players` answers THE SYSTEM SHALL append to a log: the as-of time, both players, every
  published probability (p_start, P(scores)), both keys, the verdict, the league rules used, and the content
  hashes of the facts used.
- **R14.2** THE SYSTEM SHALL never modify or delete a log entry.

## Acceptance tests

| ID | Acceptance test | Proves |
|---|---|---|
| AT-1 | Method §A9 test 2: with a flat 5.5 cameo, (p_start 0.55, p_cameo 0.35, E 7.2) and (0.90, 0.05, 6.6) tie at a key of 6.54, and ranking by p_start × E + p_cameo × 5.5 is not used | R9.8, R10.1 |
| AT-2 | Method §A9 test 4: a centre-forward with 4 goals in 5 starts, team xG 1.35 and 88 % to start is about 32 % to score; a rotation striker at 25 % with team xG 1.1 about 10 %; the first ranks ahead | R9.3, R9.4, R9.7, R10.1 |
| AT-3 | Method §A9 test 6: X is ahead if he plays but only about 55 % to get a rating, so the answer is "start X, Y first on the bench", and the answer without bench cover differs | R10.1, R10.6 |
| AT-4 | Scripted collection end to end: from an empty lake, `compare_players` returns a refresh plan; after scripted submissions from synthetic pages, it answers with sources and capture times | R7, R10, R11 |
| AT-5 | An official lineup overrides three probable lineups that disagreed | R4.2, R3.3 |
| AT-6 | Two outlets 0.90 and 0.50 for the same player give p_start 0.70, marked disputed | R3.2, R3.3 |
| AT-7 | Bad submissions are rejected with the reason and nothing is stored: a host off the allowlist, 10 starters, shares summing to 80 %, a margin of 25 % | R8, ADR-0005 |
| AT-8 | An answer at an earlier as-of time ignores facts captured later | R7.4 |
| AT-9 | Every answer adds one log entry; entries are never changed | R14 |
| AT-10 | A user without league rules gets the setup step instead of an answer; after `set_league_rules`, the answer uses those rules, and raising the goal bonus raises E_start; an out-of-range value is rejected | R12 |
| AT-11 | Manual: the owner sets their rules in Claude Desktop, then asks a real "X or Y?" for a real round, and gets an answer whose facts all come from the reading list | All, R13 |

## Owner decisions

- **2026-10-26:** league rules are set by each user in Claude, the first time they ask, through
  `set_league_rules` (option A). The owner's league uses the Classic values for goal (+3), assist (+1) and
  yellow card (−0.5).
- **2026-10-26:** these requirements approved. The constants marked *(start)* are the method's starting
  values, calibrated later from the decision log.
- **2026-10-26, after the first real round:** R10.7 (a player who can't play isn't benched) and R13.4 (a
  Claude Project and a guide for the second player) added. When no odds are found, the flagged team-form
  fallback (R5.3) stays.
- **2026-10-30, first test round:** Claude couldn't read Wikipedia (its reader saw a stale cache without the
  season page), and the plan offered nothing else, so no answer was possible. The owner asked for more
  reliable sources: Fantacalcio.it's calendar and table become the primary pages, and R11.4 rules out single
  points of failure.
- **2026-10-30, same round:** Claude found only 1X2 prices for a match, which `submit_match_odds` couldn't
  take, so the answer fell back to team form. The owner approved making over/under 2.5 optional (R5.1), so the
  fit uses whichever markets the page shows, but over/under stays wanted (R5.4): it prices the bonuses.
- **2026-10-30, the answer's shape:** the owner showed the "X or Y?" answer they want: match context first,
  then each player with a one-line verdict and reasons (start chance and rival, penalties, scoring chance and
  value, form). R10.8 adds the data that needs; the agent prompt's "How to answer" follows it.
