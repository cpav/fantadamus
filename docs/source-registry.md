# Source registry (draft for discussion)

Status: **Draft, 2026-10-17; MVP note added 2026-10-24.** This is a research summary, **not legal
advice**. Anything marked *to verify* must be checked against the provider's own current terms before its
ADR.

> **MVP (from 2026-10-24).** In the two-person MVP, **each user's Claude collects the data** and submits
> structured facts through our MCP tools ([ADR-0005](adr/0005-mvp-claude-collects-tools-decide.md),
> accepted; it supersedes ADR-0004's server-side fetching for the MVP). The **MVP reading list** below is
> what Claude reads, and its allowed hosts are the submit tools' allowlist. The routes and decisions after
> it (D1–D6) are the **v1 plan**.

## MVP reading list (approved 2026-10-24)

Each site was checked on 2026-10-24 with one request to its `robots.txt` and one to its home page or a
sample page, at most one request per second. The checks were run from the owner's machine; nothing
fetched is kept in the repository.

**Since ADR-0005:** the site decisions (D-S1, D-T1 to D-T3) define which hosts are allowed. Decisions about
our own fetching and APIs (D-S2, D-S4, D-S6, D-S9, and API-Football under D-T1) take effect from v1.
In collector mode, Claude's own fetcher applies Anthropic's robots.txt rules; the allowlist keeps D-S1's
exclusions either way.

### Allowed sources (the submit tools' allowlist)

| Allowed hosts | Excluded hosts (reason) |
|---|---|
| `fantacalcio.it` (terms risk accepted), `fantacalcio-online.com`, `sosfanta.com` (D-T3), `gazzetta.it` (D-T3, free articles), `corrieredellosport.it`, `tuttosport.com`, `tuttomercatoweb.com`, `it.wikipedia.org`, `en.wikipedia.org`, `wikidata.org`, `livetipsportal.com`, `jamma.tv` and `jamma.it` (D-T3) | `sport.sky.it`, `goal.com`, `fotmob.com`, `sportsgambler.com`, `betexplorer.com`, `soccerway.com`, `legaseriea.it`, `transfermarkt.*` (terms, D-T1/D-T2); `fantamaster.it`, `calciomercato.com`, `ansa.it`, `football-data.co.uk`, `understat.com` (robots.txt, D-S1); `fbref.com`, `sofascore.com`, `oddschecker.com` and the bookmakers (blocked); `youtube.com` (no scraping) |

The owner's `import-csv` is always allowed, with the source recorded as manual.

### How guardrail 1 (robots.txt) is applied

- The `User-agent: *` group applies to us. The fetcher identifies itself as
  `Fantadamus/0.1 (user-triggered AI agent; personal use)` plus a contact address.
- **Groups that name user-triggered AI agents also apply to us**, because that is what Fantadamus is:
  `ChatGPT-User`, `Claude-User`, `Claude-Web`, `Perplexity-User`. Choosing a new user-agent name to slip
  past a site that turns those agents away would be gaming robots.txt.
- Groups that name **training crawlers** (`GPTBot`, `ClaudeBot`, `CCBot`, `Google-Extended`,
  `Applebot-Extended`, `Meta-ExternalAgent`, `Bytespider`) don't apply. We never train on what we fetch.
- A `401`, a `403`, a login wall or a bot challenge ("Just a moment…") means **blocked** (guardrail 2):
  the source is unavailable and the manual path takes over.

### Site status

"Data in HTML" means a plain fetch returns the data, so no JavaScript has to run.

| Site | robots.txt for us | Data in HTML? | Login or paywall | MVP use |
|---|---|---|---|---|
| fantacalcio.it | Allowed, except `/probabiliformazioniseriea`, `/ricerca` and a few others | Yes: probable lineups, injured, unavailable, suspended, penalty takers, quotazioni, and **player profiles** (`/serie-a/squadre/{club}/{player}/{id}`: goals, assists, cards, penalties scored/taken, appearances). **No:** match voti and the calendar render in JavaScript | The listone Excel (`/api/v1/Excel/prices/…`) returns **401** without login | **Yes.** Terms conflict accepted for the MVP (ADR-0004, guardrail 8) |
| sosfanta.com | Allowed (`/api` and `/modal` disallowed) | Yes: probable lineups, official lineups, unavailable table, match voti articles | No | **Yes**; terms not found, kept provisionally (D-T3) |
| sport.sky.it | Allowed for `/calcio/serie-a/…`; `/calcio_italiano/` and `/content/` disallowed | Yes: per-match probable lineups, unavailable lists per round, match pages (score, scorers), ratings, and the **league table** (`/calcio/serie-a/classifica`: goals for and against per team) | No | **No**: its terms forbid scraping, including by AI tools (D-T1) |
| gazzetta.it | Allowed: only training crawlers are blocked | Yes for free articles: ratings, live match pages, news | Some G+ articles are paywalled, so skipped | **Yes**, free articles only; terms not found, kept provisionally (D-T3) |
| corrieredellosport.it | Allowed; publishes an [`llms.txt`](https://www.corrieredellosport.it/llms.txt) inviting AI assistants | Yes: articles and ratings; probable lineups are photo galleries | No | **Yes** |
| tuttosport.com | Allowed (same publisher; `llms.txt`) | Yes: articles, ratings | No | **Yes** |
| tuttomercatoweb.com | Allowed | Yes: news | No | **Yes**, news |
| wikipedia.org, wikidata.org | Allowed; use the MediaWiki API with a contact user agent | Yes | No | **Yes**. Open licences (CC BY-SA, CC0) |
| api-football.com (API-Sports) | n/a: a licensed API, not page fetching | Structured JSON: fixtures, lineups, events with minutes, player match stats, standings, injuries, coaches | Free key in the owner's name (100 requests/day) | **Yes** (D-T1). Terms read at sign-up; current-season access confirmed by a test call |
| legaseriea.it | Allowed | Fixture list yes; **match centre no** (lineups and stats load in JavaScript widgets) | No | **No**: its terms forbid extraction (D-T2) |
| sportsgambler.com | Allowed (`/team-news_player.php`, `/odds.php` disallowed) | Yes: injury lists | No | **No**: its terms forbid automated access (D-T2) |
| fotmob.com | Allowed, except `/api/*` | Match pages embed their data (xG, ratings, events) as JSON in the HTML | No | **No**: its terms forbid systematic retrieval (D-T2); N7 comes from API-Football |
| transfermarkt.it | Allowed | Yes | Bot protection likely | **No**: its terms restrict its databases to its own site (D-T2) |
| fantacalcio-online.com | Explicitly allows all crawlers, including AI | **Probable lineups: yes.** The page shows a consensus of four outlets' lineups, plus each match's 1X2 odds with implied percentages and the chance of 3+ goals. **Match voti: no**: the Fantacalcio.it rating column loads in JavaScript | Partly, for subscriber features | **Yes** for probable lineups and odds; voti need D-S9 *(corrected 2026-10-24: the first check missed the data)* |
| goal.com (`/it`) | Allowed | Yes: per-round probable lineups with ballottaggio percentages (`/it/liste/probabili-formazioni-serie-a-giornata-{n}-…`) | No | **No**: its terms reserve text and data mining (D-T2) |
| livetipsportal.com | Allowed | Yes: per-match odds previews from Italian bookmakers (Betsson, Eurobet): 1X2, over/under 2.5, goal/no goal. URLs vary (`quote-…`, `pronostico-…`), so found by search | No | **Yes**, N14 cross-check |
| jamma.tv | Allowed (foreign-language sections disallowed) | Yes: betting news, including Betsson odds round-ups per round. Found by search | No | **Yes**, N14 cross-check; terms not found, kept provisionally (D-T3) |
| it.soccerway.com (news) | Allowed for `/news/` (data sections disallowed) | Yes: betting previews with odds | No | **No**: same terms as BetExplorer (D-T2) |
| fantamaster.it | **Blocks** `ChatGPT-User`, `Claude-Web`, `Perplexity-User` | — | — | **No** |
| calciomercato.com | **Blocks** `ChatGPT-User`, `Perplexity-User`, `Claude-Web` | — | — | **No** |
| ansa.it | **Blocks** `ChatGPT-User`, `Claude-Web` | — | — | **No** |
| football-data.co.uk | **Blocks** `ChatGPT-User`, `Claude-Web` | — | — | **No** automated use. The owner may download its CSV by hand |
| understat.com | **Disallows everything** | — | — | **No** |
| fbref.com | Bot challenge (403) | — | — | **No** (guardrail 2) |
| sofascore.com | 403 | — | — | **No** (guardrail 2) |
| clubelo.com, uefa.com | Not reachable during the check | — | — | Retry later; not critical |
| **Odds sites (checked for N14)** | | | | |
| betexplorer.com | Allowed (query-string pages disallowed) | League page: **average 1X2 odds in the HTML**. Match pages: over/under, both teams to score and scorer tabs load in JavaScript | No | **No**: its terms forbid scraping (D-T2, reversing D-S7) |
| oddschecker.com | Allowed | Bot challenge (403) | — | **No** (guardrail 2) |
| oddsportal.com | Allowed, but its odds feeds (`*/feed/*`, `*/ajax-nextgames-odds/*`) are disallowed | Odds load from the disallowed feeds | — | **No** |
| eurobet.it | Allowed, but its odds services (`*/detail-service/*`, `*/_next/*`) are disallowed | JavaScript app | Account for betting | **No** |
| betfair.it | Market and event pages (`/sport*eventId*`, `*marketId*`) disallowed | JavaScript app | Account | **No** for pages; the Exchange API is a separate, account-based route (D-S8) |
| snai.it, sisal.it, bet365.it, goldbet.it, lottomatica.it, planetwin365.it, betflag.it | "Access Denied" even for robots.txt (bot protection or geo-blocking outside Italy) | — | — | **No** (guardrail 2) |
| diretta.it / flashscore.it | Live and results sections disallowed; odds load in JavaScript | — | — | **No** |

### Terms of use (read 2026-10-24, guardrail 8)

Each site's terms page was read once on 2026-10-24 for clauses on automated access, scraping, extraction,
text and data mining (TDM), AI use and reuse. Paraphrased; follow the links for the exact wording. **Not
legal advice.**

| Site | What the terms say | Conflict with our use? | Action (approved 2026-10-24) |
|---|---|---|---|
| fantacalcio.it ([terms](https://www.fantacalcio.it/termini-e-condizioni)) | Scraping and "any processing of the data" need written authorisation; personal copies not on a networked server | **Yes** | Keep: risk **accepted** by the owner for the private MVP (ADR-0004, guardrail 8); resolve before v1 (D1) |
| sport.sky.it ([note legali](https://www.sky.it/info/note-legali.html)) | No robots, bots, spiders, crawlers or scraping, nor data extraction by automated or manual means, without Sky's written authorisation; this explicitly covers AI tools. Personal, private, non-commercial viewing only | **Yes**, explicit | **Drop**; replace its roles (D-T1) |
| goal.com ([terms](https://www.goal.com/it/legale/termini-e-condizioni)) | A clause titled "No text or data mining, or web scraping": no robots, scrapers or automated analysis of the site's text and data | **Yes**, explicit TDM reservation | **Drop** (it was only an N3 cross-check) |
| fotmob.com ([terms](https://www.fotmob.com/tos.txt)) | Robots, spiders and other systematic, regular or bulk retrieval are forbidden; AI assistants may index public pages per robots.txt if they don't reproduce data in bulk | **Yes** for a pipeline | **Drop**; N7 from the free licensed API (D-S3) |
| sportsgambler.com ([terms](https://www.sportsgambler.com/terms-conditions/)) | No automated means (bots, scrapers, crawlers, data-mining tools) without written permission; no AI training | **Yes** | **Drop** (it was an N8 cross-check) |
| betexplorer.com ([terms](https://www.betexplorer.com/terms-of-service.php)) | Personal, non-commercial use only; no scraping, aggregating or embedding without consent; database right on its content | **Yes** | **Drop**; this reverses D-S7. Fantacalcio-Online's odds cover the 1X2 cross-check |
| it.soccerway.com ([terms](https://it.soccerway.com/terms-of-use/)) | Same publisher (Livesport) and the same clauses as BetExplorer | **Yes** | **Drop** |
| legaseriea.it ([terms](https://www.legaseriea.it/terms-and-conditions)) | Personal, non-commercial use; no extraction or use of content without written consent | **Yes** | **Drop**; fixtures come from Wikipedia and the free API |
| transfermarkt.it ([terms](https://www.transfermarkt.it/intern/anb)) | Its databases and material may be used only on Transfermarkt; reproduction prohibited | **Yes** | **Don't use** (it was a D-S3 candidate) |
| fantacalcio-online.com ([terms](https://www.fantacalcio-online.com/it/termini-e-condizioni)) | Content may be used for personal, non-commercial purposes with attribution; robots.txt explicitly welcomes AI crawlers. Only account creation by bots is banned | **No**, for personal use with attribution | **Keep**; store the source and show it as attribution |
| corrieredellosport.it, tuttosport.com ([CdS terms](https://www.corrieredellosport.it/widget/utility/2018/05/18-43095287/condizioni_generali_di_utilizzo), [legal note](https://www.corrieredellosport.it/widget/utility/2017/10/30-33143936/nota_legale)) | No reproduction, redistribution or republication of content; no scraping or TDM clause; `llms.txt` invites AI assistants | **No**, for reading and extracting facts privately | **Keep**; never republish text |
| tuttomercatoweb.com ([copyright](https://www.tuttomercatoweb.com/copyright/)) | Reproduction allowed if the source (and author) are clearly credited | **No** | **Keep**, with attribution |
| livetipsportal.com ([disclaimer](https://www.livetipsportal.com/it/disclaimer/)) | All rights reserved to its publisher; no scraping clause found | **No explicit conflict** | **Keep** for odds facts; never republish |
| wikipedia.org, wikidata.org ([Terms of Use](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use)) | CC BY-SA (Wikipedia) and CC0 (Wikidata); API use with an identifying user agent is welcome | **No** | **Keep**, with attribution |
| The Odds API ([terms](https://the-odds-api.com/terms-and-conditions.html)) | Storing data indefinitely, displaying it, deriving values and training models are permitted; reselling it as a data product is not | **No** | **Keep** |
| Brave Search API | Free plan: AI-inference rights, no storage rights | **No**, as designed (results not stored) | **Keep** |
| gazzetta.it, sosfanta.com, jamma.tv | **Terms page not found**: not linked in the HTML we fetched, and searches didn't surface it | Unknown | **Keep provisionally** (D-T3): read facts only, never republish, re-check |

**Decisions for the owner (terms)**: approved 2026-10-24, as recommended.

| # | Decision | Recommendation |
|---|---|---|
| D-T1 | **Sky** was primary for N5 (match pages) and a cross-check for N2, N3, N6 and N8, but its terms explicitly forbid scraping, including by AI tools. Accept that risk like Fantacalcio.it's, or replace it? | **Replace.** Use API-Football's free tier (licensed; to verify: current-season access and its terms) for events, minutes, lineups, standings and team goals, plus Wikipedia. This keeps the accepted risk confined to Fantacalcio.it, the one source we can't replace. API-Football's terms page returns 403 to our fetcher (bot protection), so you'd read the terms when you sign up for the free key; a test call with `season=2026` confirms coverage. If either fails: Wikipedia, Fantacalcio.it profiles and football-data.org's free tier (fixtures and results only) |
| D-T2 | Drop the sites whose terms prohibit our use and which were only cross-checks: Goal, FotMob, Sportsgambler, BetExplorer (reversing D-S7), Soccerway, Lega Serie A, Transfermarkt | **Yes.** N3 keeps three views (Fantacalcio.it, Fantacalcio-Online's four-outlet consensus, SOS Fanta); N14 keeps Fantacalcio-Online, livetipsportal and Jamma as cross-checks |
| D-T3 | Gazzetta, SOS Fanta and Jamma: terms not found. Keep them provisionally, reading facts only and never republishing, and re-check before v1? | **Yes** |

### What we read for each need

The search column shows the Brave query template, used only where a page's URL can't be built directly.
`{home}`, `{away}` and `{n}` (the round) come from the fixtures.

| Need | Primary | Cross-check | Found by | Refresh (MVP) | Manual fallback |
|---|---|---|---|---|---|
| **N1** Player register | Fantacalcio.it listone Excel, **downloaded by the owner** (it needs login) | `fantacalcio.it/quotazioni-fantacalcio` page for new arrivals | Fixed URL | Weekly, and after transfer windows | It *is* manual: `import-csv players` |
| **N2** Fixtures and results, all competitions | Fantacalcio.it's Serie A calendar (round by round, kickoffs in Italian time); changed 2026-10-30, as Claude's reader saw only a stale cache of Wikipedia | Wikipedia: the Serie A season page and each club's season page (league, cup and European matches) | Fixed URL; search hint | Daily on match days, otherwise weekly | CSV. *v1: API-Football* |
| **N3** Probable lineups (three views) | `fantacalcio.it/probabili-formazioni-serie-a`, with ballottaggio percentages | Fantacalcio-Online's page (itself a consensus of four outlets); `sosfanta.com/lista-formazioni/probabili-formazioni-serie-a/` (D-T3). Sky and Goal are dropped (D-T1, D-T2); FantaMaster stays excluded (D-S1) | Fixed URLs | Twice a day from 72 h before the round; every 2–3 h in the last 24 h | CSV |
| **N4** Official lineups | Fantacalcio.it news "`{home}-{away}`-le-formazioni-ufficiali" | SOS Fanta "formazioni ufficiali" articles (D-T3) | Claude's search: `{home} {away} formazioni ufficiali site:fantacalcio.it` | From 75 min before each kickoff, whenever a user asks | CSV. *v1: API-Football* |
| **N5** Match events and minutes | **Fantacalcio.it player profiles** (season goals, assists, cards, penalties, appearances, counted the league's way), read for the players asked about; Fantacalcio.it's Serie A table for team goals (goals for and against; Wikipedia's table as the fallback) | Wikipedia match results and scorers; Gazzetta live pages (D-T3) | Profile URLs from player IDs; fixed URL; search hints | After each round | CSV. *v1: API-Football events with minutes, so goal share can use team goals while he's on the pitch* |
| **N6** Ratings (voti) | Fantacalcio.it ratings, the league's rater: per round from **Fantacalcio-Online's match pages** (their Fantacalcio.it column, as Claude read it all season); season averages from Fantacalcio.it profiles; else the owner enters them | Gazzetta (D-T3), Corriere dello Sport and Tuttosport ratings articles; SOS Fanta voti articles (D-T3; rater to identify) | Claude's search: `{home} {away} pagelle voti site:<rater site>` | The morning after each match | CSV (owner) |
| **N7** xG, xA, chances, saves | **Gap in the MVP**: no allowed page carries them | — | — | — | Goal share uses goals, as method §A4 allows. *v1: API-Football player and team match stats* |
| **N8** Injuries, suspensions, fitness | `fantacalcio.it/infortunati-serie-a`, `/indisponibili-serie-a`, `/squalificati-e-diffidati-campionato-serie-a` | SOS Fanta unavailable table (D-T3) | Fixed URLs | Daily; twice a day in the last 48 h | CSV. *v1: plus API-Football injuries* |
| **N9** Penalty and set-piece takers | `fantacalcio.it/rigoristi-serie-a` | Notes on Fantacalcio.it player profiles (e.g. a club's first-choice taker); derived from N5 events; manual overrides | Fixed URL | Weekly and after each match | CSV |
| **N10** Coaches, club events, news | Coaches: Wikidata and Wikipedia. News: Corriere dello Sport, Tuttosport, TMW, Fantacalcio.it, and Gazzetta and SOS Fanta (D-T3) | Two independent outlets confirm a claim | Claude's search per club and topic, for example `{club} allenatore OR infortunio OR formazione` | Every 6 h; hourly in the last 24 h | CSV |
| **N11** Team-strength prior | Derived from N14 match lines (team xG, method §A4) | Regressed team form (method §A5); ClubElo (retry) | — | With N14 | CSV |
| **N12** FantaCreators | **Manual**: the owner's notes, pseudonymised | — | — | Weekly | CSV |
| **N13** League data | **User-supplied**: the owner's export or CSV of rules, rosters and lineups | — | — | When it changes | CSV |
| **N14** Betting markets | **Match lines from betting news**: livetipsportal's Betsson and Eurobet previews and Jamma's Betsson round-ups (1X2, over/under 2.5, goal/no goal), plus Fantacalcio-Online's 1X2 and P(3+ goals) per match: the route that worked all season | Each source against the others; disagreement is kept, not averaged | Claude's search: `{home} {away} quote over under goal no goal` | Daily from 72 h before the round; every 3 h in the last 24 h | CSV of odds by hand. **Player markets are a gap in the MVP**: no anytime-scorer check, and P(yellow) from card history. *v1: The Odds API* |

**Collection load (MVP).** Claude's searches and page reads come out of each user's Claude plan, not ours.
A full refresh for one round is roughly 10 probable-lineup pages, 10 odds articles, 3 unavailable pages and
a profile per player asked about. Because freshness is shared, a "warm-up" request before the deadline
rush (refresh everything for my squad) saves both users time.

### Decisions for the owner (scrape list): all approved 2026-10-24, as recommended

| # | Decision | Recommendation |
|---|---|---|
| D-S1 | Apply guardrail 1 as written above: rules aimed at user-triggered AI agents apply to us, rules aimed at training crawlers don't | **Yes**: it's the honest reading of the guardrail you approved |
| D-S2 | Use a headless browser (Playwright) for JavaScript-rendered pages: Fantacalcio.it voti, the Lega Serie A match centre, Fantacalcio-Online? It renders pages as any browser does; it never logs in or solves challenges | **Yes, for Fantacalcio.it voti only**, and only if they are public without login. It runs locally first; it's heavy for Lambda |
| D-S3 | FotMob (xG) and Transfermarkt (injuries): their terms likely prohibit scraping (to read). Accept that risk, or fill N7 from a free licensed API (API-Football's free tier: 100 requests/day) instead? | **Read the terms first.** If they prohibit it, use the free API for N7 rather than add terms risk **Resolved by D-T1 and D-T2:** both dropped on their terms; N7 comes from API-Football. |
| D-S4 | Use The Odds API's free tier (500 credits/month) for N11: a licensed API, not scraping | **Yes** |
| D-S5 | Owner's manual chores: weekly listone download, FantaCreator notes, league data, voti if D-S2 fails | Confirm you're happy to do these |
| D-S6 | **Betting markets (N14) through The Odds API's free tier**, for match lines *and* player markets. This extends D-S4. Budget: about 70 credits a round (league lines in one call; 3 player markets × 10 events; two refreshes), about 300 of the free 500 a month. The paid tier is $30/month for 20,000 credits if needed | **Yes** (approved 2026-10-24) |
| D-S7 | Scrape BetExplorer's league page for average 1X2 odds as a cross-check of the API's lines | **Yes** (approved 2026-10-24), subject to its terms **Reversed by D-T2:** BetExplorer's terms forbid scraping. |
| D-S8 | Betfair Exchange API: the sharpest match prices, but it needs an Italian Exchange account in your name and is licensed for personal use only | **Not now** (approved 2026-10-24); revisit if the free API's lines prove thin |
| D-S9 | Extend D-S2's headless rendering to **Fantacalcio-Online's match pages**, to read their Fantacalcio.it rating column: the same data as Fantacalcio.it's own voti, from a site whose robots.txt welcomes AI crawlers | **Yes** (approved 2026-10-24): prefer it to rendering fantacalcio.it itself |
| D-S10 | Betting-news pages (livetipsportal, Jamma) and Fantacalcio-Online's odds as the fallback for match lines when the API lacks `totals` or `btts` for a match. They're snapshots at publication time, so the as-of time is the article's | **Yes** (approved 2026-10-24) |

### Still to check before each slice (slice loop, step 1)

- ~~Read each site's terms of use and record conflicts here~~ **Done 2026-10-24** (see "Terms of use" above); D-T1 to D-T3 approved. Originally (guardrail 8): Sky, Gazzetta, Corriere dello
  Sport, Tuttosport, SOS Fanta, TMW, sportsgambler, FotMob, Transfermarkt, Wikipedia (CC BY-SA attribution),
  **The Odds API** (use and caching of odds data) and **BetExplorer**.
- The Odds API on a trial round: which EU bookmakers price Serie A `totals` and `btts`, how many of the
  10 matches get `player_goal_scorer_anytime` from US bookmakers, and the real credit cost per refresh.
- Confirm whether Fantacalcio.it's match voti are public without login (needs a rendered page, D-S2).
- Identify the rater behind SOS Fanta's voti articles.
- ~~Read the terms of Goal, livetipsportal, Jamma and Soccerway~~ Done 2026-10-24.
- **API-Football (v1, no longer needed for the MVP):** when v1 starts, sign up for the free key and put it in private configuration (`FANTADAMUS_PRIVATE_CONFIG`), never in the repository or a chat; read the terms in the dashboard; a test call with `season=2026` confirms current-season access, lineup timing and whether Serie A matches carry expected goals.
- Retry ClubElo and UEFA.

## How to read this

Each need lists candidate sources, what they give us, how we'd access them, their terms, cost and
freshness. Every source gets one of these **route types**:

| Route | Meaning | Can we automate it? |
|---|---|---|
| **Licensed** | A provider sells or grants API access under terms that cover our use | Yes |
| **Open** | Published under an open licence (for example Wikidata, CC0) | Yes |
| **Permission** | Allowed only with written permission from the owner of the content | Only once permission is granted |
| **User-supplied** | Data our users own and give us (their rosters, rules, lineups) | Yes, through import |
| **Manual** | The owner reads a source and records facts or judgements by hand, through `import-csv` | No: human in the loop |
| **Derived** | We compute it ourselves from data we hold legitimately | Yes |
| **Blocked** | The terms forbid our use | No |

## The headline finding: Fantacalcio.it

Fantacalcio.it is the natural anchor: our league scores with its *voti*, and it publishes the player list,
roles, probable lineups and three raters' marks (its own, plus the "Roma" and "Torino" desks). Its
[Terms of Use](https://www.fantacalcio.it/termini-e-condizioni) (June 2026, Fantacalcio S.r.l.) say:

- copying, reproducing or processing the content needs **written authorisation**, and the ban
  "extends to any processing of the data" (*Navigazione*, cl. 3(b));
- **scraping** and any automated tool to copy or access pages is prohibited (cl. 3(a)), as is evading the
  tools that exclude automated systems (cl. 3(e));
- personal, non-commercial copies are allowed, but **"not on a server or a networked storage device"**
  (*Proprietà Intellettuale*, cl. 3);
- there is no API, no licensing contact and no TDM reservation in the terms.

**Consequence:** any Fantacalcio.it content inside Fantadamus (voti, roles, quotazioni, probable lineups),
even typed in by hand, needs written authorisation, because Fantadamus stores it on AWS and serves it to
other people. Facts that aren't Fantacalcio.it's own content (who scored, who started) can come from
elsewhere. Fantacalcio's **assists and bonuses follow its own editorial rules**, so a third-party "assist"
won't always match the league's. → **Decision D1.**

## Needs

The gold data products each need feeds into are named in brackets.

| # | Need | Feeds |
|---|---|---|
| N1 | Player register: identity, club, role (P/D/C/A), club changes | `players`, `player_aliases`, everything |
| N2 | Fixtures and results, all competitions (Serie A, Coppa Italia, Supercoppa, UCL, UEL, UECL) | `fixtures`, `congestion`, `team_form` |
| N3 | Probable lineups, 2–3 independent views | `availability_consensus` |
| N4 | Official lineups, within minutes (fast path) | `official_lineups`, lineup-change events |
| N5 | Match events and minutes: goals, assists, cards, substitutions with minute, **goal minutes** (method §A4 needs team goals while each player is on the pitch), penalties taken and by whom, own goals, goals conceded, clean sheets | `match_player_stats`, `player_form`, `bench_impact` |
| N6 | Ratings (voti): the league's rater plus others | `rater_bias`, `player_form`, scoring |
| N7 | Performance stats: xG, xA, chances created, passes, saves | `rater_bias`, `bench_impact` |
| N8 | Injuries, suspensions, fitness | `availability_snapshots` |
| N9 | Penalty and set-piece takers | `set_piece_roles` |
| N10 | Coaches, club events, news and claims | `coach_tenures`, `club_events`, `news_claims` |
| N11 | Team-strength prior: now **derived from N14** (team xG fitted from match lines, method §A4); regressed team form is the fallback | `team_form` (regressed), keeper and fixture adjustments |
| N12 | Pundit opinion (FantaCreators) | `creator_consensus` |
| N13 | League data: rules, rosters, submitted lineups | League domain (Specs 2–3) |
| N14 | **Betting markets.** Match lines (1X2, over/under, both teams to score) to fit team xG and P(clean sheet); player markets (anytime scorer, assists, cards) to check P(scores) and price P(yellow) | Method §A4, §A6, §A8: `market_lines`, `player_market_props`, calibration against the market |

## Candidates per need

### N2, N4, N5, N7, N8: commercial football-data APIs

One licensed API can cover fixtures, official lineups, events, minutes, injuries and, as an add-on, xG.
The three realistic candidates:

| | **Sportmonks** | **API-Football** (api-sports.io) | **football-data.org** |
|---|---|---|---|
| Entry price | Starter **€29/month**: pick any 5 leagues, e.g. Serie A, Coppa Italia, UCL, UEL, UECL ([pricing](https://www.sportmonks.com/football-api/plans-pricing/)) | Free tier: **100 requests/day**, 10/min, all endpoints, according to its own [getting-started guide](https://www.api-football.com/news/post/how-to-get-started-with-api-football-the-complete-beginners-guide); paid from about $19/month (*to verify*) | Free: 12 competitions, fixtures and results only. **"Free + Deep Data" €29/month** adds lineups, substitutions, goals, bookings and squads; Coppa Italia, UEL and UECL need Standard at €49 ([pricing](https://www.football-data.org/pricing)) |
| Official lineups | Included in all plans, about 1 hour before kickoff ([docs](https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/premium-expected-lineups)) | Yes; timing *to verify* | Yes, on the Deep Data plan |
| Injuries / sidelined | Yes (*to verify for Serie A*) | Yes, an injuries endpoint (*to verify*) | No |
| Player match stats | Yes | Yes, including an algorithmic match rating (*to verify*) | Goals, bookings and substitutions only |
| xG | Add-on **€24/month** (xG and Pressure Index) | *To verify* | No |
| Predicted lineups | Add-on (FootballFeeds), €199/month, Growth plan or above | "Predictions" are match outcomes, not lineups | No |
| Terms | *To verify*: commercial use, caching, display | *To verify*: the pricing page returned 403 to our fetch | *To verify*; no terms on the pricing page |
| Free trial | 14 days | Free tier | Free tier |

Rough call budget for API-Football's free tier per round: fixtures and results about 5 requests, official
lineups polled every 5 minutes from 75 minutes before each kickoff about 150 (spread over 3–4 days), player
stats 10, injuries 4. That's about 170 per round across several days, which fits 100 per day *if the free
tier includes the current season* (*to verify*: some providers restrict free tiers to past seasons).

**Recommendation:** shortlist **Sportmonks** (one bill covers all five competitions, the xG add-on and
official lineups an hour ahead; about €53/month) and **API-Football** (cheapest, possibly free). Trial
both on rounds 8–9 before the ADR. football-data.org lacks injuries and xG. → **Decision D2.**

### N7: free xG sources

| Source | Status | Route |
|---|---|---|
| FBref | Lost Opta's advanced data in January 2026; only basic stats remain ([Awful Announcing](https://amp.awfulannouncing.com/soccer/sports-reference-pulls-advanced-data-agreement-violation-dispute.html)) | Basic stats only; terms *to verify* |
| Understat | Own xG model for Serie A, widely scraped from an internal endpoint; no published terms found | **Permission** (ask the site) |
| FotMob, Sofascore | Opta-based data, no public API | Assumed **Blocked** (*to verify*: their terms typically prohibit scraping) |

### N1: player register

| Source | Provides | Route |
|---|---|---|
| Licensed API (N2 choice) | Player IDs, names, clubs, positions, transfers | **Licensed** |
| Fantacalcio.it listone | Fantacalcio roles (P/D/C/A), quotazioni, FVM | **Permission** (D1) |
| Users | Their own squad with Fantacalcio roles, as shown in their league app | **User-supplied** |

Quotazioni and FVM serve auctions and market value, which are **out of scope for v1**, so we don't need
them. Roles are needed for formations: from users (their own squads) or from Fantacalcio.it with
permission. **Proposal:** the master player ID comes from the licensed API, not from the Fantacalcio list.
This changes the brief, which named the official list's `Id` as the master key. → **Decision D3.**

### N3: probable lineups

Every source is an editorial page: Fantacalcio.it, Gazzetta, Corriere dello Sport, Sky Sport, and
FantaMaster among others. None offers an API. The only licensed feed found is Sportmonks' Expected Lineups
add-on at €199/month.

| Option | Pros | Cons |
|---|---|---|
| A. Permission from 2–3 outlets | Matches the brief's design (disagreement as information) | Uncertain; takes time |
| B. Owner enters 2–3 views by hand, as human-judgement claims with provenance | Works now, through `import-csv` | Still reuses editorial content (D1 applies to Fantacalcio.it); doesn't scale |
| C. **Derive our own p_start** from objective data (recent starts and minutes, injuries, suspensions, congestion, coach changes), with editorial views as optional inputs where permitted | No licensing; fully automated; testable | A new model to build and calibrate; less informed on Friday-press-conference news |

**Recommendation:** C as the backbone, plus B for the owner's league in the meantime, while A is pursued.
→ **Decision D4.**

### N6: ratings (voti)

| Source | Provides | Route |
|---|---|---|
| Fantacalcio.it | Its own voti plus the "Roma" and "Torino" desks: the league's rater, and two more | **Permission** (D1) |
| Licensed API | An algorithmic per-match rating (Sportmonks / API-Football, *to verify*) | **Licensed**: a "statistical rater", useful as a bias baseline |
| Owner's league app | The league's own match-day scores (fantavoti) for the owner's players | **User-supplied**, but limited to rostered players |

Without Fantacalcio.it's voti we can't measure the league rater's bias (`rater_bias`) or calibrate expected
ratings (Spec 2). This is the strongest reason to ask for permission.

### N8: injuries, suspensions, fitness

| Source | Provides | Route |
|---|---|---|
| Licensed API | Injuries and sidelined lists | **Licensed** |
| Lega Serie A, Giudice Sportivo communiqués (weekly) | Official suspensions after each round | Public official documents; legaseriea.it terms *to verify* |
| Club injury reports and news | Fitness, expected return | Via N10 (news claims) |

### N9: penalty and set-piece takers

No source publishes pecking orders as data. **Derived:** infer takers from match events (who took each
penalty and free kick), plus **Manual** overrides for designated takers and backups (the Pessina/Cutrone
case in the brief).

### N10: coaches, club events, news

| Source | Provides | Route |
|---|---|---|
| Wikidata | Coaches with start and end dates, clubs, owners | **Open** (CC0); updates can lag by days |
| News articles (RSS feeds of Italian outlets) | Coach changes, injuries, tactics, rumours, "pupilli" | **TDM exception**, see below |
| Official club and league press releases | Coach appointments, ownership changes | Facts; per-site terms *to verify* |

**Text and data mining in Italy.** Art. 70-quater of the Italian copyright law (L. 633/1941, added by
d.lgs. 177/2021, implementing art. 4 of the EU DSM Directive) allows mining lawfully accessible works
**unless the rights holder has expressly reserved it**, and copies may be kept **only as long as the
mining needs them** ([analysis](https://www.agendadigitale.eu/mercati-digitali/text-e-data-mining-come-tutelare-il-database-dopo-la-direttiva-copyright/),
[example reservation](https://www.drivek.it/tdm/)). For news this means:

- check each outlet's machine-readable reservation (robots.txt, TDMRep, terms) before adding it;
- extract **claims** (facts, with link and source), never republish article text;
- **don't keep full article text in bronze indefinitely.** Store the URL, hash, claims and a short excerpt,
  and delete the text after extraction. This is an exception to "bronze keeps raw payloads", and the Spec 1
  design must reflect it.

Fantacalcio.it's terms prohibit "any processing of the data" contractually, whatever the TDM exception
allows, so their news is out until D1 is settled.

### N11: team-strength prior

| Source | Provides | Route |
|---|---|---|
| The Odds API | Serie A pre-match odds (1X2, totals); free 500 credits/month, paid from about $30/month (third-party reports) | **Licensed**; Serie A coverage and terms *to verify* |
| ClubElo (api.clubelo.com) | Daily Elo ratings as CSV | No published terms found; **Permission** (ask the author) |
| football-data.co.uk | Historical results and closing odds as CSV, free | Terms *to verify*; good for calibrating the regression prior |
| Licensed API odds add-on | Sportmonks Odds & Predictions €15/month; football-data.org Odds €15/month | **Licensed** |

**Recommendation:** odds-implied team strength (totals give expected goals) from the licensed API's odds
add-on or The Odds API's free tier, with football-data.co.uk history for calibration once its terms are
confirmed.

### N12: FantaCreators (YouTube)

Under YouTube's [Developer Policies](https://developers.google.com/youtube/terms/developer-policies):

- downloading or storing audiovisual content needs written approval, and **scraping is prohibited**;
- API data may be stored for at most **30 days** before it must be refreshed or deleted;
- API data may be aggregated **only across channels of the same content owner**;
- caption downloads through the API need rights on the video (a 403 `forbidden` otherwise, per the
  [errors reference](https://developers.google.com/youtube/v3/docs/errors)).

| Option | Route |
|---|---|
| Ask each chosen creator to share their ratings (many already publish sheets or posts) | **Permission** |
| The owner watches and records ratings and schierabilità by hand, pseudonymised | **Manual** |
| Transcripts via the API or scraping | **Blocked** |

The Serie A highlights channel adds little that N7 (xG, chances created) doesn't already give us as data.
**Proposal:** drop highlights as a source. → **Decision D5.**

### N13: league data

Rules, rosters and submitted lineups belong to the league and its users. **User-supplied:** users enter
them or upload an export from their league app. Fantacalcio.it's league-settings catalogue (the options to
enumerate for rules) is research for the League domain; reading it to design our config is fine, but
copying its content is not.

## Cost picture

| Stack | Monthly cost | Covers |
|---|---|---|
| Free-first | €0 + AWS | API-Football free tier (if current season), Wikidata, odds free tier, manual entry |
| Recommended paid | about **€53** + AWS | Sportmonks Starter (5 competitions) + xG add-on |
| Paid with odds | about €68 + AWS | The same, plus the Odds & Predictions add-on |

Any of these is a **paid service beyond the agreed AWS stack** and needs your approval (`tech.md`).

## Decisions for the owner

| # | Decision | Recommendation |
|---|---|---|
| D1 | Ask Fantacalcio S.r.l. for written authorisation to use voti, roles and probable lineups (or a data licence)? | **Yes.** Without it, the league's own rater and roles are off-limits. I can draft the request; you send it |
| D2 | Which licensed football API to trial? | Trial **Sportmonks** (14 days) and **API-Football** (free) on rounds 8–9, then an ADR |
| D3 | Master player ID from the licensed API instead of the Fantacalcio list? | **Yes**, with Fantacalcio roles attached from users or under D1 |
| D4 | Probable lineups: derive our own p_start, plus manual views, while seeking permission? | **Yes** (option C + B, pursue A) |
| D5 | Drop YouTube highlights; FantaCreators by permission or manual notes only? | **Yes** |
| D6 | News: an RSS-plus-TDM route, outlet by outlet, keeping claims but not article text? | **Yes**, after a per-outlet reservation check |

## Verification backlog (before each ADR)

- API-Football: terms, current-season access on the free tier, lineup timing, xG and injuries for Serie A.
- Sportmonks: terms (caching, showing data to our users), Serie A injury coverage, rating field.
- The Odds API: Serie A coverage and terms. ClubElo and football-data.co.uk: terms, or ask the authors.
- legaseriea.it terms for the Giudice Sportivo communiqués.
- Each news outlet's TDM reservation.
- Whether Fantacalcio.it's partner products (for example Fantacalcio-Online, which says it is rebuilding
  its objective ratings "together with Fantacalcio.it") point to a licensing channel.
