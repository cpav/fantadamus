# Fantadamus

A Fantacalcio advisor (Serie A fantasy football, Classic rules). It answers "who do I field?": "X or Y?"
with a verdict and its reasons, one player's outlook, the best eleven and bench under a league's own rules,
and the formation call. It also puts a match on one screen and the round at a glance, and after a round reviews
the lineup you fielded. You ask in your own Claude app; Fantadamus's MCP tools hold the data and do the arithmetic.
On a Mac, a schedule keeps the facts fresh and a notification says when the news changes your lineup.

- **For players:** what it answers, how it decides and what it costs, in
  [`docs/presentation/product.html`](docs/presentation/product.html).
- **How it's built:** the architecture tour, in
  [`docs/presentation/architecture.html`](docs/presentation/architecture.html).

Both pages open directly in a browser; [`docs/presentation/`](docs/presentation/README.md) also links
published copies.

## How it works

```text
your Claude app ──ask──▶ best_lineup, compare_players… ──▶ collector reads its pages ──▶ checks ──▶ bronze ─▶ silver ─▶ gold ─▶ engine
       │                      │                                                                         ▲
       │                      └─▶ answer, or a plan for what's still missing                            │
       └─read_page (Fantadamus fetches the listed page) ──▶ submit tools ───────────────────────────────┘
```

- **Fantadamus collects, Claude fills the gaps, the tools decide.** Fantadamus reads its pages itself, politely,
  when an answer needs them and on a schedule: Fantacalcio-Online's round page (fixtures, four outlets' chances of
  starting, official lineups and odds) and its round ratings; Fantacalcio.it's statistics page (every player's
  season figures), penalty takers, table, and injured and suspended players; and Wikipedia's pages of the European
  cups and the Coppa Italia. For the rest, Claude reads the listed pages through `read_page`, which fetches them,
  and submits what they say. Fantadamus checks every fact, stores it, and computes every probability in tested
  Python ([ADR-0006](docs/adr/0006-mvp-fantadamus-collects-round-facts.md),
  [ADR-0007](docs/adr/0007-mvp-reads-other-competitions-injuries-and-ratings.md)).
- **The method** is the owner's own: [`docs/method.md`](docs/method.md). Bonuses are priced from the betting
  odds, small samples are shrunk, and source disagreement is shown rather than averaged. After each round it scores
  its own forecasts, and its starting values are recalibrated from them ([`docs/calibration-log.md`](docs/calibration-log.md)).
- **Storage** is a small medallion lakehouse: Parquet files read through DuckDB, bronze append-only, silver in a
  file per month that each store adds to, every table under a versioned contract. Gold is worked out when an answer
  asks. The same layout moves to S3 when the server goes online.

## Status

Every slice of Phase 2 is built and signed off, each with its report in [`docs/reports/`](docs/reports/). What it
answers today:

- **"X or Y?"** for any two players of the same role, and **one player's outlook** (`mvp-collect`, `mvp-roles`):
  a forecast, with how sure each number is, how it moved and where it came from;
- **the full lineup** (`mvp-lineup`, `mvp-rules`): the eleven, the bench in order and the formation for a user's
  squad under their league's own rules, modifiers and captain included, simulated to give the expected score and the
  chance of each goal threshold;
- **a match card** for each fixture and **the round at a glance** (`mvp-cards`), with rest days, European fixtures,
  injuries and bans as context (`mvp-sources`);
- **the review of a fielded lineup** after a round: what each choice against the advice was expected to cost, and what
  it did (`mvp-review`).

Behind them: the starting values recalibrated on the rounds scored so far (`mvp-recalibrate`), a notification on the Mac
when the news changes a lineup (`mvp-alerts`), and storing and reading that keep their speed all season (`mvp-store`).
The answers' shapes are in [docs/answer-formats.md](docs/answer-formats.md). A second player installs it from the
[setup guide](docs/player-setup.md).

**Now:** the Phase 2 report. Round 12 (21 to 23 November 2026) ran end to end with the schedule installed, and the
five small fixes it found are `mvp-fixes`, signed off on 2026-11-24 ([report](docs/reports/slice-mvp-fixes.md)). Then
Phase 3. The review before going online ran on 2026-11-16 ([report](docs/reports/review-before-phase-3.md)); its first
finding became `mvp-store`, and two of its decisions are still the owner's.

