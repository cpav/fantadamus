# Implementation Plan: `mvp-cards` (Phase 2, sixth slice)

Status: **Approved by the owner, 2026-11-10** · From the approved [requirements](requirements.md) and the [design](design.md)

## How to read and run these tasks

- **One top-level task = one branch = one pull request**, named `<type>/cd-<n>-<slug>`. Sub-tasks are the steps inside it, each with its own
  test, written first and seen failing (red → green).
- **Before a task**, run `make task-check TASK=<n> SPEC=mvp-cards`. Task 1's branch makes this spec the default (`CURRENT_SPEC` in
  `scripts/checks/task_check.py`, and `CLAUDE.md`).
- **A ticked box** (`- [x]`) marks a task or step as done; the agent ticks it on the task's branch.
- **The property tests P1–P5 in the design are required.** No task is optional.
- **Each task ends with the task report**; the owner approves the pull request, the agent squash-merges it.
- **Breaking the code on purpose:** each code task does it once before its report, from a green baseline, and says what it found.
- **Tests for this spec** live in a `cards/` folder in each test layer. Clubs, players, odds and tables are invented; a real page or card
  never reaches the repository.
- **Never run a real collection from an unmerged branch:** a line it logs may not be readable by the code on `main`.

## Tasks

- [x] 1. The table's record and form
  - Branch: `feat/cd-1-table` · Depends on: none · ADRs: ADR-0006
  - [x] 1.1 `TeamRow` gains wins, draws, losses and the last five results, optional and checked against the record; Fantadamus reads the
    table page daily, with Claude as the fallback; tables stored before stay valid. The order of the form is checked against the recorded
    calendar's results. This spec becomes the current one.
    - _Requirements: R2.4, R6.3_
    - _Test: `tests/contract/test_fcit_table.py::test_the_record_and_the_form`, `::test_a_club_that_doesnt_add_up_is_named`,
      `::test_a_page_whose_columns_changed_is_unreadable`; `tests/contract/test_real_pages.py::test_every_club_on_the_table`;
      `tests/unit/cards/test_table.py::test_tables_stored_before_still_read`, `::test_the_record_adds_up`, `::test_the_form_fits_the_record`;
      `tests/integration/cards/test_table_read.py::test_the_collector_reads_the_table`, `::test_switched_off_the_table_is_claudes`,
      `::test_the_table_is_due_daily`,
      `::test_claude_still_submits_it`; `tests/unit/checks/test_task_check.py::test_default_is_the_current_spec`_

- [x] 2. The match in numbers
  - Branch: `feat/cd-2-numbers` · Depends on: 1 · ADRs: none
  - [x] 2.1 The chances from the de-margined odds and their spread, the expected goals and clean sheets, three goals or more and both teams to
    score, team form without odds; the season so far, shown and never used. `domains/cards.py` joins the mutation run.
    - _Requirements: R2.1 to R2.4_
    - _Test: **AT-2** `tests/acceptance/cards/test_numbers.py::test_at2_the_numbers_by_hand`, `::test_at2_several_odds_pages`,
      `::test_at2_without_odds`; **AT-3** `::test_at3_the_season_so_far`; **P1** `tests/property/cards/test_numbers.py::test_p1_chances_add_up`,
      **P3** `::test_p3_the_record_moves_no_number`_

- [x] 3. The lineups
  - Branch: `feat/cd-3-lineups` · Depends on: 2 · ADRs: none
  - [x] 3.1 Each side's likely eleven with its confidence, the disputed places with their contenders and the outlets that differ, who's out,
    and the official lineups once stored.
    - _Requirements: R3.1 to R3.4_
    - _Test: **AT-4** `tests/acceptance/cards/test_lineups.py::test_at4_a_likely_eleven`, `::test_at4_a_ballottaggio_is_one_place`,
      `::test_at4_an_outlet_that_disagrees`, `::test_at4_the_unavailable`, `::test_at4_the_official_lineups`; **P2**
      `tests/property/cards/test_lineups.py::test_p2_eleven_and_one_keeper`, `::test_p2_the_official_eleven`_

