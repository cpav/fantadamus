# Fantadamus

A Fantacalcio advisor (Serie A fantasy football, Classic rules). It answers "who do I field?": "X or Y?"
with a verdict and its reasons, the best eleven and bench under a league's own rules, and the formation
call. You ask in your own Claude app; Fantadamus's MCP tools hold the data and do the arithmetic.

- **For players:** what it answers, how it decides and what it costs, in
  [`docs/presentation/product.html`](docs/presentation/product.html).
- **How it's built:** the architecture tour, in
  [`docs/presentation/architecture.html`](docs/presentation/architecture.html).

Both pages open directly in a browser; [`docs/presentation/`](docs/presentation/README.md) also links
published copies.

## How it works

```text
your Claude app ──ask──▶ read tools ──▶ answer, or a refresh plan (what's stale, where to read it)
       │                     ▲
       └─reads approved sites, then──▶ submit tools ──▶ checks ──▶ bronze ─▶ silver ─▶ gold ─▶ engine
```

- **Claude collects, the tools decide.** Each player's Claude reads only the approved sites and submits what
  they say, with the link and the time. Fantadamus checks every fact, stores it, and computes every
  probability in tested Python ([ADR-0005](docs/adr/0005-mvp-claude-collects-tools-decide.md)).
- **The method** is the owner's own: [`docs/method.md`](docs/method.md). Bonuses are priced from the betting
  odds, small samples are shrunk, and source disagreement is shown rather than averaged.
- **Storage** is a small medallion lakehouse: Parquet files read through DuckDB, bronze append-only, every
  table under a versioned contract. The same layout moves to S3 when the server goes online.

## Status

Not ready for other players yet. Phase 0, the foundation, is complete and signed off
([report](docs/reports/phase-0-report.md)). Phase 1's "X or Y?" for two forwards runs locally in Claude
Desktop: the submit tools, the checks and storage, the forward model and `compare_players`. The owner's first
real round was answered on 2026-10-26 ([Phase 1 report](docs/reports/phase-1-report.md)).

Re-planned on 2026-10-26: the work now goes in thin slices, each taking one question from data to answer.

| Phase | Builds | Status |
|---|---|---|
| 0 Foundation | Repository, gates, CI, hooks, storage, walking skeleton | Done, signed off 2026-10-26 |
| 1 `mvp-x-or-y` | "X or Y?" for two forwards in the owner's Claude Desktop: the facts, the method, `compare_players` | First real round answered 2026-10-26 ([report](docs/reports/phase-1-report.md)); awaiting sign-off |
| 2 More slices | Keepers and defenders; the full lineup with league rules and the bench; the formation | Method written |
| 3 Online | The MCP server online for a second player, with the AWS work moved from Phase 0 | Prompt written |

A setup guide for players comes with Phase 3.

## Run it locally

You need macOS or Linux, `git`, `make` and [uv](https://docs.astral.sh/uv/).

```bash
make setup      # the locked Python environment, the pinned tools and the git hooks
make check      # every gate, as CI runs it: one PASS or FAIL line per check
make test-fast  # format, lint, unit and property tests with the fast profile
make skeleton   # the walking skeleton end to end, compared with its golden file
```

`uv run fantadamus serve` starts the MCP server on stdio: `compare_players`, `set_league_rules` and the seven
submit tools.

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
   [`docs/agent-prompt.md`](docs/agent-prompt.md)) as its instructions, so Claude uses the tools unasked.
5. In that project, ask "X or Y?" for two forwards. The first time, Claude asks for your league's bonuses and
   maluses, with the Fantacalcio Classic values offered. When facts are missing or stale, Claude reads the
   approved pages, submits what they say, and asks again.

A second player installs it from [`docs/player-setup.md`](docs/player-setup.md), step by step.

Your league rules, the lake and the decision log stay in git-ignored `data/local/`.

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
