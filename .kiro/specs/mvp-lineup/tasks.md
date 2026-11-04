# Implementation Plan: `mvp-lineup` (Phase 2, third slice)

Status: **Approved by the owner, 2026-11-04** · From the approved [requirements](requirements.md) and
[design](design.md)

## How to read and run these tasks

- **One top-level task = one branch = one pull request**, named `<type>/ml-<n>-<slug>`. Sub-tasks are the steps inside it,
  each with its own test, written first and seen failing (red → green).
- **Before a task**, run `make task-check TASK=<n> SPEC=mvp-lineup`. It checks that the task's dependencies are ticked, that
  every step names its requirements and test, and that its ADRs are Accepted. Task 1's branch makes this spec the default
  (`CURRENT_SPEC` in `scripts/checks/task_check.py`).
- **A ticked box** (`- [x]`) marks a task or step as done; the agent ticks it on the task's branch.
- **The property tests P1–P10 in the design are required.** No task is optional.
- **Each task ends with the task report**; the owner approves the pull request, the agent squash-merges it.
- **Breaking the code on purpose** has found tests that couldn't fail, in every slice so far. Each code task does it once before
  its report, and says what it found.
- **Tests for this spec** live in a `lineup/` folder in each test layer:
  - squads are invented, and a real squad never reaches the repository, fixtures or committed logs;
  - tests never touch the internet: the collector runs against the local server on 127.0.0.1.
- **The order:** 1 and 2 in turn; then 3 and 4 in either order, since the engine is pure; then 5, 6, 7, 8 and 9.

## Tasks

- [x] 1. What a choice is worth
  - Branch: `feat/ml-1-worth` · Depends on: none · ADRs: none
  - [x] 1.1 `verdict` keeps ordering by key:
    - `margin` becomes `r_a·r_b·(k_a − k_b)`, and `label` comes from it;
    - the difference in keys stays as `key_margin`, for the flip search and the breakdown;
    - a player with no chance of a rating keeps today's message and the difference in keys.
    - _Requirements: R8.1, R8.2_
    - _Test: `tests/unit/lineup/test_worth.py::test_margin_is_what_the_choice_is_worth`, `::test_no_chance_of_a_rating`;
      **P7** `tests/property/lineup/test_worth.py::test_p7_worth_is_bounded_and_keeps_the_order`;
      **AT-11** `tests/acceptance/lineup/test_worth.py::test_at11_backup_keeper_is_a_coin_flip`_
  - [x] 1.2 The documents and tests that move:
    - the formula in `docs/method.md` §A3, and a note on `mvp-x-or-y` R10.2;
    - `mvp-x-or-y` AT-3 (method §A9 test 6) moves from "clear" to "lean", with its order unchanged;
    - the agent prompt's wording of the margin stays as it is: it's still true, and task 8 rewrites the prompt, so players
      re-paste it once;
    - this spec becomes the default for `make task-check` (`CURRENT_SPEC`, `CLAUDE.md`).
    - _Requirements: R8.1_
    - _Test: `tests/acceptance/xy/test_method.py::test_at3_bench_cover_changes_verdict`;
      `tests/unit/checks/test_task_check.py::test_default_is_the_current_spec`_

- [x] 2. Tidy and speed up
  - Branch: `refactor/ml-2-advisor` · Depends on: 1 · ADRs: none
  - [x] 2.1 `mcp/advisor.py`:
    - the facts, the models, the advisor and the shared steps move there from `mcp/tools/compare.py`, with no change of
      behaviour, and the tests change only what they import;
    - `answer_at` is split around `gather(players, as_of)`, which returns each player's facts and what's missing;
    - missing facts are sorted into needed and better to have.
    - _Requirements: R3.1, R5.5_
    - _Test: the existing suite, passing with only its imports changed;
      `tests/integration/lineup/test_gather.py::test_needed_and_better_to_have`,
      `::test_x_or_y_still_asks_for_what_is_only_better_to_have`_
  - [x] 2.2 Faster reads:
    - `_words` and `_spellings` cached, and each distinct name of a club resolved once per `availability` call;
    - `Facts.read(lake, as_of)` reads only the 14 days up to `as_of`, filtered in DuckDB;
    - a replay still works, and movement older than 7 days has no earlier value;
    - freshness worked out once per kickoff: on a real squad, the slowest step left once names were cached.
    - A real squad's 25 names took 1.27 s before this task and 0.35 s after it (2026-11-04).
    - _Requirements: R4.6_
    - _Test: `tests/integration/lineup/test_reads.py::test_window_moves_with_as_of`, `::test_old_rows_left_out`,
      `::test_an_answer_reads_what_the_collector_just_stored`, `::test_each_name_resolved_once_per_call`,
      `::test_a_whole_squad_reads_quickly`; `tests/integration/lineup/test_gather.py::test_freshness_is_each_match_own`_

