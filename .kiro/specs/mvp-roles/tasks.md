# Implementation Plan: `mvp-roles` (Phase 2, second slice)

Status: **Proposed 2026-11-03, for the owner's review** · From the approved [requirements](requirements.md) and
[design](design.md) · No task starts until `mvp-collect` is signed off

## How to read and run these tasks

- **One top-level task = one branch = one pull request**, named `<type>/mr-<n>-<slug>`. Sub-tasks are the
  steps inside it, each with its own test, written first and seen failing (red → green).
- **Before a task**, run `make task-check TASK=<n> SPEC=mvp-roles`. It checks that the task's dependencies are
  ticked, that every step names its requirements and test, and that its ADRs are Accepted. Task 1's branch
  switches `CURRENT_SPEC` in `scripts/checks/task_check.py` to this spec, after `mvp-collect`'s sign-off.
- **A ticked box** (`- [x]`) marks a task or step as done; the agent ticks it on the task's branch.
- **The property tests P1–P7 in the design are required.** No task is optional.
- **Each task ends with the task report**; the owner approves the pull request, the agent squash-merges it.
- **Tests for this spec** live in a `roles/` folder in each test layer:
  - the statistics page is a synthetic copy of the real page's structure, with the test clubs and invented
    players, built by `tests/collect_pages.py`;
  - tests never touch the internet: the collector runs against the local server on 127.0.0.1.
- **The order:** 1, 2, 3 in turn; 4 at any time, since the engine is pure; then 5, 6, 7 and 8.

## Tasks

- [ ] 1. Contracts and storage for the statistics page
  - Branch: `feat/mr-1-season-stats` · Depends on: none · ADRs: ADR-0006
  - [ ] 1.1 `PlayerSeasonPayload` 1.1.0 and `SeasonStatsPayload` 1.0.0:
    - `goals_conceded`, and the appearances description;
    - the goals-conceded rules;
    - one shared definition of a player's row and its checks, each player once per read;
    - the schema snapshots and changelog entries.
    - _Requirements: R6.1, R6.2, R1.3_
    - _Test: `tests/contract/test_roles_contracts.py::test_goals_conceded_rules`, `::test_season_stats_players_once`,
      `::test_profile_without_goals_conceded_still_valid`_
  - [ ] 1.2 The `season_stats` domain:
    - one bronze record per read;
    - `silver.season_stats`, with `goals_conceded` on both season tables;
    - a read missing a club, with a club without a keeper, or naming an unknown club is refused with the reason.
    - _Requirements: R1.1, R1.6, R6.1_
    - _Test: `tests/integration/roles/test_season_stats.py::test_one_record_per_read`, `::test_incomplete_read_refused`_
  - [ ] 1.3 Gold reads both season tables as one:
    - the newest row of a player wins, whichever page it came from;
    - every player read is known to name resolution;
    - the cost of reading the larger table is measured.
    - _Requirements: R1.1_
    - _Test: `tests/unit/roles/test_season_gold.py::test_newest_figures_win`, `::test_every_player_known`_

- [ ] 2. The statistics reader
  - Branch: `feat/mr-2-stats-reader` · Depends on: 1 · ADRs: ADR-0006
  - [ ] 2.1 `read_stats` on a synthetic statistics page:
    - the fields of design C3;
    - the fantamedia, penalties saved and red cards not read;
    - `0,0` read as no average;
    - appearances set to the rated appearances;
    - a bad row left out with its reason;
    - an unexpected layout unreadable.
    - _Requirements: R1.2, R1.3, R1.6_
    - _Test: `tests/unit/roles/test_read_stats.py::test_rows_read`, `::test_no_rating_no_average`,
      `::test_bad_row_left_out`, `::test_unexpected_layout_unreadable`;
      **P1** `tests/property/roles/test_read_stats.py::test_p1_any_order_and_partial_pages`_
  - [ ] 2.2 An optional check on the pages saved under `data/private/pages/`, skipped with the registered reason
    when they're absent:
    - the statistics page reads in full;
    - every outlet name on the saved round page resolves to one player of its club.
    - _Requirements: R1.2, R1.6_
    - _Test: `tests/contract/test_real_pages.py::test_saved_statistics_page`, `::test_round_page_names_resolve`_
  - [ ] 2.3 The statistics page in the reading list (first for `player_season`) and in the source registry
    - _Requirements: R7.2_
    - _Test: `tests/unit/test_sources_config.py::test_statistics_page_listed_first`, `::test_collector_page_is_allowed`_

