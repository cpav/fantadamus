# Implementation Plan: `mvp-x-or-y` (Phase 1)

Status: **Approved by the owner, 2026-10-26** · Date: 2026-10-26 · From the approved [requirements](requirements.md)
and [design](design.md)

## How to read and run these tasks

- **One top-level task = one branch = one pull request**, named `<type>/xy-<n>-<slug>`. Sub-tasks are the
  steps inside it, each with its own test, written first and seen failing (red → green).
- Before a task, `make task-check TASK=<n>` (this spec is the default) checks that its dependencies are
  ticked, that every step names its requirements and test, and that its ADRs are Accepted. If it fails, the
  agent stops and asks the owner.
- A ticked box (`- [x]`) marks a task or step as done. The agent ticks it on the task's own branch, so it
  reaches `main` only with the owner's merge.
- The property tests P1–P8 in the design are **required**. No task is optional.
- Each task ends with the task report (`quality.md`); the owner approves the pull request, the agent
  squash-merges it.
- **Owner** marks a step only the owner can do.
- **Tests for this spec** live in an `xy/` folder in each test layer (`tests/unit/xy/`, `tests/property/xy/`,
  `tests/integration/xy/`, `tests/acceptance/xy/`), so its AT numbers don't clash with Spec 0's. Contract
  tests go in `tests/contract/test_xy_contracts.py`. Fixtures are synthetic: invented players at invented
  clubs (the repository is public).
- **The order:** 1 → 2 → 3 and 4; 5 and 6 can come at any point; 7 needs 3 to 6; then 8.

## Tasks

- [x] 1. Clubs, contracts and the reading list
  - Branch: `feat/xy-1-contracts` · Depends on: none · ADRs: ADR-0005
  - [x] 1.1 `config/clubs.toml`: the 20 Serie A clubs of 2026/27, each with its canonical key and the spellings
    outlets use, and a lookup that rejects an unknown club with the list of known ones. The club list is read
    from Wikipedia's season page (on the reading list), and the owner checks it in the task report
    - _Requirements: R2.1, R6.2_
    - _Test: `tests/unit/xy/test_clubs.py::test_twenty_clubs_unique_aliases`,
      `::test_unknown_club_lists_known_ones`_
  - [x] 1.2 The seven fact contracts in `contracts/xy/` (C2), each with its quality rule as a model validator:
    `FixturesPayload`, `ProbableLineupPayload`, `OfficialLineupPayload`, `MatchOddsPayload`,
    `PlayerSeasonPayload`, `TeamSeasonPayload`, `PenaltyTakersPayload`; their schema snapshots and changelog
    entries
    - _Requirements: R1.1, R2.1, R3.1, R4.1, R5.1, R6.1, R6.2, R6.3, R8.1, R8.2, R8.3, R8.4_
    - _Test: `tests/contract/test_xy_contracts.py::test_synthetic_pages_parse`, `::test_eleven_starters`,
      `::test_ballottaggio_shares`, `::test_odds_margin`, `::test_impossible_season_figures`_
  - [x] 1.3 `config/reading_list.toml` (C11): for each fact, the page or URL template, the cross-check pages,
    a search hint where no URL can be built, and the submit tool
    - _Requirements: R11.1_
    - _Test: `tests/unit/test_sources_config.py::test_reading_list_pages_are_allowed`,
      `::test_reading_list_covers_each_submit_tool`_