- [x] 3. Rules and squads
  - Branch: `feat/ml-3-rules-squads` · Depends on: 2 · ADRs: none
  - [x] 3.1 `LeagueRules` 1.1.0 with an optional `lineup: LineupRules`:
    - format, thresholds, bench size, substitutions and their mode, formations, the no-rating vote and other rules;
    - impossible values refused with the reason;
    - the schema snapshot and changelog entry.
    - _Requirements: R2.1, R2.3, R2.4_
    - _Test: `tests/contract/test_lineup_contracts.py::test_lineup_rules`, `::test_impossible_values_refused`,
      `::test_stored_rules_without_lineup_stay_valid`_
  - [x] 3.2 `set_league_rules` takes them, and `lineup_setup_step` offers the most common values for what's unset, while
    "X or Y?" keeps working with only bonuses and maluses.
    - _Requirements: R2.1, R2.2, R2.4_
    - _Test: `tests/unit/lineup/test_league_setup.py::test_asks_for_just_what_is_unset`,
      `::test_thresholds_not_asked_of_a_total_points_league`, `::test_a_partial_lineup_fills_in_the_stored_one`;
      **AT-8** `tests/acceptance/lineup/test_rules.py::test_at8_setup_step_only_for_what_is_missing`,
      `::test_at8_an_impossible_value_is_rejected_with_the_reason`; `best_lineup` returning the step is in task 5.1_
  - [x] 3.3 `set_squad(players, team="mine")`:
    - a name with an optional club, resolved among the club's players;
    - any name that doesn't resolve stores nothing and comes back with its candidates;
    - it returns the squad by role, and says if an allowed formation can't be fielded;
    - several squads per user by team name, stored in git-ignored `data/local/league/`;
    - if nobody is known yet, it first asks the collector for the statistics page.
    - _Requirements: R1.1, R1.2, R1.3, R1.5_
    - _Test: **P8** `tests/property/lineup/test_squads.py::test_p8_any_order_gives_the_same_players`,
      `::test_p8_any_name_that_fails_stores_nobody`;
      `tests/unit/lineup/test_squads.py::test_a_formation_short_in_one_line_cannot_be_fielded`;
      **AT-7** `tests/acceptance/lineup/test_squad.py::test_at7_set_squad`, `::test_at7_says_what_it_cannot_field`,
      `::test_at7_reads_the_statistics_page_if_nobody_is_known`_

- [x] 4. The engine
  - Branch: `feat/ml-4-engine` · Depends on: 1 · ADRs: none
  - [x] 4.1 `arrange(candidates, formation, rules, start, leave_out)`, pure:
    - each role by key, the top fielded and the rest on the bench in order;
    - a player with no chance of a rating last;
    - a club's keepers as one place;
    - a bench with too many players loses the lowest key, among those who aren't first in their role.
    - _Requirements: R3.2, R3.3_
    - _Test: `tests/unit/lineup/test_arrange.py`;
      **P1** `tests/property/lineup/test_arrange.py::test_p1_fills_the_formation`,
      **P2** `::test_p2_one_keeper_of_a_club`;
      **AT-1** `tests/acceptance/lineup/test_ordering.py::test_at1_sorting_by_key_is_optimal`_
  - [x] 4.2 `simulate`, pure, seeded and standard-library only, drawing 10,000 rounds once and scoring every arrangement on them:
    - each match's goals drawn once, each goal and assist to at most one squad player;
    - who plays, from each player's chances;
    - scores, with the new starting values in `constants.py`.
    - _Requirements: R4.2, R4.3, R4.6_
    - _Test: `tests/unit/lineup/test_points.py`;
      **P2** `tests/property/lineup/test_simulate.py::test_p2_a_clubs_keepers_never_start_together`,
      `::test_each_goal_goes_to_at_most_one_player`, `::test_each_assist_goes_to_at_most_one_player`,
      **P4** `::test_p4_means_match_the_models`, `::test_p4_keepers_match_their_model`,
      **P6** `::test_p6_same_inputs_same_results`, `::test_p6_simulate_is_repeatable`;
      **AT-2** `tests/acceptance/lineup/test_simulation.py::test_at2_a_goal_against_your_own_keeper`_
  - [x] 4.3 Substitutions and thresholds:
    - the league's mode and cap, a keeper only for a keeper, a cameo with a rating blocking his substitute, a formation change
      only into an allowed formation;
    - the score converted through the thresholds;
    - each arrangement's mean, 10th and 90th percentiles, expected fantasy goals and threshold chances.
    - _Requirements: R4.1, R4.4, R4.5_
    - _Test: **P3** `tests/property/lineup/test_simulate.py::test_p3_substitutions_keep_the_rules`,
      **P5** `::test_p5_thresholds_never_fall`;
      **AT-3** `tests/acceptance/lineup/test_simulation.py::test_at3_substitution_rules`,
      **AT-4** `::test_at4_thresholds`_

