# Fantadamus

A Fantacalcio advisor (Serie A fantasy football, Classic rules). It answers "who do I field?": "X or Y?"
with a verdict and its reasons, one player's outlook, the best eleven and bench under a league's own rules,
and the formation call. You ask in your own Claude app; Fantadamus's MCP tools hold the data and do the arithmetic.

- **For players:** what it answers, how it decides and what it costs, in
  [`docs/presentation/product.html`](docs/presentation/product.html).
- **How it's built:** the architecture tour, in
  [`docs/presentation/architecture.html`](docs/presentation/architecture.html).

Both pages open directly in a browser; [`docs/presentation/`](docs/presentation/README.md) also links
published copies.

## How it works

```text
your Claude app ──ask──▶ best_lineup, compare_players… ──▶ collector reads its two pages ──▶ checks ──▶ bronze ─▶ silver ─▶ gold ─▶ engine
       │                      │                                                                         ▲
       │                      └─▶ answer, or a plan for what's still missing                            │
       └─read_page (Fantadamus fetches the listed page) ──▶ submit tools ───────────────────────────────┘
```

- **Fantadamus collects, Claude fills the gaps, the tools decide.** Fantadamus reads two pages itself,
  politely: Fantacalcio-Online's round page (fixtures, four outlets' chances of starting, official lineups and
  odds) and Fantacalcio.it's statistics page (every player's season figures). For the rest, Claude reads the listed pages through `read_page`, which fetches them, and submits what they say.
  Fantadamus checks every fact, stores it, and computes every probability in tested Python
  ([ADR-0006](docs/adr/0006-mvp-fantadamus-collects-round-facts.md)).
- **The method** is the owner's own: [`docs/method.md`](docs/method.md). Bonuses are priced from the betting
  odds, small samples are shrunk, and source disagreement is shown rather than averaged.
- **Storage** is a small medallion lakehouse: Parquet files read through DuckDB, bronze append-only, every
  table under a versioned contract. The same layout moves to S3 when the server goes online.

## Status

Phase 2 is under way. Its first two slices are signed off ([report](docs/reports/slices-mvp-collect-and-roles.md)).
`mvp-collect`: Fantadamus reads the round's lineups and odds
itself, compares its sources, and answers as a forecast, with how sure each number is, how it moved and where it
came from. `mvp-roles`: "X or Y?" for any two players of the same role, and one player's outlook. A second player can install
it from the [setup guide](docs/player-setup.md). `mvp-lineup`, built and waiting for a real round before its sign-off:
the eleven, the bench in order and the formation for a user's squad under their league's own rules, simulated to give the
expected score and the chance of each goal threshold; a finished round scores its own forecasts. Phases 0 and 1 are signed off
([reports](docs/reports/phase-1-report.md)). The answers' shapes, from "X or Y?" to the full lineup, are in
[docs/answer-formats.md](docs/answer-formats.md).

Re-planned on 2026-10-26: the work now goes in thin slices, each taking one question from data to answer.

| Phase | Builds | Status |
|---|---|---|
| 0 Foundation | Repository, gates, CI, hooks, storage, walking skeleton (retired 2026-10-31) | Done, signed off 2026-10-26 |
| 1 `mvp-x-or-y` | "X or Y?" for two forwards in the owner's Claude Desktop: the facts, the method, `compare_players` | Done, signed off 2026-10-26 ([report](docs/reports/phase-1-report.md)) |
| 2 Slices | `mvp-collect` and `mvp-roles` (every role), signed off 2026-11-04; `mvp-lineup` (the full lineup, the bench, the formation and calibration), built; then every other feature discussed, in the order in [`product.md`](.kiro/steering/product.md#delivery-order) | In progress: `mvp-lineup`'s real round |
| 3 Online | The MCP server online, so that a player installs nothing, with the AWS work moved from Phase 0 | After Phase 2 |

For now each player installs and runs Fantadamus on their own Mac; going online in Phase 3 removes the install.

## Run it locally

You need macOS or Linux, `git`, `make` and [uv](https://docs.astral.sh/uv/).

```bash
make setup      # the locked Python environment, the pinned tools and the git hooks
make check      # every gate, as CI runs it: one PASS or FAIL line per check
make test-fast  # format, lint, unit and property tests with the fast profile
```

`uv run fantadamus serve` starts the MCP server on stdio: `best_lineup`, `compare_players`, `player_outlook`,
`set_squad`, `set_league_rules`, `collect`, `read_page` and the submit tools. `uv run fantadamus collect` reads the round page and Fantacalcio.it's
statistics page now (`--fact` picks one fact's page); `--report` shows the last run. `uv run fantadamus calibrate --round N`
prints a finished round's report on the forecasts; `--again` scores it again.

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
