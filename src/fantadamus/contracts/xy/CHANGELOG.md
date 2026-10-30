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