- [ ] 5. `best_lineup`
  - Branch: `feat/ml-5-best-lineup` · Depends on: 3, 4 · ADRs: none
  - [ ] 5.1 The tool, with the statuses `setup`, `squad`, `choose`, `refresh` and `lineup`:
    - the same steps first as the other tools;
    - a stored player no longer listed is named and left out.
    - _Requirements: R3.1, R2.2, R1.4_
    - _Test: `tests/integration/lineup/test_best_lineup.py::test_statuses`, `::test_player_no_longer_listed`_
  - [ ] 5.2 The answer:
    - the summary, starters, bench, formations, who's out or doubtful, likely scorers, what moved and what to check before the
      lock;
    - each source once, and under 15 KB;
    - the formation with the most fantasy goals, or the highest score in a total-points league.
    - _Requirements: R3.4, R5.1, R5.3, R5.4, R6.1_
    - _Test: **AT-5** `tests/acceptance/lineup/test_lineup.py::test_at5_the_formation_falls_out_of_the_marginal_players`,
      **AT-6** `::test_at6_bench_and_keepers`, **AT-9** `::test_at9_same_facts_fast_and_small`_
  - [ ] 5.3 Warnings and `improve`:
    - every number on basic data is warned about, and a lineup is never held back for it;
    - better data is listed with its pages and search hints;
    - a league's rules this spec leaves out are named in every lineup.
    - _Requirements: R2.3, R5.5, R5.6_
    - _Test: **AT-14** `tests/acceptance/lineup/test_lineup.py::test_at14_warnings_and_improve`;
      `tests/integration/lineup/test_best_lineup.py::test_rules_left_out_are_named`_
  - [ ] 5.4 The decision log's `kind="lineup"`, with every squad player's chances, and earlier lines still read.
    - _Requirements: R7.1_
    - _Test: `tests/integration/lineup/test_best_lineup.py::test_lineup_logged`, `::test_earlier_lines_still_read`_

- [ ] 6. Overrides and calls
  - Branch: `feat/ml-6-overrides` · Depends on: 5 · ADRs: none
  - [ ] 6.1 `calls`, the two or three that matter: the formation, from the marginal players of each role, and the closest
    choices between a starter and the player behind him, each with what it's worth. Within 0.15 points the formation is a coin
    flip, and the answer says which has the higher ceiling.
    - _Requirements: R3.4, R5.2_
    - _Test: `tests/integration/lineup/test_calls.py::test_calls_that_matter`, `::test_coin_flip_names_the_ceiling`_
  - [ ] 6.2 `start`, `leave_out` and `formation`: that lineup, with its cost against the recommendation in points and
    threshold chances, from the same simulated rounds. An override that can't be fielded is refused with the reason.
    - _Requirements: R3.5_
    - _Test: **AT-10** `tests/acceptance/lineup/test_overrides.py::test_at10_an_override_and_its_cost`;
      `tests/integration/lineup/test_calls.py::test_override_refused`_
  - [ ] 6.3 `compare_players`' two-role message points to `best_lineup` when the user has a squad.
    - _Requirements: R6.2_
    - _Test: `tests/integration/lineup/test_calls.py::test_two_roles_with_a_squad`_

