# Fantadamus

A Fantacalcio advisor (Serie A fantasy football, Classic rules). It answers "who do I play?": the best
eleven and bench for a league's own rules, "X or Y?" with a short breakdown, and the best formation.
The numbers come from a deterministic decision engine over a small data lakehouse; the chat happens in
the user's own Claude app through MCP tools.

## Status

Phase 0, `engineering-foundation`: the repository, tooling, CI, test harness and infrastructure skeleton.
No pipeline or advice code exists yet.

## How this project works

The project is spec-driven. The specs use Kiro's file layout as plain Markdown; Claude Code is the coding
agent:

- [`.kiro/steering/`](.kiro/steering/): what the product is, the technology, the repository structure
  and the quality gates;
- [`.kiro/specs/`](.kiro/specs/): requirements, design and tasks for each spec, built in order;
- [`docs/adr/`](docs/adr/): one record per research decision, with its sources;
- [`docs/method.md`](docs/method.md): the decision method; [`docs/source-registry.md`](docs/source-registry.md):
  where the data comes from and on what terms.

## Setup

`make setup` installs the locked Python environment, the pinned tools and the git hooks. It arrives with
task 7 of `engineering-foundation`; until then there is nothing to install.

## Repository rules

- This repository is public. Third-party data, recorded source pages and personal data about league
  members are never committed; they live in git-ignored `data/private/`.
- Private configuration (creator identities, AWS account details, API keys) lives outside the repository,
  at `FANTADAMUS_PRIVATE_CONFIG` (default `~/.config/fantadamus/private.toml`).

## Licence

**No licence is granted. All rights reserved.** The code is public so that its work can be seen; it may
not be copied, modified or distributed without written permission from the owner.
