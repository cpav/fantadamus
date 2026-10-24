# ADR-0004: The MVP ingests on demand through web search, page fetch and LLM extraction

- **Status:** Accepted by the owner, 2026-10-24. **For the MVP, its ingestion mechanism is superseded by
  [ADR-0005](0005-mvp-claude-collects-tools-decide.md)** (the same day); it remains the reference for v1's
  server-side collection
- **Deciders:** the owner
- **Specs affected:** `data-foundation` (MVP scope), `chat-agent` (MVP scope)
- ADR-0001 to ADR-0003 are reserved for Spec 0 (tool choices, IaC, region and deploy identity).

## Context

On 2026-10-24 the owner pivoted the first release to an **MVP for two people** (the owner and one friend).
Their flow:

> the user calls the tool, the tool scrapes the info, pushes it to the pipelines, then queries the
> databases to advise the user.

The source research ([source registry](../source-registry.md)) found that the clean routes are slow or
costly to obtain: licensed APIs cost about €53/month and don't carry voti or probable lineups, and
Fantacalcio.it's content needs written authorisation. The owner also chose:

- **Interface:** the tools are an **MCP server**, used from each person's own Claude app. It runs locally on
  the owner's Mac first, then gets a remote endpoint on AWS so the friend can connect.
- **Extraction:** web search plus LLM extraction into our schemas, rather than hand-written site parsers.
- **Foundation:** Spec 0 (`engineering-foundation`) is built **as written** before any MVP code.

## Options

| Option | For | Against |
|---|---|---|
| A. Licensed APIs now (registry D2) | Clean terms, structured, reliable | About €53/month; no voti or probable lineups; still needs scraping or permission for those |
| B. Scheduled scraping on AWS | Data is ready before anyone asks | Builds v1's automation before the MVP proves its value; more requests, more terms exposure |
| **C. On-demand ingestion: search, fetch, LLM extraction into the medallion, cached by freshness** | Value quickly; requests only when someone asks and the data is stale; the bronze/silver/gold layers are the same as in v1 | Terms risk on some sites; first answer on stale data is slow; LLM extraction can be wrong |

## Decision

**Option C for the MVP.**

```
Claude app ──MCP tool call──▶ fantadamus MCP server
   1. which data products does this answer need?      (e.g. availability for two players' fixtures)
   2. freshness check per product                     (fresh → skip to 6)
   3. web search (Brave) with per-need query templates → pick URLs   (results used transiently)
   4. fetch pages (robots.txt checked, rate-limited)   → bronze snapshot: url, captured_at, sha256, raw
   5. LLM extraction → pydantic contract (invalid → rejected and reported) → silver → gold
   6. decision engine reads gold → answer with breakdown and source links
```

- **Shared cache.** A refresh triggered by one user serves both until the data passes its freshness target.
- **Same medallion as v1.** Bronze is append-only and hashed, silver is validated by versioned contracts,
  gold holds the data products. v1 replaces step 3–4's on-demand trigger with schedules and licensed or
  permitted sources; the layers stay.
- **Manual fallback.** `import-csv` still writes every table, and it is the route wherever the guardrails
  below rule a site out.
- **Extraction model:** a small Anthropic model on Amazon Bedrock, with output validated against the
  contract. Which model the account can invoke in `eu-north-1` is confirmed in Spec 1, because the
  gamegusto account has hit an eligibility gate on newer models.

## Guardrails

These are part of the decision. Code enforces each one, and each one has a test.

1. **robots.txt is honoured on every fetch.** A disallowed path is never fetched. For example,
   fantacalcio.it disallows `/probabiliformazioniseriea`. *How this applies (D-S1 in the source registry,
   approved by the owner 2026-10-24):* Fantadamus is a user-triggered AI agent, so robots.txt groups that name
   such agents (`ChatGPT-User`, `Claude-User`, `Claude-Web`, `Perplexity-User`) apply to it, as does `*`.
   Groups aimed only at training crawlers don't.
2. **No circumvention.** No bypassing logins, paywalls, CAPTCHAs, rate limits or bot detection. When a site
   blocks us, the source is marked unavailable and the manual path takes over.
3. **Polite rate.** At most one request per second per host, with an identifying user agent.
4. **No YouTube scraping.** YouTube's Developer Policies prohibit scraping and storing content.
   FantaCreator opinions enter by hand, pseudonymised.
5. **Search results are transient.** Brave's free plan grants AI-inference rights but not storage rights,
   so search results only choose URLs. We store the fetched page and its URL, not the result list.
6. **Fetched content stays private.** It lives in git-ignored `data/private/` locally and in a private S3
   prefix in AWS. It is never committed and never shown to users verbatim; answers carry short facts with
   source links.
7. **Personal use by two people.** No publication, no redistribution, no other users until v1.
8. **Terms are recorded, and conflicts are explicit.** Each site's terms go into the source registry.
   **Known conflict:** Fantacalcio.it's terms prohibit scraping and "any processing of the data" without
   written authorisation. The owner accepts this risk for the private MVP, and it must be resolved
   (registry D1) before v1 opens to more users.

## Consequences

- **Good:** answers within days of starting Spec 1 rather than after licensing; no data fees beyond LLM
  tokens and Brave's free tier (2,000 queries/month); the pipeline code carries over to v1.
- **Bad:** contractual risk with some sites (guardrail 8); extraction errors, mitigated by contract
  validation, data-quality rules and source links in every answer; brittleness when sites change.
- **Latency:** a Claude tool call has a time limit, so a full round refresh can't run inside one call.
  The MCP design must refresh per fixture, or start a refresh and return what's fresh now. This belongs
  to the `chat-agent` MVP design.
- **Fixtures and CI:** fetched pages can't be committed (public repository). Contract and integration
  tests use synthetic pages with the same structure, or read `data/private/` and skip with a registered
  reason when it's absent.
- **v1:** scheduled ingestion on AWS, licensed or permitted routes per the source registry (D1–D6),
  freshness targets instead of on-demand refresh, and more users.

## Sources

- Fantacalcio.it, [Termini di Utilizzo](https://www.fantacalcio.it/termini-e-condizioni) (June 2026) and
  [robots.txt](https://www.fantacalcio.it/robots.txt)
- YouTube, [API Services Developer Policies](https://developers.google.com/youtube/terms/developer-policies)
- Brave Search API, [pricing](https://api-docs.search.brave.software/pricing) and
  [help and FAQ](https://api-docs.search.brave.software/resources/help) on storage rights
- Owner's gamegusto project: `services/search_service.py` (Brave client) and `services/bedrock_service.py`
  (Bedrock Converse client), reused under Spec 1
