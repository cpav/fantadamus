# Implementation Plan: `mvp-review` (Phase 2, fifth slice)

Status: **Approved by the owner, 2026-11-09** · From the approved [requirements](requirements.md) and the [design](design.md)

## How to read and run these tasks

- **One top-level task = one branch = one pull request**, named `<type>/rv-<n>-<slug>`. Sub-tasks are the steps inside it, each with its own
  test, written first and seen failing (red → green).
- **Before a task**, run `make task-check TASK=<n> SPEC=mvp-review`. Task 1's branch makes this spec the default (`CURRENT_SPEC` in
  `scripts/checks/task_check.py`, and `CLAUDE.md`).
- **A ticked box** (`- [x]`) marks a task or step as done; the agent ticks it on the task's branch.
- **The property tests P1–P5 in the design are required.** No task is optional.
- **Each task ends with the task report**; the owner approves the pull request, the agent squash-merges it.
- **Breaking the code on purpose:** each code task does it once before its report, from a green baseline, and says what it found.
- **Tests for this spec** live in a `review/` folder in each test layer. Squads, statistics reads and fielded lineups are invented; a real
  lineup or review never reaches the repository, fixtures or committed logs.
- **Never run a real collection from an unmerged branch:** a line it logs may not be readable by the code on `main`.

## Tasks

- [x] 1. Three more columns of the statistics page
  - Branch: `feat/rv-1-columns` · Depends on: none · ADRs: ADR-0006
  - [x] 1.1 FM, RP and Esp read, kept and named in the reading list; rows stored before stay valid. This spec becomes the current one.
    - _Requirements: R2.1, R5.3_
    - _Test: `tests/contract/test_fcit_stats.py::test_the_three_new_columns`, `::test_a_fantasy_average_below_zero_reads`,
      `::test_a_column_that_changes_meaning_makes_the_page_unreadable`; `tests/unit/review/test_columns.py::test_rows_stored_before_still_read`,
      `::test_the_new_columns_are_bounded`; `tests/integration/review/test_columns_kept.py::test_the_three_columns_are_kept`_

- [x] 2. One round from two reads
  - Branch: `feat/rv-2-round` · Depends on: 1 · ADRs: none
  - [x] 2.1 A player's round: rated or not, the rating from the averages and from FM, the events, an own goal where FM shows one, and each reason
    it can't be known. `domains/review.py` joins the mutation run.
    - _Requirements: R2.1, R2.3_
    - _Test: **AT-2** `tests/acceptance/review/test_round.py::test_at2_a_round_by_hand`, `::test_at2_what_cant_be_known`,
      `::test_at2_a_penalty_scored_and_one_missed`, `::test_at2_an_own_goal_shows_in_the_fantasy_average`, `::test_at2_a_keeper`,
      `::test_at2_a_cameo_without_a_rating`, `::test_at2_late_in_the_season_the_fantasy_average_settles_it`, `::test_at2_a_read_stored_before_the_new_columns`,
      `::test_at2_the_first_round_read_with_the_new_columns`, `::test_at2_a_player_not_yet_rated`,
      `::test_at2_a_fantasy_average_that_disagrees_otherwise_names_no_own_goal`;
      **P1** `tests/property/review/test_round.py::test_p1_the_rating_is_found`, `::test_p1_late_in_the_season_never_a_wrong_rating`, **P2** `::test_p2_a_round_is_never_invented`_

- [x] 3. The real score
  - Branch: `feat/rv-3-score` · Depends on: 2 · ADRs: none
  - [x] 3.1 A lineup's real score as the league scores it: the table, the substitutions on real ratings, the formula rules and the captain on
    real votes, the thresholds, and who makes it unknown.
    - _Requirements: R2.2, R2.3_
    - _Test: **AT-3** `tests/acceptance/review/test_score.py::test_at3_a_real_score_by_hand`, `::test_at3_an_unknown_player`,
      `::test_at3_formula_rules_and_the_captain_on_real_votes`, `::test_at3_a_defenders_clean_sheet_from_his_teams_goals`,
      `::test_at3_what_the_reads_cant_say_is_named`, `::test_at3_penalties_cards_and_saves`, `::test_at3_a_keeper_who_conceded_is_left_out`_

- [x] 4. What the user fielded, and the advice
  - Branch: `feat/rv-4-fielded` · Depends on: 3 · ADRs: none
  - [x] 4.1 The fielded store: names resolved, "as advised", a lineup the league couldn't field refused, saving again replacing, a
    league-mate's team kept apart, all of it private.
    - _Requirements: R1.1, R1.2, R1.3, R1.4, R5.4_
    - _Test: **AT-1** `tests/acceptance/review/test_fielded.py::test_at1_by_name`, `::test_at1_as_advised`, `::test_at1_refused`,
      `::test_at1_saved_again`, `::test_at1_a_bench_longer_than_the_leagues`, `::test_at1_a_name_that_could_be_two_players`_
  - [x] 4.2 The advice: the last lineup logged before the lock, or the advice replayed at the lock and marked so.
    - _Requirements: R3.4, R3.5_
    - _Test: `tests/unit/review/test_advice.py::test_the_last_before_the_lock`, `::test_a_replay_when_none_was_asked`,
      `::test_an_override_shows_the_advice_it_was_priced_against`; `tests/integration/review/test_advice_logged.py::test_an_override_logs_the_advice`_

