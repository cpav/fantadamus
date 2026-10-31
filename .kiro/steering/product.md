---
inclusion: always
---

# Product: Fantadamus, a Fantacalcio advisor

## Purpose

Fantadamus advises players of **Fantacalcio** (Serie A fantasy football, Classic rules) on who to field.
The audience ranges from a group of friends to a live chat under a YouTube stream, where people post two
names and ask which to play. **The method is [`docs/method.md`](../../docs/method.md)** (the owner's,
2026-10-24): the `decision-engine` spec implements it and takes its acceptance tests from §A9. The chat
agent's behaviour is [`docs/agent-prompt.md`](../../docs/agent-prompt.md), and the shape of every answer, a
forecast like a good weather app's, is [`docs/answer-formats.md`](../../docs/answer-formats.md). Numbers marked *(start)* are
starting values, calibrated from logged predictions (§A8). The earlier hand-written playbook is not used.

The product must stay **cheap per question as the number of users grows**. That single constraint drives
most of the architecture: facts are collected once and served many times (see `tech.md`).

## Users

| User | Situation | What they need |
|---|---|---|
| League player (owner and friends) | Known squad, known league rules | Best eleven and ordered bench; "X or Y?" with a short breakdown |
| Live-chat viewer | Anonymous, rules unknown, asks minutes before the deadline | A fast answer to "X or Y?" under standard Classic rules, asked once for their rules |
| Owner / operator | Runs the pipelines | Freshness, disagreements and gaps per round (`status`), cost visibility |

## Scope (v1)

1. **Best lineup for a league's own rules.** Given a squad and the league's rules, produce the eleven and
   the ordered bench that maximise expected score.
   - Rules are set at sign-up or at the start of a session.
   - The options mirror the settings of official Fantacalcio.it leagues: goal thresholds, bonuses and
     penalties, modifiers, bench size, substitutions and allowed formations. They are researched and
     enumerated in the requirements of the spec that owns the League domain.
   - When the league is unknown (a live chat, say), default to standard Classic rules, ask once and
     remember the answer.
2. **"Who do I play?" at three levels.**
   - *Club level:* who will actually start for the real team. This covers the starting probability, the
     risk of only coming off the bench and, above all, **the expected impact of a substitute**: expected
     goals and assists in previous substitute appearances, usual minutes, fitness, form and the opponent.
   - *User level:* "X or Y?", the most common question by far, often asked minutes before the deadline.
     The answer carries a short, transparent breakdown, not just a name, and includes bench advice
     ("start X, put Y first on the bench").
   - *Formation level:* for example, is my fourth defender worth more than my fourth midfielder this week?
3. **Match-up intelligence.** One card per fixture combining:
   - *numbers:* form, goals for and against (home and away), injuries, suspensions, penalty and set-piece
     takers, rest days and midweek European fixtures;
   - *context:* coach changes, ownership changes, tactical shifts, credible reports and rumours;
   - *implications per player:* goals conceded for keepers, each attacker's share of his team's output,
     rotation risk.

**Out of scope for v1:** trades, auctions and market valuation. Don't build them.

## Releases: MVP, then v1

| | **MVP** (now) | **v1** (later) |
|---|---|---|
| Users | Two: the owner and one friend | More: friends' leagues, live-chat viewers |
| Interface | Each person's own Claude app, calling the Fantadamus **MCP tools**: local on the owner's Mac first, then a remote endpoint on AWS | Decided in the `chat-agent` spec |
| Ingestion | **Collected by Fantadamus itself** from the approved pages, on demand and on a schedule ([ADR-0006](../../docs/adr/0006-mvp-fantadamus-collects-round-facts.md)); **each user's Claude collects only as the fallback** when a page can't be read: a read tool reports what's missing and where to read it, Claude submits structured facts, and the tools validate, store and decide ([ADR-0005](../../docs/adr/0005-mvp-claude-collects-tools-decide.md)) | **Automated.** Schedules driven by the fixture calendar, licensed or permitted sources ([source registry](../../docs/source-registry.md)) |
| Storage | DuckDB over Parquet with the medallion layout; local first, the same layout on S3 once remote | Lakehouse on AWS (Iceberg, Glue, Athena), per `tech.md` |
| Sources | The MVP reading list in the source registry: the approved sites only, enforced by the submit tools | Routes approved per source, including the licensed APIs |
| Agent browsing | **Allowed, for fallback collection only** (the agent prompt's MVP section) | **Not allowed:** the tools gather everything |

The MVP keeps the medallion layers, contracts and quality rules of v1, so v1 changes how data arrives,
not what happens to it.

## Principles: how professionals research football, and what we copy

| Professional practice | Our rule |
|---|---|
| **Collect once, reuse everywhere.** Opta codes each match once and sells the same feed to clubs, broadcasters, bookmakers and apps. | Every fact is fetched once per refresh and shared across all users. The chat model never answers from the web: in the MVP it collects facts for the tools when they ask, and in v1 it doesn't browse at all. Answers always come from the data products. |
| **Price bonuses from the market.** Bookmakers aggregate more information than any single source. | Team xG comes from the betting lines (1X2, over/under, both teams to score); a player's goal and assist chances are his share of it. Anytime-scorer odds are a check: a large gap is investigated, never averaged (method §A4). Bonus probabilities must be precise, so they are never eyeballed. |
| **Never trust one source.** Providers cross-check each other; Football Manager calibrates evaluators against peers and reference players. | Probable lineups come from 2–3 sources. Disagreement is stored as information, never quietly averaged away. |
| **Human judgement is data, with provenance and biases.** Fantacalcio "voti" are journalists' ratings with their own logic; fans talk about raters' favourites ("pupilli"). | Store who said what, when and from which source. Measure each rater's bias per player against performance statistics. Treat "pupilli" mentions as claims. |
| **Sit downstream of existing data products.** Clubs buy feeds rather than collect. | We don't build collection. We consume lineups, fixtures, results, ratings, statistics and news; our value is the decision layer on top. |
| **Licensing changes.** FBref lost its Opta licence in January 2026. | Keep a source registry with each source's terms of use, and a manual CSV fallback for every source. |
| **The shape exists elsewhere.** Twelve's Earpiece is a chat interface over structured event data. | Same shape for Fantacalcio: a chat front end over precomputed data products. |

### Two rules for context and news

- **Price context at its real size, and always show it.** Context feels big and usually moves numbers very
  little. Most of a "new coach bounce" is a struggling team regressing to its normal level; a defender's
  rating moves only about ±0.15 with his team's result (the owner's estimate; to be measured). Any adjustment from context is
  **bounded, logged and visible** in the breakdown.
