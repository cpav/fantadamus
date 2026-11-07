# Changelog: `mvp-x-or-y` contracts

Each contract has a semantic version. A schema change needs a version bump and an entry here; a breaking
change (a field removed or renamed, a type or value set narrowed, a field newly required) needs a major bump.
Headings are `## <Contract> <version> (<date>)`.

## FixturesPayload 1.0.0 (2026-10-26)

- First version: `round` and `matches` (`home`, `away`, `kickoff_at`); each club once per round (R2.1).

## ProbableLineupPayload 1.0.0 (2026-10-26)

- First version: `outlet`, `home`, `away` and per team `starters`, `ballottaggi`, `bench`, `unavailable`;
  11 starters (R8.1), shares summing to 95–105 % (R8.2).

## OfficialLineupPayload 1.0.0 (2026-10-26)

- First version: `home`, `away` and per team `starters` and `bench`; 11 starters (R8.1).

## MatchOddsPayload 1.0.0 (2026-10-26)

- First version: 1X2, over/under 2.5 and optional goal/no goal decimal odds with the `bookmaker`; each
  market's margin within 0–15 % (R8.3).

## PlayerSeasonPayload 1.0.0 (2026-10-26)

- First version: the profile's ID, name, club, roles and season figures; plausibility rules (R8.4).

## TeamSeasonPayload 1.0.0 (2026-10-26)

- First version: per club `played`, `goals_for`, `goals_against` (R6.2).

## PenaltyTakersPayload 1.0.0 (2026-10-26)

- First version: per club the `takers`, first choice first (R6.3).

## LeagueRules 1.0.0 (2026-10-26)

- First version: `goal` (one value, or one per role), `assist`, `penalty_scored`, `penalty_missed`,
  `penalty_saved`, `own_goal`, `yellow_card`, `red_card`, `goal_conceded`, `clean_sheet`; bonuses 0 to 10,
  maluses −10 to 0 (R12.1, R12.2).

## MatchOddsPayload 1.1.0 (2026-10-30)

- `over_2_5` and `under_2_5` become optional, together, like goal/no goal: a page that shows only 1X2 prices
  can be submitted (R5.1). A widening change, so a minor version.

## OutletLineupPayload 1.0.0 (2026-10-31)

- First version: `outlet`, `home`, `away` and per team `players` (`name`, optional `role`, `percent`) and
  `unavailable`; at least 11 players per team, each once, percentages 0 to 100 (mvp-collect R4.1).

## MatchOddsPayload 1.2.0 (2026-10-31)

- Adds an optional `over_2_5_percent`: a page's own chance of 3 or more goals, used when it gives no
  over/under odds (mvp-collect C4). A widening change, so a minor version.

## PlayerSeasonPayload 1.1.0 (2026-11-03)

- Adds an optional `goals_conceded`, a keeper's goals conceded. Only a keeper may concede, and at most 10 a
  rated appearance (mvp-roles R6.1, R6.2). The `appearances` description says that, from the statistics page,
  which gives no presenze, they are the rated appearances (R1.3). A widening change, so a minor version.

## SeasonStatsPayload 1.0.0 (2026-11-03)

- First version: one read of Fantacalcio.it's statistics page, `players`, each with the same fields and checks as
  `PlayerSeasonPayload`, each player ID once (mvp-roles R1.1).

## OfficialLineupPayload 1.1.0 (2026-11-04)

- Adds an optional `unnamed_starters` per team, at most 1: a source can name only 10 of a team's 11 starters. The lineup
  must still account for 11 (mvp-x-or-y R8.1). A widening change, so a minor version.

## LeagueRules 2.0.0 (2026-11-07)

- One table of events (`events`) in place of ten fixed values and `GoalByRole` (mvp-rules R1.1). An event left out
  isn't scored. Adds `decisive_goal` and `set_piece_assist`. A breaking change for what's written, so a major
  version; rules in the earlier form, in a user's file or a decision log line, are read as the same table (R1.6).

## LeagueRules 1.1.0 (2026-11-04)

- Adds an optional `lineup`: what a lineup needs beyond bonuses and maluses, any of it still unset (mvp-lineup R2).
  Rules stored before it stay valid, and "X or Y?" doesn't need it. A widening change, so a minor version.
