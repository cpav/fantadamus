# Implementation Plan: `mvp-rules` (Phase 2, fourth slice)

Status: **Approved by the owner, 2026-11-07** · From the approved [requirements](requirements.md) and the [design](design.md)

## How to read and run these tasks

- **One top-level task = one branch = one pull request**, named `<type>/ru-<n>-<slug>`. Sub-tasks are the steps inside it, each with its own
  test, written first and seen failing (red → green).
- **Before a task**, run `make task-check TASK=<n> SPEC=mvp-rules`. Task 1's branch makes this spec the default (`CURRENT_SPEC` in
  `scripts/checks/task_check.py`, and `CLAUDE.md`).
- **A ticked box** (`- [x]`) marks a task or step as done; the agent ticks it on the task's branch.
- **The property tests P1–P7 in the design are required.** No task is optional.
- **Each task ends with the task report**; the owner approves the pull request, the agent squash-merges it.
- **Breaking the code on purpose:** each code task does it once before its report, and says what it found.
- **Tests for this spec** live in a `rules/` folder in each test layer. Rules and squads are invented, and a real rulebook or league name never
  reaches the repository, fixtures or committed logs.
- **Never run a real collection from an unmerged branch:** a line it logs may not be readable by the code on `main`.

## Tasks

- [x] 1. One table of events
  - Branch: `feat/ru-1-events` · Depends on: none · ADRs: none
  - [x] 1.1 `LeagueRules` 2.0.0: one table, with Classic as a ready-made entry; rules in the earlier form, in a file or a log line, read as the same table. This spec becomes the current one.
    - _Requirements: R1.1, R1.6_
    - _Test: **P3** `tests/property/rules/test_events.py::test_p3_a_row_changes_only_its_roles`, **P6** `::test_p6_earlier_rules_convert`;
      `tests/unit/rules/test_events.py::test_an_event_not_in_the_table_isnt_scored`, `::test_a_second_row_for_one_event_and_role_is_refused`,
      `::test_a_value_of_the_wrong_sign_or_size_is_refused`, `::test_an_old_log_line_still_reads`_
  - [x] 1.2 One calculation for the models and the simulation; the four events priced as a fixed term; a cameo's goal follows the league's goal value.
    - _Requirements: R1.2, R1.3, R1.6_
    - _Test: **AT-1** `tests/acceptance/rules/test_events.py::test_at1_stored_rules_differ_only_by_the_four`, **AT-2** `::test_at2_the_four_by_hand`;
      **P4** `tests/property/rules/test_events.py::test_p4_the_mean_matches_the_model`;
      `tests/unit/rules/test_events.py::test_a_cameos_goal_follows_the_league`, `::test_a_cameos_goal_follows_the_league_in_the_rounds`, `::test_a_keepers_rare_events_reach_the_rounds`, `::test_an_outfielders_rare_events_reach_the_rounds`, `::test_event_points_by_hand`, `::test_rare_points_by_hand`,
      `::test_a_clean_sheet_counts_only_with_no_goals_against`_
  - [x] 1.3 An outfield role's clean sheet, on the same simulated goals as his keeper.
    - _Requirements: R1.1, R1.4_
    - _Test: **AT-3** `tests/acceptance/rules/test_events.py::test_at3_a_defenders_clean_sheet`, `::test_at3_through_the_tools`, `::test_at3_a_goal_per_role_still_works`_
  - [x] 1.4 Share-based events, folded into their base event's worth.
    - _Requirements: R1.5_
    - _Test: **AT-4** `tests/acceptance/rules/test_events.py::test_at4_share_events_by_hand`_

- [x] 2. Formula rules, pure
  - Branch: `feat/ru-2-formula` · Depends on: 1 · ADRs: none
  - [x] 2.1 `FormulaRule` and its parts in the contract, with the validators; no rule can carry code.
    - _Requirements: R2.1, R2.4_
    - _Test: **AT-11** `tests/acceptance/rules/test_formula.py::test_at11_an_impossible_rule_is_refused`, `::test_at11_a_rule_cant_carry_code`,
      `::test_at11_two_rules_with_one_name_are_refused`, `::test_at11_a_league_keeps_its_rules`;
      `tests/integration/rules/test_interim.py::test_a_formula_rule_is_named_until_it_is_priced`_
  - [x] 2.2 `engine/formula.py`: the unit, who's left out, stand-ins, the condition, how they combine, and the bands.
    - _Requirements: R2.1, R2.2_
    - _Test: **AT-5** `tests/acceptance/rules/test_formula.py::test_at5_the_defence_modifier_by_hand`, `::test_at5_a_stand_in_and_the_condition`;
      **AT-6** `::test_at6_the_attack_modifier_by_hand`;
      **P1** `tests/property/rules/test_formula.py::test_p1_a_value_gets_its_bands_points`;
      `tests/unit/rules/test_formula.py::test_a_sum`, `::test_more_than_the_base_counts_the_best`, `::test_no_stand_in_averages_those_present`,
      `::test_nobody_and_no_stand_in_gives_nothing`, `::test_a_captain_rule`_