| Phase | Builds | Status |
|---|---|---|
| 0 Foundation | Repository, gates, CI, hooks, storage, walking skeleton (retired 2026-10-31) | Done, signed off 2026-10-26 ([report](docs/reports/phase-0-report.md)) |
| 1 `mvp-x-or-y` | "X or Y?" for two forwards in the owner's Claude Desktop: the facts, the method, `compare_players` | Done, signed off 2026-10-26 ([report](docs/reports/phase-1-report.md)) |
| 2 Slices | `mvp-collect` and `mvp-roles` (2026-11-04), `mvp-lineup` (11-07), `mvp-rules` (11-09), `mvp-review` and `mvp-cards` (11-11), `mvp-recalibrate` (11-12), `mvp-sources` (11-15), `mvp-alerts` and `mvp-store` (11-18), `mvp-fixes` (11-24), in the order in [`product.md`](.kiro/steering/product.md#delivery-order) | Every slice signed off on the date shown; the phase report follows round 12 |
| 3 Online | The MCP server online, so that a player installs nothing, with the AWS work moved from Phase 0 | Next |

For now each player installs and runs Fantadamus on their own Mac; going online in Phase 3 removes the install.

## Run it locally

You need macOS or Linux, `git`, `make` and [uv](https://docs.astral.sh/uv/).

```bash
make setup      # the locked Python environment, the pinned tools and the git hooks
make check      # every gate, as CI runs it: one PASS or FAIL line per check
make test-fast  # format, lint, unit and property tests with the fast profile
```

`uv run fantadamus serve` starts the MCP server on stdio: `best_lineup`, `compare_players`, `player_outlook`,
`match_card`, `round_overview`, `review_round`, `set_squad`, `set_league_rules`, `collect`, `read_page` and the submit
tools. `uv run fantadamus collect` reads the round page and Fantacalcio.it's statistics, penalty-takers and table pages
now (`--fact` takes any of the facts the collector reads and reads only its page, as the `collect` tool does in
Claude; `--round` another round's page); `--due` reads only what is past its cadence, as the schedule does, and tries
a page that got no answer again at the next run; `--report` shows the last run. `uv run fantadamus calibrate --round N`
prints a finished round's report on the forecasts, and keeps its calibration set beside it, player by player, for a
recalibration; `--again` rebuilds both. `uv run fantadamus recalibrate` proposes new starting values from the
stored sets, each checked where it wasn't fitted, and changes nothing until the owner approves one.
`uv run fantadamus alerts` prints the alerts sent and the calls kept to compare with; `--test` sends a sample
notification. `uv run fantadamus rebuild` writes every silver table again from its bronze records, or one with
`--table`, and reads no page: a store does it by itself when it finds a table out of step.

## Use it in Claude Desktop

1. Run `make setup` once, as above.
2. Find uv's full path with `which uv`: Claude Desktop doesn't read your shell's `PATH`.
3. Add the server to `~/Library/Application Support/Claude/claude_desktop_config.json`, with your two paths,
   then restart Claude Desktop:

   ```json
   {
     "mcpServers": {
       "fantadamus": {
         "command": "/Users/you/.local/bin/uv",
         "args": ["--directory", "/path/to/fantadamus", "run", "--frozen", "fantadamus", "serve", "--user", "owner"]
       }
     }
   }
   ```

4. Create a Claude **Project** called Fantadamus and paste the agent prompt (everything below the `---` line in
   [`docs/agent-prompt.md`](docs/agent-prompt.md)) as its instructions, so Claude uses the tools unasked. Below it, you
   can paste your filled-in league profile ([`docs/league-profile-template.md`](docs/league-profile-template.md)): your
   league's rules, your squad and how you like to play. Keep that copy out of this repository.
5. In that project, ask "Who do I field this round?". The first time, Claude saves your rules and squad from the profile,
   or asks for them, with the Fantacalcio Classic values offered. When facts are missing or stale, Claude reads the
   approved pages, submits what they say, and asks again.
6. To keep the facts fresh between questions and get alerts, install the schedule:
   [step 8 of the setup guide](docs/player-setup.md#8-keep-the-forecast-fresh-optional), with your folder in place of
   `~/fantadamus`.

After a `git pull`, quit Claude Desktop (⌘Q) and open it again: its Fantadamus server keeps running the code it
started with.

A second player installs it from [`docs/player-setup.md`](docs/player-setup.md), step by step.

Your league rules, your squads, the lake and the decision log stay in git-ignored `data/local/`.

## How this project works

The project is spec-driven. The specs use Kiro's file layout as plain Markdown; Claude Code is the coding
agent:

- [`.kiro/steering/`](.kiro/steering/): what the product is, the technology, the repository structure
  and the quality gates;
- [`.kiro/specs/`](.kiro/specs/): requirements, design and tasks for each spec, built in order;
- [`docs/adr/`](docs/adr/): one record per research decision, with its sources;
- [`docs/method.md`](docs/method.md): the decision method; [`docs/source-registry.md`](docs/source-registry.md):
  where the data comes from and on what terms.

## Repository rules

- This repository is public. Third-party data, recorded source pages and personal data about league
  members are never committed; they live in git-ignored `data/private/`.
- Private configuration (creator identities, AWS account details, API keys) lives outside the repository,
  at `FANTADAMUS_PRIVATE_CONFIG` (default `~/.config/fantadamus/private.toml`).

## Licence

**No licence is granted. All rights reserved.** The code is public so that its work can be seen; it may
not be copied, modified or distributed without written permission from the owner.