- [x] 5. Each decision and what it cost
  - Branch: `feat/rv-5-decisions` · Depends on: 4 · ADRs: none
  - [x] 5.1 The decisions listed and paired; each priced on its own, and the whole fielded lineup, over one shared simulation at the lock's
    facts.
    - _Requirements: R3.1, R3.2_
    - _Test: **AT-4** `tests/acceptance/review/test_decisions.py::test_at4_each_decision_by_hand`; **P3**
      `tests/property/review/test_decisions.py::test_p3_the_advice_followed`, **P4** `::test_p4_the_order_doesnt_matter`;
      `tests/unit/review/test_choices_on_the_engine.py::test_following_the_advice_on_the_engine`, `::test_a_swap_and_a_captain_on_the_engine`, `::test_the_vice_covers_in_the_real_score`;
      `tests/unit/rules/test_simulation.py::test_a_named_vice`_
  - [x] 5.2 Each real result beside its cost; following the advice shows the real score against the expected one and its range; a replayed
    advice says so.
    - _Requirements: R3.3, R3.4, R3.5_
    - _Test: **AT-4** `::test_at4_judged_by_the_cost`, `::test_at4_a_bench_order_that_never_came_into_play`, `::test_at4_a_player_whose_round_isnt_known`,
      `::test_at4_pairs_go_best_first`, `::test_at4_a_bench_choice_on_the_eleven_fielded`, `::test_at4_a_swap_that_takes_off_the_captain`,
      `::test_at4_the_choices_made_on_the_advice_give_the_eleven_fielded`, `::test_at4_a_bench_without_a_role`;
      **AT-5** `::test_at5_following_the_advice`, `::test_at5_replayed_when_none_was_asked`_

- [x] 6. The record
  - Branch: `feat/rv-6-record` · Depends on: 5 · ADRs: none
  - [x] 6.1 Each review appended with its snapshots; the record for each user and team, and how much it can tell yet.
    - _Requirements: R4.1, R4.2, R4.3_
    - _Test: **AT-6** `tests/acceptance/review/test_record.py::test_at6_over_several_rounds`, `::test_at6_too_early_to_tell`,
      `::test_at6_a_real_difference_shows`, `::test_at6_an_unknown_gain_isnt_counted`, `::test_at6_logged_with_its_snapshots`;
      **P5** `tests/property/review/test_record.py::test_p5_append_only`_

- [x] 7. The answer and the docs
  - Branch: `feat/rv-7-answer` · Depends on: 6 · ADRs: none
  - [x] 7.1 `review_round`: its statuses, the app total beside the real score, one statistics read when none is stored after the round, and
    format 7 in `docs/answer-formats.md`.
    - _Requirements: R2.4, R3.2, R3.5, R5.1, R5.2, R5.3_
    - _Test: **AT-7** `tests/acceptance/review/test_answer.py::test_at7_the_review`, `::test_at7_the_advice_replayed_when_none_was_asked`,
      `::test_at7_in_budget`; `tests/integration/review/test_tool.py::test_statuses`, `::test_no_statistics_after_the_round`,
      `::test_a_replay_reads_stores_and_logs_nothing`, `::test_a_defenders_clean_sheet_from_his_clubs_keeper`, `::test_after_the_squad_changed`,
      `::test_a_player_nobody_knew_before_the_lock`, `::test_what_it_cant_review`_
  - [x] 7.2 The agent prompt within its budget, the player guide and method §A8.
    - _Requirements: R5.5_
    - _Test: `tests/unit/test_repo_hygiene.py::test_agent_prompt_covers_the_review`_

- [x] 8. A real check and this slice's sign-off
  - Branch: `docs/rv-8-gate` · Depends on: 7 · ADRs: none
  - [x] 8.1 Real data from Claude Code, with temporary logs: round 11 reviewed as far as its reads allow, with what each review used, its time
    and its size. Results stay out of the repository.
    - _Requirements: R2.3, R5.2_
    - _Test: what each review used, and its time and size, in the report without players' figures_
    - Found and fixed (`fix/rv-8-known-facts`): freshness targets kept the facts stored before the lock from being priced, so a review
      takes them whatever their age, at the lock as the design first said; and a replayed advice is worked out from the same facts as the
      prices, read once. _Test: `tests/integration/review/test_tool.py::test_news_after_the_advice_is_priced`;
      `tests/acceptance/review/test_answer.py::test_at7_in_budget` (now with the replay)_
  - [x] 8.2 **Owner:** review your real round 12 in a Claude app, and check its real score against your league's app.
    - _Requirements: AT-8 (R2.4, R5.1)_
    - _Test: recorded in the report, without the team's details_
    - Taken on round 11 from here at the owner's request, 2026-11-11; the league app's total is still to compare.
  - [x] 8.3 A mutation run on the core modules, with survivors read; the slice report: tests, coverage, quality, cost, open risks and the
    acceptance tests.
    - _Requirements: R5.2; phase gate (`quality.md`)_
    - _Test: the report exists with every section; `make check` green on `main`_
  - [x] 8.4 **Owner:** sign off this slice.
    - _Requirements: Phase gate (`quality.md`)_
    - _Test: sign-off recorded in the report_