- [x] 3. Formula rules in the simulation and the answer
  - Branch: `feat/ru-3-simulate` · Depends on: 2 · ADRs: none
  - [x] 3.1 Marks from `draw_marked`, only when a league has formula rules; rules worked out after substitutions, in each arrangement's total.
    - _Requirements: R2.2, R3.1, R3.4_
    - _Test: **AT-8** `tests/acceptance/rules/test_simulation.py::test_at8_a_rules_points_reach_the_fantasy_goals`, `::test_at8_a_modifier_can_change_the_formation`,
      `::test_at8_a_total_points_league`; **P2** `tests/property/rules/test_simulation.py::test_p2_zero_bands_change_nothing`,
      **P5** `::test_p5_the_same_inputs_the_same_results`; `tests/unit/rules/test_marks.py::test_a_starters_mark_is_his_score_without_the_events`,
      `::test_a_cameos_mark`, `::test_marking_changes_no_round`; `tests/unit/rules/test_formula.py::test_the_best_are_the_highest_votes_whatever_their_order`_
  - [x] 3.2 What each rule is worth in the answer and the log, an override's cost, and a close call a rule could tip.
    - _Requirements: R3.2, R3.4, R3.5_
    - _Test: **AT-9** `tests/acceptance/rules/test_simulation.py::test_at9_each_rules_worth_is_in_the_answer`, `::test_at9_an_overrides_cost_includes_the_rules`;
      `tests/integration/rules/test_answer.py::test_a_close_call_says_a_rule_could_tip_it`_
  - [x] 3.3 The budget, measured on the invented squad and the real one.
    - _Requirements: R5.1, R5.2_
    - _Test: **AT-12** `tests/acceptance/rules/test_simulation.py::test_at12_a_squad_with_rules_stays_in_budget`_

- [ ] 4. The captain
  - Branch: `feat/ru-4-captain` · Depends on: 3 · ADRs: none
  - [ ] 4.1 The recommended captain and vice from the rounds, a named captain with its cost, the vice when the captain has no rating, and the stand-in.
    - _Requirements: R3.3_
    - _Test: **AT-7** `tests/acceptance/rules/test_captain.py::test_at7_the_table_by_hand`, `::test_at7_the_vice_covers`, `::test_at7_the_recommended_captain_is_the_best`,
      `::test_at7_naming_another_gives_its_cost`; **P7** `tests/property/rules/test_captain.py::test_p7_a_captains_points_stay_in_the_bands`_

- [ ] 5. The translator
  - Branch: `feat/ru-5-translator` · Depends on: 3, 4 · ADRs: none
  - [ ] 5.1 `set_league_rules` returns what's priced and what's left out; a rule the engine can't price goes in `other_rules` with what it needs, and every answer names it.
    - _Requirements: R2.5, R4.2, R4.3, R4.4_
    - _Test: **AT-10** `tests/acceptance/rules/test_translator.py::test_at10_left_out_rules_are_named`, `::test_at10_the_read_back`_
  - [ ] 5.2 One setup step, with the ready-made entries; the schema's descriptions; the agent prompt within its budget; the blank profile and the player guide.
    - _Requirements: R2.3, R4.1, R4.5_
    - _Test: **AT-13** `tests/acceptance/rules/test_translator.py::test_at13_the_profile_names_the_new_settings`, `::test_at13_the_ready_made_entries_are_valid`;
      `tests/unit/test_repo_hygiene.py::test_agent_prompt_covers_the_lineup`_
  - [ ] 5.3 `docs/league-rules.md` and the method's sections.
    - _Requirements: R5.3, R4.5_
    - _Test: `tests/unit/test_repo_hygiene.py::test_league_rules_guide_covers_the_vocabulary`_

- [ ] 6. A real check and this slice's sign-off
  - Branch: `docs/ru-6-gate` · Depends on: 5 · ADRs: none
  - [ ] 6.1 Real data from Claude Code, with temporary logs: the owner's league gets today's numbers apart from the four events, and a made-up league with a defence modifier and a captain gets a sensible lineup. Bugs found get their own failing tests and fixes. Results stay out of the repository.
    - _Requirements: R1.6, R3.1, R5.1_
    - _Test: what each answer used, and its time and size, in the report without players' figures_
  - [ ] 6.2 **Owner:** paste a real rulebook, your friend's if you can, into a Claude app, and check what it read back.
    - _Requirements: AT-14_
    - _Test: recorded in the report, without the league's details_
  - [ ] 6.3 A mutation run on the core modules, with survivors read; the slice report: tests, coverage, quality, cost, open risks and the acceptance tests.
    - _Requirements: R5.1, R5.2; phase gate (`quality.md`)_
    - _Test: the report exists with every section; `make check` green on `main`_
  - [ ] 6.4 **Owner:** sign off this slice → the next slice in `product.md` may start, after a real round has been answered on these numbers.
    - _Requirements: Phase gate (`quality.md`)_
    - _Test: sign-off recorded in the report_