- [ ] 7. Calibration
  - Branch: `feat/ml-7-calibration` · Depends on: 5 · ADRs: ADR-0006
  - [ ] 7.1 The finished round's page: read once, 12 hours after the round's last kickoff, as its own page kind, so it never
    delays a read of the current round's page. A failed read is tried again, no more often than every 15 minutes.
    - _Requirements: R7.2_
    - _Test: `tests/unit/lineup/test_finished_round.py::test_when_a_round_has_finished`,
      `tests/integration/lineup/test_finished_round.py::test_read_once`, `::test_current_round_reads_not_delayed`,
      `::test_failed_read_tried_again`_
  - [ ] 7.2 `domains/calibration.py`, scoring both sets apart:
    - what users were told, and the model on everyone with the official lineup left out;
    - starting, getting a rating, scoring if he started, and a clean sheet if he started;
    - the Brier score and reliability by bucket, next to always guessing the set's average;
    - what couldn't be scored and why, with no page text.
    - _Requirements: R7.2, R7.3, R7.4_
    - _Test: **P9** `tests/property/lineup/test_calibration.py::test_p9_brier_scores_are_bounded`,
      **P10** `::test_p10_nothing_after_kickoff`;
      `tests/unit/lineup/test_calibration.py::test_hand_worked_scores`, `::test_unscored_named_with_the_reason`_
  - [ ] 7.3 A round scores itself:
    - `collect --due` and an answer check for a finished, unscored round; an answer does it first, except in the last hour before
      a deadline, and carries on if it fails;
    - the result stored under `data/local/calibration/`, `fantadamus calibrate --round N` to print it and `--again` to recompute
      it;
    - `best_lineup`'s `last_round` line;
    - the time measured against the 5-second budget; if scoring everyone runs over, that set moves to `collect --due` and the
      command, and the task report says so.
    - _Requirements: R7.2, R7.5, R7.6_
    - _Test: **AT-12** `tests/acceptance/lineup/test_calibration.py::test_at12_a_round_scores_itself`_

- [ ] 8. The agent prompt, the league profile and the docs
  - Branch: `docs/ml-8-prompt` · Depends on: 6, 7 · ADRs: none
  - [ ] 8.1 The agent prompt:
    - `set_squad` and `best_lineup`, and formats 2, 3 and 6;
    - using the league profile when the Project has one: rules and squads saved on first use, and preferences that shape the
      explanation, never the numbers;
    - warnings given, `improve` tried once, an override's cost stated once and then help with the user's choice;
    - `last_round` said once;
    - two roles with a squad point to `best_lineup`.
    - _Requirements: R9.1, R9.4, R6.2_
    - _Test: `tests/unit/test_repo_hygiene.py::test_agent_prompt_covers_the_lineup`; the prompt's size stays within what a
      Project takes_
  - [ ] 8.2 The blank league profile, tied to the rules so that a new setting can't be forgotten, and holding no user's details.
    - _Requirements: R9.3_
    - _Test: **AT-15** `tests/acceptance/lineup/test_profile.py::test_at15_the_profile_names_every_setting`_
  - [ ] 8.3 The README, the player guide and `docs/answer-formats.md`: what Fantadamus now answers, how to give a squad and
    rules, and where the profile goes.
    - _Requirements: R9.2_
    - _Test: `tests/unit/test_repo_hygiene.py::test_player_guide_covers_the_lineup`_

- [ ] 9. The real round and Phase 2's gate
  - Branch: `docs/ml-9-gate` · Depends on: 8 · ADRs: none
  - [ ] 9.1 Testing from Claude Code on real data, with the local tools and a real squad kept in private memory: a draft, a check
    after the official lineups, an override and a league-mate's squad. Bugs found get their own failing tests and fixes.
    Results stay out of the repository.
    - _Requirements: R3.1, R5.1, R5.5, R7.1_
    - _Test: what each answer used, and the time and size of each, recorded in the report without players' figures_
  - [ ] 9.2 **Owner:** give a real squad and rules in Claude Desktop, and compare a lineup for a real round with your own
    choice.
    - _Requirements: AT-13_
    - _Test: recorded in the report, without players' figures_
  - [ ] 9.3 The first calibration report, in `docs/reports/`, aggregates only, after a real round has finished:
    - both sets, and what couldn't be scored;
    - whether 12 hours was long enough for the statistics page;
    - whether a finished page keeps the outlets' last percentages, against a read before kickoff;
    - any change proposed to a starting value, for the owner to approve.
    - _Requirements: R7.2, R7.4, R7.6_
    - _Test: the report exists with every section, and names the round; no player's figures in it_
  - [ ] 9.4 A mutation-testing run on the core modules (`engine/`, `domains/calibration.py`), with survivors looked at. If `mutmut`
    won't run on the owner's Mac, say so and ask before choosing another way.
    - _Requirements: R3.2, R4.1, R7.2; phase gate (`quality.md`)_
    - _Test: the score and the survivors, in the phase report_
  - [ ] 9.5 The phase report: tests, coverage, quality results, cost and open risks, all six of method §A9, and the acceptance
    tests of this slice.
    - _Requirements: Phase gate (`quality.md`), R9.2_
    - _Test: the report exists with every section; `make check` green on `main`_
  - [ ] 9.6 **Owner:** sign off Phase 2 → Phase 3 may start
    - _Requirements: Phase gate (`quality.md`)_
    - _Test: sign-off recorded in the phase report_