- [x] 2. Fixtures, season figures and names
  - Branch: `feat/xy-2-fixtures-season` · Depends on: 1 · ADRs: ADR-0005
  - [x] 2.1 `submit_fixtures` and the `fixtures` domain: bronze with the envelope, silver `fixtures` with
    history, the gold view `fixture(club, round)` and the round's deadline (its first kickoff)
    - _Requirements: R2.1, R2.2, R7.1, R7.2_
    - _Test: `tests/integration/xy/test_fixtures.py::test_submit_fixtures_bronze_to_silver`,
      `::test_deadline_is_first_kickoff`, `::test_as_of_ignores_later_fixtures`,
      `::test_capture_after_receipt_counts_as_receipt` (added in task 8.1, after the owner's first round)_
  - [x] 2.2 `submit_player_season`, `submit_team_season` and `submit_penalty_takers`, and the `season` domain:
    silver `player_seasons` (a player's identity is his latest row), `team_seasons`, `penalty_takers`; the gold views
    `player_form(player, as_of)` and `penalty_order(club, as_of)`
    - _Requirements: R1.1, R6.1, R6.2, R6.3, R7.1, R7.2_
    - _Test: `tests/integration/xy/test_season.py::test_profile_creates_player_and_season`,
      `::test_team_table_and_penalty_takers`, `::test_resubmission_keeps_history`_
  - [x] 2.3 Name resolution (C4): case, accents and spacing ignored; a unique surname; "Lautaro M." style;
    candidates instead of a guess
    - _Requirements: R1.2, R1.3_
    - _Test: `tests/unit/xy/test_resolve.py::test_full_name_and_unique_surname`, `::test_surname_and_initial`,
      `::test_ambiguous_or_unknown_returns_candidates`;
      **P5** `tests/property/xy/test_resolve.py::test_p5_resolution_ignores_learning_order`_

- [x] 3. Probable and official lineups
  - Branch: `feat/xy-3-lineups` · Depends on: 2 · ADRs: ADR-0005
  - [x] 3.1 `submit_probable_lineups` and `submit_official_lineup`, and the `availability` domain: silver
    `lineup_views` and `official_lineups`; names that don't resolve are kept and resolved again when a
    profile arrives
    - _Requirements: R3.1, R4.1, R7.1, R7.2_
    - _Test: `tests/integration/xy/test_lineups.py::test_outlets_kept_side_by_side`,
      `::test_unresolved_name_resolves_when_profile_arrives`_
  - [x] 3.2 Consensus (C5) and the gold view `availability(player, match, as_of)`: each outlet's view, the
    mean over fresh outlets, the spread and the disputed flag, p_cameo, the official lineup's override
    - _Requirements: R3.2, R3.3, R3.4, R4.2_
    - _Test: `tests/unit/xy/test_consensus.py::test_outlet_views`, `::test_unmentioned_player_counts_bench`,
      `::test_unavailable_has_no_cameo`; **P1** `tests/property/xy/test_consensus.py::test_p1_probabilities_bounded`,
      **P2** `::test_p2_official_lineup_wins`, **P3** `::test_p3_outlet_order_ignored`;
      **AT-5** `tests/acceptance/xy/test_lineups.py::test_at5_official_lineup_overrides`,
      **AT-6** `::test_at6_two_outlets_disputed`_

- [x] 4. Match odds and team xG
  - Branch: `feat/xy-4-odds` · Depends on: 2 · ADRs: ADR-0005
  - [x] 4.1 `submit_match_odds` and the `odds` domain: silver `odds` with each page's de-margined
    probabilities
    - _Requirements: R5.1, R7.1, R7.2_
    - _Test: `tests/integration/xy/test_odds.py::test_submit_odds_de_margined`,
      `::test_pages_kept_side_by_side`_
  - [x] 4.2 The fit (`engine/odds.py`, C7): Poisson with the Dixon–Coles correction, grid then refinement;
    the fallback from regressed team form; the gold view `team_xg(match, as_of)`, with the fallback flagged
    - _Requirements: R5.2, R5.3_
    - _Test: `tests/unit/xy/test_odds_fit.py::test_known_market`, `::test_dixon_coles_low_scores`,
      `::test_regressed_form_fallback`;
      **P6** `tests/property/xy/test_odds_fit.py::test_p6_fit_reproduces_market`_

- [x] 5. The forward model
  - Branch: `feat/xy-5-forward-model` · Depends on: none · ADRs: none
  - [x] 5.1 `engine/constants.py` (every _(start)_ value with its method section) and the formulas in
    `engine/forwards.py` (C8): expected vote, shares, E[goals] with the penalty term, P(yellow), E_start with
    signed rule values, E_cameo
    - _Requirements: R9.1, R9.2, R9.3, R9.4, R9.5, R9.6, R9.7, R12.5_
    - _Test: `tests/unit/xy/test_forwards.py::test_formulas_by_hand`, `::test_signed_yellow_lowers_score`;
      **AT-2** `tests/acceptance/xy/test_method.py::test_at2_goal_chances`_
  - [x] 5.2 The key, the comparison, the margin label, the flip points and the verdict without bench cover
    - _Requirements: R9.8, R10.1, R10.2, R10.4, R10.6_
    - _Test: `tests/unit/xy/test_forwards.py::test_margin_labels`, `::test_flip_points`;
      **AT-1** `tests/acceptance/xy/test_method.py::test_at1_tie_and_rejected_ranking`,
      **AT-3** `::test_at3_bench_cover_changes_verdict`;
      **P7** `tests/property/xy/test_forwards.py::test_p7_higher_e_start_never_ranks_lower`_

- [x] 6. League rules
  - Branch: `feat/xy-6-league-rules` · Depends on: none · ADRs: ADR-0005
  - [x] 6.1 The `LeagueRules` contract and the store (`league/rules.py`, C9): one file per user under the
    git-ignored `data/local/league/`, each change keeping the previous version
    - _Requirements: R12.1, R12.2, R12.4_
    - _Test: `tests/contract/test_xy_contracts.py::test_league_rules_ranges`,
      `tests/unit/xy/test_league_rules.py::test_change_keeps_previous_version`_
  - [x] 6.2 `set_league_rules` and the setup step: every field with its Classic starting value and one line on
    what it means
    - _Requirements: R12.2, R12.3, R12.5_
    - _Test: `tests/integration/xy/test_league_rules.py::test_set_then_change_rules`,
      `::test_out_of_range_rejected_with_reason`;
      `tests/unit/xy/test_league_rules.py::test_setup_step_offers_classic_values`_

- [x] 7. `compare_players` and the server
  - Branch: `feat/xy-7-compare` · Depends on: 3, 4, 5, 6 · ADRs: ADR-0005
  - [x] 7.1 The freshness targets (R7.3) and the as-of reads across every gold view
    - _Requirements: R7.3, R7.4_
    - _Test: `tests/unit/xy/test_freshness.py::test_targets_tighten_near_the_match`;
      **P4** `tests/property/xy/test_as_of.py::test_p4_as_of_never_sees_later_facts`_
  - [x] 7.2 `compare_players` (C10): setup step, names, round and fixtures, the refresh plan in its order,
    then the answer with its breakdown, the rules it used, times in `Europe/Rome`, the flagged fallbacks and
    what to check before the deadline
    - _Requirements: R1.3, R1.4, R2.2, R2.3, R10.1, R10.2, R10.3, R10.4, R10.5, R10.6, R11.1, R11.2, R11.3,
      R12.3, R12.4_
    - _Test: `tests/integration/xy/test_compare.py::test_refresh_plan_order`, `::test_forwards_only`,
      `::test_no_fixture_means_not_playing`, `::test_first_match_to_check`;
      **AT-4** `tests/acceptance/xy/test_compare.py::test_at4_scripted_collection`,
      **AT-8** `::test_at8_earlier_as_of_ignores_later_facts`, **AT-10** `::test_at10_league_rules`_
  - [x] 7.3 The decision log (C12): one appended line per answer
    - _Requirements: R14.1, R14.2_
    - _Test: **AT-9** `tests/acceptance/xy/test_compare.py::test_at9_one_log_entry_per_answer`;
      **P8** `tests/property/xy/test_decision_log.py::test_p8_log_only_grows`_
  - [x] 7.4 The server (C13): the nine tools, the skeleton's tools no longer served, `docs/agent-prompt.md` as
    the instructions, `--user`, tool descriptions naming their pages; the README's Claude Desktop setup
    - _Requirements: R13.1, R13.2, R13.3, R7.1, R8.1, R8.2, R8.3_
    - _Test: `tests/integration/xy/test_server.py::test_served_tools`, `::test_instructions_are_agent_prompt`;
      **AT-7** `tests/acceptance/xy/test_compare.py::test_at7_bad_submissions_rejected`;
      `tests/unit/test_repo_hygiene.py::test_readme_claude_desktop_setup`_

- [x] 8. The owner's real round and the Phase 1 gate
  - Branch: `docs/xy-8-phase-report` · Depends on: 7 · ADRs: ADR-0005
  - [x] 8.1 **Owner:** add the server to Claude Desktop, set your league rules, and ask a real "X or Y?" for a
    real round
    - _Requirements: AT-11; R12.3, R13.1, R13.2, R13.3_
    - _Test: the answer's facts all come from the reading list, recorded in the phase report (no page text,
      no creator names)_
  - [x] 8.2 Short Phase 1 report in `docs/reports/`: tests, coverage, acceptance tests, the first decision-log
    entries, cost ($0), open risks
    - _Requirements: R14.1, Phase 1 exit gate (`quality.md`)_
    - _Test: the report exists with every section; `make check` green on `main`_
  - [x] 8.3 **Owner:** sign off Phase 1 → the next slice may start
    - _Requirements: Phase gate (`quality.md`)_
    - _Test: sign-off recorded in the phase report_

- [x] 9. Fixes from the first real round
  - Branch: `feat/xy-9-round-fixes` · Depends on: 7 · ADRs: ADR-0005
  - [x] 9.1 A player who can't play isn't put first on the bench
    - _Requirements: R10.7_
    - _Test: `tests/unit/xy/test_forwards.py::test_verdict_knows_who_can_play`,
      `tests/integration/xy/test_compare.py::test_player_who_cannot_play_is_not_benched`_
  - [x] 9.2 The agent prompt names only the tools that exist, calls `compare_players` for every "X or Y?" and
    tells the round's deadline from each player's kickoff; the README and `docs/player-setup.md` set up a
    Claude Project with it
    - _Requirements: R13.2, R13.4_
    - _Test: `tests/integration/xy/test_server.py::test_prompt_names_only_served_tools`,
      `tests/unit/test_repo_hygiene.py::test_player_guide_setup`_

- [x] 10. Reliable sources, from the first test round
  - Branch: `fix/xy-10-reliable-sources` · Depends on: 9 · ADRs: ADR-0005
  - [x] 10.1 Every fact in the reading list has fallbacks, best first, with a search hint; Fantacalcio.it's
    calendar and table lead for fixtures and the table; the agent prompt and the plan say to work down the
    list; `submit_fixtures` asks for Italian kickoffs with their offset
    - _Requirements: R11.1, R11.4_
    - _Test: `tests/unit/test_sources_config.py::test_reading_list_has_fallbacks`,
      `tests/integration/xy/test_server.py::test_prompt_explains_fallbacks`_

- [x] 11. Clear tool schemas, from the first test round
  - Branch: `fix/xy-11-clear-schemas` · Depends on: 10 · ADRs: ADR-0005
  - [x] 11.1 The server publishes each tool's schema with its references inlined, and the nested submit tools'
    descriptions show their payload shape
    - _Requirements: R13.1, R7.1_
    - _Test: `tests/integration/xy/test_server.py::test_schemas_spell_out_every_field`_

- [x] 12. 1X2-only odds, from the first test round
  - Branch: `fix/xy-12-odds-1x2` · Depends on: 11 · ADRs: ADR-0005
  - [x] 12.1 Over/under 2.5 becomes optional in `MatchOddsPayload` (a minor version); silver keeps it empty;
    the fit uses whichever markets are present
    - _Requirements: R5.1, R5.2, R8.3_
    - _Test: `tests/contract/test_xy_contracts.py::test_odds_without_totals`,
      `tests/integration/xy/test_odds.py::test_one_x_two_only_odds_are_used`;
      **P6** `tests/property/xy/test_odds_fit.py::test_p6_fit_reproduces_market`_