- [ ] 3. The collector reads two pages
  - Branch: `feat/mr-3-two-pages` · Depends on: 2 · ADRs: ADR-0006
  - [ ] 3.1 The `[collector]` table's `statistics` and `statistics_enabled`:
    - `collect(round, facts)` reads the pages the facts need, with one report each and one fetcher per run;
    - an unchanged read confirms the figures;
    - a failure lists `player_season` for Claude.
    - _Requirements: R1.1, R1.5, R1.6_
    - _Test: `tests/integration/roles/test_two_pages.py::test_reads_the_pages_asked_for`,
      `::test_statistics_failure_for_claude`;
      **AT-6** `tests/acceptance/roles/test_statistics.py::test_at6_statistics_collected`;
      **P2** `tests/property/roles/test_two_pages.py::test_p2_same_page_stores_nothing_new`_
  - [ ] 3.2 The cadence and freshness:
    - `player_season` due daily, counted from its own page's last attempt;
    - the season figures fresh for 48 hours;
    - `collect --due` reads only the pages due.
    - _Requirements: R1.4_
    - _Test: `tests/unit/roles/test_cadence.py::test_statistics_daily`, `::test_last_attempt_per_page`,
      `::test_season_figures_fresh_for_48_hours`_
  - [ ] 3.3 `collect` and `fantadamus collect` take the fact, and read both pages by default
    - _Requirements: R1.4_
    - _Test: `tests/integration/roles/test_collect_tool.py::test_tool_and_command_choose_the_fact`_

- [ ] 4. The engine for every role
  - Branch: `feat/mr-4-engine` · Depends on: none · ADRs: none
  - [ ] 4.1 `engine/rank.py`, from `forwards.py`:
    - the option, key, cover, label and verdict;
    - the flip search, for any value function and bound.
    - The forward tests pass unchanged, apart from their imports.
    - _Requirements: R2.6, R4.1_
    - _Test: `tests/unit/xy/test_forwards.py` (unchanged); `tests/acceptance/xy/test_method.py` (unchanged);
      **P7** `tests/property/roles/test_rank.py::test_p7_order_asked_doesnt_matter`_
  - [ ] 4.2 The outfield model:
    - the priors table by Mantra role, with its fallbacks and weights;
    - the penalty term at his own minutes;
    - the flat 5.5 cameo;
    - the goal bonus of his Classic role.
    - _Requirements: R2.1, R2.2, R2.3, R2.4, R2.5, R2.6_
    - _Test: `tests/unit/roles/test_outfield.py::test_priors_by_role`, `::test_t_takes_attacking_midfielder_priors`;
      **AT-4** `tests/acceptance/roles/test_engine.py::test_at4_role_priors`,
      **AT-5** `::test_at5_defenders_bench_advice`;
      **P5** `tests/property/roles/test_outfield.py::test_p5_priors_without_games`,
      **P6** `::test_p6_goal_bonus_never_lowers`_
  - [ ] 4.3 The keeper model:
    - skill, its prior and its shrinkage;
    - the expected vote, P(clean sheet) and E_start;
    - no cameo;
    - the flip on the opponent's xG.
    - `Scoring` gains the clean sheet and the goal conceded.
    - _Requirements: R3.1, R3.2, R3.3, R3.4, R4.1_
    - _Test: `tests/unit/roles/test_keepers.py::test_keeper_value_steps`, `::test_flip_on_opponent_xg`;
      **AT-1** `tests/acceptance/roles/test_engine.py::test_at1_keepers_on_regressed_form`,
      **AT-2** `::test_at2_same_skill_same_vote`, **AT-3** `::test_at3_clean_sheet_from_the_fit`;
      **P3** `tests/property/roles/test_keepers.py::test_p3_skill_net_of_conceded`,
      **P4** `::test_p4_clean_sheet_falls_with_opponent_xg`_
  - [ ] 4.4 Two keepers of the same club: the likelier starter first, labelled `covered`
    - _Requirements: R3.6_
    - _Test: `tests/unit/roles/test_rank.py::test_same_club_keepers_covered`_

