# ADR-0005: In the MVP, each user's Claude collects the data; Fantadamus tools validate, store and decide

- **Status:** Accepted by the owner, 2026-10-24
- **Supersedes:** ADR-0004's ingestion mechanism (search, fetch and extraction by our server) for the MVP.
  ADR-0004 stays the reference for v1's server-side collection.
- **Specs affected:** `data-foundation` (MVP scope), `chat-agent` (MVP scope)

## Context

All season, Claude chat produced the inputs without any API key. It searched with Anthropic's built-in web
search, read public pages with Anthropic's fetcher, and fitted the odds in its code sandbox. It read:

- odds in betting news, fitted to team xG in code;
- player profiles on Fantacalcio.it;
- a league table for team goals;
- season ratings from Fantacalcio.it, and round ratings from Fantacalcio-Online's Fantacalcio.it column;
- probable lineups from several outlets;
- penalty notes from player profiles.

ADR-0004 rebuilt that inside our server: a Brave key, our own fetcher and extraction model, and later
API-Football and The Odds API keys (source registry D-S6, D-T1). In the MVP, though, both users already
reach Fantadamus from their own Claude app, and that Claude has web search and fetch.

## Options

| Option | For | Against |
|---|---|---|
| A. ADR-0004: our server searches, fetches and extracts | Can run on a schedule; deterministic; ready for v1 | Most to build; needs keys (Brave, plus the data APIs) |
| **B. Collector mode: the user's Claude browses and submits structured facts through MCP tools; our server validates, stores and decides** | No keys; least to build; copies what worked all season | Uses the users' Claude usage; extraction quality depends on the client model; collection happens only when someone asks |
| C. Hybrid of A and B | Best coverage | Builds both |

## Decision

**Option B for the MVP.**

```text
user: "Beto o Laurienté?" ──▶ Claude app
  1. Claude calls a read tool (e.g. compare_players)
  2. the tool answers, or returns a refresh plan: what is missing or stale, the allowed sources to read
     (fixed URLs or search hints from the source registry), and which submit tool takes each fact
  3. Claude reads those pages with its own web search and fetch
  4. Claude calls submit tools with structured facts, the source URL and the source's publication time
  5. the server validates (contract, allowed source, name resolution, quality rules), stores
     bronze → silver → gold, and recomputes
  6. Claude calls the read tool again and relays the engine's answer with its breakdown
```

- **Submit tools** (names indicative; final in the `chat-agent` spec): `submit_fixtures`,
  `submit_probable_lineups`, `submit_official_lineup`, `submit_match_result`, `submit_player_season_stats`,
  `submit_ratings`, `submit_availability`, `submit_penalty_takers`, `submit_match_odds` (1X2, over/under
  2.5, both teams to score), `submit_news_claim`. Their input schemas are the versioned pydantic contracts.
  The owner's `import-csv` writes the same tables.
- **What stays ours:** validation, storage, freshness, consensus, provenance and all arithmetic
  ([method](../method.md)). Claude never computes a probability, and never answers from what it read
  directly: it submits, then asks the tools.

## Guardrails (adapted from ADR-0004)

1. **Allowed sources only.** A submit tool accepts a fact only if its source URL's host is on the MVP
   reading list in the [source registry](../source-registry.md). That list already reflects D-S1 and
   D-T1 to D-T3. Anything else is rejected with the reason, so those decisions hold in collector mode too.
2. **No circumvention.** Claude's fetcher follows Anthropic's own rules. The agent prompt adds: never sign
   in, never get around a block or paywall; if a page can't be read, say so and use the manual path.
3. **No YouTube.** FantaCreator opinions stay manual and pseudonymised.
4. **Store facts, not pages.** Bronze holds the submitted structured payload with its source URL, the
   source's publication time, `received_at` and a content hash. No page text is stored, which is a smaller
   copyright footprint than ADR-0004's.
5. **Private.** Two users; nothing published; nothing committed to the public repository.
6. **Fantacalcio.it.** The terms risk stays accepted for the private MVP (ADR-0004, guardrail 8) and is
   resolved before v1 (registry D1).
7. **Disagreement is the server's job.** When two sources disagree, both are stored and the player is
   flagged (method §A2). Claude doesn't reconcile sources by judgement.

## Consequences

- **No API keys in the MVP.** Brave, The Odds API and API-Football move to v1; their decisions (D-S6,
  D-T1) remain approved for v1. The owner doesn't need the API-Football key yet.
- **Two gaps in the MVP**, both allowed by the method:
  - No player betting markets on the readable pages, so method §A4's anytime-scorer check is skipped and
    P(yellow) comes from the player's card history.
  - No per-player xG (N7), so goal share uses goals.
- **No headless browser.** D-S2 and D-S9 aren't needed: Claude's fetcher read Fantacalcio-Online's rating
  column all season. If that stops working, ratings fall back to manual entry.
- **The agent prompt changes.** Its MVP section allows browsing, for collection only
  ([agent-prompt.md](../agent-prompt.md)). v1 removes that section and reinstates "never browse the web".
- **Latency.** Collection happens when someone asks. Freshness is shared, so one user's refresh serves
  both. Before the deadline rush, a "warm-up" request (refresh everything for my squad) helps.
- **Cost.** Web search and tokens come out of each user's Claude plan; ours is AWS only.
- **Quality.** Client extraction errors are caught by the contracts, alias resolution, data-quality rules
  (11 starters per team, ballottaggio shares near 100 %, and so on) and cross-source disagreement flags.
  Every fact carries its URL, so answers can cite it.
- **Testing.** The submit and read tools are tested with scripted submissions; the collector itself is the
  user's Claude, so each slice ends with one manual end-to-end check in a Claude app.
- **v1** replaces collector mode with scheduled server-side ingestion (ADR-0004's route or licensed APIs).

## Sources

- The owner's account of how Claude chat gathered each input in 2026/27 (conversation, 2026-10-24)
- [ADR-0004](0004-mvp-on-demand-web-ingestion.md) and the [source registry](../source-registry.md)
- Model Context Protocol, [specification](https://modelcontextprotocol.io/specification) (tools)