- [x] 4. What it means for the players
  - Branch: `feat/cd-4-players` · Depends on: 3 · ADRs: none
  - [x] 4.1 Each player's chance of scoring and share, the likeliest scorers, the keepers, the takers, the rotation risks and the user's
    players first, under the stored rules or Classic's.
    - _Requirements: R4.1 to R4.6_
    - _Test: **AT-5** `tests/acceptance/cards/test_players.py::test_at5_a_scorer_by_hand`, `::test_at5_the_likeliest_scorers`,
      `::test_at5_a_keeper`, `::test_at5_the_takers`, `::test_at5_a_rotation_risk`, `::test_at5_rotation_at_its_edges`,
      `::test_at5_your_players_first`; **AT-6**
      `::test_at6_classic_without_rules`, `::test_at6_a_leagues_own_rules`_

- [x] 5. The card tool
  - Branch: `feat/cd-5-card` · Depends on: 4 · ADRs: none
  - [x] 5.1 `match_card`: the clubs by any spelling, the club with no match, a match whose round is past its deadline, the facts gathered as other answers
    gather them, what's missing, and the log for calibration.
    - _Requirements: R1.1 to R1.5, R6.1_
    - _Test: **AT-1** `tests/acceptance/cards/test_card.py::test_at1_by_two_clubs_and_by_one`, `::test_at1_a_club_with_no_match`,
      `::test_at1_kicked_off`; **AT-8** `::test_at8_the_same_numbers_as_an_outlook`; **AT-9** `::test_at9_logged_and_counted`;
      **P4** `tests/property/cards/test_card.py::test_p4_as_player_outlook`, **P5** `::test_p5_a_replay_logs_nothing`;
      `tests/integration/cards/test_card_tool.py::test_statuses`, `::test_missing_lineups_still_give_a_card`_

- [ ] 6. The round overview
  - Branch: `feat/cd-6-overview` · Depends on: 5 · ADRs: none
  - [ ] 6.1 `round_overview`: one line per fixture in kickoff order, team-level only, enough for a question across fixtures.
    - _Requirements: R5.1, R5.2_
    - _Test: **AT-7** `tests/acceptance/cards/test_overview.py::test_at7_one_line_per_fixture`, `::test_at7_the_safest_keepers`; **P5**
      `tests/property/cards/test_overview.py::test_p5_in_kickoff_order`_

- [ ] 7. The docs and the limits
  - Branch: `feat/cd-7-docs` · Depends on: 6 · ADRs: none
  - [ ] 7.1 Format 5 as built and the overview's example; each tool's description with its rendering rules; the prompt's line within its
    budget; the player guide; both tools within 3 seconds and 15 KB.
    - _Requirements: R6.2, R6.4, R6.5_
    - _Test: **AT-10** `tests/acceptance/cards/test_answer.py::test_at10_in_budget`, `::test_at10_from_no_new_page`;
      `tests/unit/test_repo_hygiene.py::test_agent_prompt_covers_the_cards`_

- [ ] 8. A real check and this slice's sign-off
  - Branch: `docs/cd-8-gate` · Depends on: 7 · ADRs: none
  - [ ] 8.1 Real data from Claude Code, with a temporary decision log: a real round's cards and overview, with what each used, its time and its
    size. Results stay out of the repository.
    - _Requirements: R6.2_
    - _Test: what each card used, and its time and size, in the report without players' figures_
  - [ ] 8.2 **Owner:** read the next round's cards in a Claude app before its deadline (round 12's, if the slice is built by then), and
    check them against the round page.
    - _Requirements: AT-11 (R1 to R5)_
    - _Test: recorded in the report_
  - [ ] 8.3 A mutation run on the core modules, with survivors read; the slice report: tests, coverage, quality, cost, open risks and the
    acceptance tests.
    - _Requirements: R6.2; phase gate (`quality.md`)_
    - _Test: the report exists with every section; `make check` green on `main`_
  - [ ] 8.4 **Owner:** sign off this slice.
    - _Requirements: Phase gate (`quality.md`)_
    - _Test: sign-off recorded in the report_