- [ ] 5. `compare_players` for every role
  - Branch: `feat/mr-5-every-role` · Depends on: 3, 4 · ADRs: ADR-0006
  - [ ] 5.1 The advisor's reads take one name or two:
    - stale or missing season figures call the collector for the statistics page, inside the 60-second budget;
    - the refresh plan lists the statistics page first.
    - _Requirements: R1.4, R1.6, R5.2_
    - _Test: `tests/integration/roles/test_compare_roles.py::test_season_figures_collected_first`,
      `::test_statistics_failure_in_plan`_
  - [ ] 5.2 Same-role verdicts from the matching model:
    - a keeper's answer carries P(clean sheet), his expected goals conceded and his goals conceded;
    - movement adds P(clean sheet);
    - the "won't play" advice names the role.
    - _Requirements: R3.5, R4.1, R4.3_
    - _Test: `tests/integration/roles/test_compare_roles.py::test_keepers_compared`, `::test_defenders_compared`,
      `::test_wont_play_names_the_role`;
      **AT-8** `tests/acceptance/roles/test_answers.py::test_at8_same_club_keepers`_
  - [ ] 5.3 Two roles get the status `outlooks`, no verdict and the formation-call message; `forwards only` goes
    - _Requirements: R4.2_
    - _Test: **AT-7** `tests/acceptance/roles/test_answers.py::test_at7_two_roles_two_outlooks`_
  - [ ] 5.4 The decision log:
    - each entry's kind;
    - optional verdict fields;
    - a keeper's P(clean sheet) and expected goals conceded;
    - earlier lines still read.
    - _Requirements: R6.3, R5.3_
    - _Test: `tests/unit/roles/test_decision_log.py::test_keeper_probabilities_logged`, `::test_earlier_lines_read`_

- [ ] 6. One player's outlook
  - Branch: `feat/mr-6-outlook` · Depends on: 5 · ADRs: ADR-0006
  - [ ] 6.1 `player_outlook`:
    - the same statuses as `compare_players`, or an outlook: the round and its deadline, the rules, the update
      times, what to check before the deadline, and the player with his movement;
    - each outlook logged;
    - served by the MCP server.
    - _Requirements: R5.1, R5.2, R5.3_
    - _Test: `tests/integration/roles/test_outlook.py::test_outlook_statuses`, `::test_outlook_logged`;
      `tests/integration/xy/test_server.py::test_served_tools`;
      **AT-9** `tests/acceptance/roles/test_answers.py::test_at9_outlook_in_one_call`_

- [ ] 7. The agent prompt and docs
  - Branch: `docs/mr-7-prompt` · Depends on: 6 · ADRs: none
  - [ ] 7.1 The agent prompt:
    - every role, `player_outlook`, and two roles answered with outlooks;
    - a keeper's lines, and rated games in a player's form;
    - the MVP section names the statistics page.
    - Also: a keeper's line in `docs/answer-formats.md`, and the README's tool list.
    - _Requirements: R7.1_
    - _Test: `tests/integration/xy/test_server.py::test_prompt_names_every_role`_

- [ ] 8. The real round and the slice gate
  - Branch: `docs/mr-8-report` · Depends on: 7 · ADRs: ADR-0006
  - [ ] 8.1 **Owner:** in Claude Desktop, on a real round:
    - ask "X or Y?" for two keepers, two defenders and two midfielders;
    - ask for one player's outlook;
    - check that the season figures came from the statistics page.
    - _Requirements: AT-10; R1.1, R4.1, R5.1_
    - _Test: what each answer used and the collection log, recorded in the slice report (no page text)_
  - [ ] 8.2 A short slice report in `docs/reports/`: tests, coverage, acceptance tests, the decision log's
    record, open risks
    - _Requirements: R5.3, slice gate (`quality.md`)_
    - _Test: the report exists with every section; `make check` green on `main`_
  - [ ] 8.3 **Owner:** sign off the slice → the full-lineup slice may start
    - _Requirements: Slice gate (`quality.md`)_
    - _Test: sign-off recorded in the slice report_