- **Context mostly changes uncertainty, not the expected score.** A new coach's first match, a reported
  tactical change or a dressing-room rumour mainly widens uncertainty on the lineup (more disputed places,
  lower confidence) unless the numbers back up a shift. **Exception:** midweek European fixtures are the
  most reliable structured signal of rotation seen this season (Kean was benched for Como's Champions
  League debut).

## Trust, privacy and provenance

- **FantaCreators** (the fantasy-football YouTubers whose lineup opinions we use) are identified only in
  private configuration outside the repository. Their identity never appears in the repository, fixtures,
  logs, gold data products or user-facing output. Opinions are shown as "pundit consensus".
- No third-party content is scraped or downloaded without a route the owner has approved. For the MVP
  that route is ADR-0005: each user's Claude reads only the sites on the registry's MVP reading list, never
  circumvents a block, never uses YouTube, and the tools store facts with their source URL, never page
  text. The owner accepts the remaining terms risk for
  a private two-person MVP; it is resolved before v1.
- The code repository is public. Third-party data and personal data about league members are never
  committed to it (see `structure.md`).
- Every answer can be traced back to the snapshots it used (source, captured_at, content hash).

## Delivery order

Re-planned on 2026-10-26 to reach a usable advisor sooner: work goes in thin vertical slices, each taking one
question from data to answer, instead of three full specs one after another. Brought up to date on 2026-10-31.

**Phases 1 to 3 are the MVP**: two players, data fetched by Fantadamus from the approved pages and the rest read
by their Claude through `read_page`. **Phase 4 is v1.** Every feature is built once, in the MVP's slices, and
carries over: v1 changes how the data arrives (licensed or permitted sources, on a schedule) and where it runs
(AWS), not what the answers say.

| Phase | Spec | Status rule |
|---|---|---|
| 0 | `engineering-foundation`: repository, tooling, CI, test harness, agent hooks | Done, signed off 2026-10-26; its AWS skeleton moved to Phase 3 |
| 1 | `mvp-x-or-y`: "X or Y?" for two forwards in the owner's Claude Desktop: the facts, the method for forwards, `compare_players` | Done, signed off 2026-10-26 |
| 2 | Slices, one small spec each, toward the full lineup: **(a)** `mvp-collect`: Fantadamus collects the round's facts itself, sources compared, forecast-style answers (built; the real round is running); **(b)** every role: "X or Y?" and one player's outlook for keepers, defenders and midfielders, with players' season figures read in bulk; **(c)** the full lineup: the user's squad, the league's full rules, the eleven, the bench order and the formation, simulated to give the expected score and the chance of each threshold; **(d)** later, match cards | Each after the previous slice has answered a real round |
| 3 | Online for the second player: the remote MCP endpoint, plus the AWS skeleton, budget alarm and deploy gate moved from Phase 0 | After the slices the second player needs |
| 4 | v1: automated, scheduled pipelines on licensed or permitted sources; more users | After the MVP has been used for real rounds |

Live forecasts during a match, and alerts such as "the official lineup changes your call", come in their own
specs once the full lineup works.

Gates and the Definition of Done are in `quality.md`.

## Glossary

| Term | Meaning |
|---|---|
| Round (giornata) | One Serie A matchday. Its **deadline** is the kickoff of its first fixture. |
| Voto / rating | A journalist's 1–10 match rating of a player. The league uses Fantacalcio.it ratings. |
| Fantavoto | Rating plus bonuses and penalties (goals, assists, cards…) under the league's rules. |
| Ballottaggio | A two-way contest for one starting place, usually published with percentage shares. |
| p_start | Probability that a player starts. |
| Cameo | Coming off the bench and getting a rating. |
| Schierabilità | How safe a player is to field, as rated by a pundit. |
| Pupillo (pl. pupilli) | A rater's favourite: a player consistently rated above his performance. |
| FantaCreator | A fantasy-football content creator whose lineup videos we use as one opinion source. |
| Quotazione / FVM | Official player price and Fantacalcio market value from the official list. |
| Classic rules | The standard Fantacalcio.it league format (as opposed to Mantra). |
| Key | The ordering key of method §A3: (p_start·E_start + p_cameo·E_cameo) / (p_start + p_cameo). |
| Team xG | A team's expected goals in a fixture, fitted from the betting lines (Poisson with a Dixon-Coles correction). |
| De-margined odds | Bookmaker prices with the bookmaker's margin removed, so the implied probabilities sum correctly. |
