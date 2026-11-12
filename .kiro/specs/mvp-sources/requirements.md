# Requirements Document: `mvp-sources` (Phase 2, eighth slice)

Status: **Draft for the owner's approval, 2026-11-12** · Workflow: requirements-first · Depends on: `mvp-recalibrate`
(signed off 2026-11-12) · Abbreviation: `so` · Method: [`docs/method.md`](../../../docs/method.md) §A2, §A4, §A8 ·
Sources: [`docs/source-registry.md`](../../../docs/source-registry.md)

## Introduction

The owner put four things in this slice (2026-11-11): the other competitions' fixtures and the rest days they leave,
injury detail, per-match ratings and the raters' bias, and research into anytime-scorer odds. Match news for the cards
and set-piece takers wait for v1.

Every new route is researched first and approved by the owner in an ADR before any code depends on it (the research
gate, `quality.md`). The research started on 2026-11-12; what it found is below. It found no new site to add: every
page is on one the owner has already approved.

**Not in this spec:**

- match news and context on the cards, and set-piece takers (v1);
- collecting anytime-scorer odds: this slice researches the route only;
- changing a number from the new facts: they're shown and kept as evidence, and a later recalibration proposes;
- any paid service or new account;
- trades, auctions and market values (out of scope for v1).

## Glossary

| Term | Meaning |
|---|---|
| Other competitions | The Champions League, Europa League, Conference League and Coppa Italia |
| Rest days | Days since a club's previous match in any competition, and to its next |
| European week | A Serie A match within three days of the club's match in a European competition, before or after |
| Diffidato | A player one booking from a ban |
| Base rating | A rater's vote before bonus and malus (voto puro) |
| Desk | One of the raters a page shows: Fantacalcio.it (the league's), Roma and Torino |
| Rater bias | How far a desk rates a player above or below the other desks, over the same matches |
| Pupillo | A rater's favourite (`product.md`'s glossary): here, a player a desk rates above the others over enough matches |

## What the research found

Read on 2026-11-12, one request per page, from Claude Code; nothing fetched is kept in the repository.

| Fact | Candidate | What it gives | Route |
|---|---|---|---|
| Other competitions' fixtures | Wikipedia's [2026–27 Champions League league phase](https://en.wikipedia.org/wiki/2026%E2%80%9327_UEFA_Champions_League_league_phase) and [Europa League league phase](https://en.wikipedia.org/wiki/2026%E2%80%9327_UEFA_Europa_League_league_phase) pages, and the Conference League's and Coppa Italia's | Every match by matchday, played and to come, with its full date and kickoff in each match's report block; the Italian clubs named | Wikipedia is on the reading list (CC BY-SA, read with an identifying agent); Fantadamus reading it itself would be new |
| Injury and suspension detail | Fantacalcio.it's injured, unavailable and suspended-and-diffidati pages | Why a player is out, when he's expected back, bans, and who's one booking from one | On the reading list for Claude (need N8), served in the HTML (checked 2026-10-24); Fantacalcio.it's terms risk accepted for the MVP |
| Per-match ratings, three desks | Fantacalcio-Online's round ratings page, `/it/serie-a/2026-2027/voti/{n}-giornata` | Each player's base rating from Fantacalcio.it, Roma and Torino, and when he came off or on, for every match of the round. Served in the HTML: the registry's 2026-10-24 note said the ratings loaded in JavaScript | Fantacalcio-Online is approved: its robots.txt welcomes AI crawlers, and its terms allow personal use with attribution |
| The league's rating, without a new page | The two statistics reads around a round, as the review reads them (`mvp-review`) | Each player's rating in the round, exactly, up to about 24 rated games | Already read |
| Anytime-scorer odds | [The Odds API](https://the-odds-api.com/sports-odds-data/betting-markets.html): `player_goal_scorer_anytime` among its soccer player markets, Serie A included | US bookmakers only; one request per match, one credit per market per region: about 20 of the free plan's 500 credits a round | Approved for v1 (registry D-S6); in the MVP it needs an account and a key in the owner's name |

## Requirements

### Requirement 1: Routes first

**User Story:** As the owner, I want every new page approved before Fantadamus reads it.

- **R1.1** Before any code reads a new page, its route SHALL be recorded in the source registry and an ADR: the page, its
  robots.txt and terms as read, whether its data is in the HTML, its cadence and its fallback. The owner approves it.
- **R1.2** Fantadamus SHALL read each new page with its polite fetcher, under ADR-0004's and ADR-0006's rules, with
  Claude as the fallback through `read_page`. Each new page SHALL have a switch that turns it off.

### Requirement 2: The other competitions and rest days

**User Story:** As a player, I want to know whose clubs played midweek before I pick them.

- **R2.1** THE SYSTEM SHALL keep every Serie A club's matches in the other competitions it plays: the date and kickoff,
  the opponent and the competition.
- **R2.2** FOR each Serie A match THE SYSTEM SHALL give each side's rest days since its previous match in any
  competition and to its next one, and say when either is a European match.
- **R2.3** The match card and the player outlook SHALL show them as context, where `docs/answer-formats.md` keeps their
  place ("Inter played Wednesday in the Champions League"), with the source at the bottom.

### Requirement 3: Injury and suspension detail

**User Story:** As a player, I want to know why a player is out and for how long.

- **R3.1** THE SYSTEM SHALL keep, for each player the injury and suspension pages list: the reason (an injury and its
  kind where given, illness, a ban, other), his expected return or the matches banned where given, and whether he's one
  booking from a ban.
- **R3.2** The card, the outlook and the lineup's out-and-doubtful list SHALL show the detail of a player who's out or
  doubtful ("out: thigh injury, back in about two weeks"; "banned, one match"), and mark a player one booking from a ban.
- **R3.3** The detail SHALL NOT add a view to the chance of starting: the outlets already price who's out. A player the
  pages list as out while an outlet lists him as a starter SHALL be shown as a disagreement.

### Requirement 4: Per-match ratings

**User Story:** As the owner, I want each round's ratings kept as evidence for the rating constants.

- **R4.1** FOR each scored round THE SYSTEM SHALL keep each player's base rating from the league's rater: recovered from
  the statistics reads around the round where they recover it exactly, otherwise from the ratings page. It's kept in the
  round's calibration set.
- **R4.2** THE SYSTEM SHALL also keep the Roma and Torino desks' base ratings from the ratings page, for R5.
- **R4.3** `fantadamus recalibrate` SHALL count the kept ratings as the evidence for the rating constants that wait, and
  say how much there is against what each needs. Fitting them is a later recalibration's.

### Requirement 5: Rater bias

**User Story:** As a player, I want to know when a rater favours a player.

- **R5.1** FOR each player THE SYSTEM SHALL measure each desk's bias against the other desks' ratings of the same
  matches, with its sample and a 90% interval.
- **R5.2** A desk's bias above a threshold, set in the design, over at least a minimum number of matches SHALL be shown
  as a claim on the outlook and the card ("Fantacalcio.it rates him 0.3 above the other desks, over 9 matches").
- **R5.3** The league's rater's bias is already inside a player's average rating: it SHALL NOT move his expected vote.

### Requirement 6: Anytime-scorer odds, researched

**User Story:** As the owner, I want to know what checking the scoring chances against the market would take.

- **R6.1** THE SYSTEM SHALL NOT collect anytime-scorer odds in this slice.
- **R6.2** An ADR SHALL compare the routes: The Odds API's player markets, betting-news pages and any other found. For
  each it gives its Serie A coverage, its cost in credits or money, its terms, and how the method would use it (§A4: a
  large gap between our chance of scoring and the market's is a flag, never averaged). It ends with a one-round trial
  plan for the owner to approve or turn down.

### Requirement 7: Freshness, cost and budgets

**User Story:** As a player, I want the new facts fresh without slower answers.

- **R7.1** Each new fact SHALL have a freshness target and a cadence: the other competitions' fixtures weekly and on match
  days; injuries and bans daily, twice a day in the last 48 hours before a round; ratings the morning after each round.
- **R7.2** THE SYSTEM SHALL add no paid service and no account. Every answer SHALL stay within its budget: a card within
  3 seconds and 15 KB, the outlook and the lineup as before, and the agent prompt within 13,000 characters.

### Requirement 8: The docs

**User Story:** As the owner, I want the docs to say where each new fact comes from.

- **R8.1** THE SYSTEM SHALL update the source registry and the reading list, `docs/answer-formats.md` for rest days,
  injury detail and raters' claims, method §A8, and the player guide.

## Acceptance tests

| Test | What it proves | Requirements |
|---|---|---|
| AT-1 | Manual: the owner approves the routes' ADR | R1 |
| AT-2 | The other competitions' fixtures from an invented page; rest days and European weeks for each side, by hand; shown on a card and an outlook | R2 |
| AT-3 | Injury and ban detail from invented pages; shown on a card, an outlook and a lineup; a disagreement shown; no chance moves | R3 |
| AT-4 | A round's base ratings recovered from two reads, by hand, and from the ratings page where the reads don't bracket the round; kept in the set; counted as evidence | R4 |
| AT-5 | Rater bias by hand on invented ratings, with its sample; a claim shown; the expected vote unchanged | R5 |
| AT-6 | Manual: the owner reads the anytime-scorer ADR, with each route's coverage, cost and terms | R6 |
| AT-7 | A card and an outlook within their budgets with the new facts; no paid service | R7 |
| AT-8 | Manual, from Claude Code on a real round: the new pages read, a card with rest days and injury detail, the round's ratings kept | R1 to R5 |

## Review of these requirements

An Analyze-Requirements pass, before design.

- **Double counting.** The outlets' lineups already price rotation, injuries and bans. Shown as context, the new facts
  can't count twice (R3.3); moving a number from them would need evidence that the outlets underprice them, which a later
  recalibration can look for in the calibration sets.
- **European weeks are few.** Seven Serie A clubs play in Europe this season, between September and January. Measuring a
  rotation effect beyond what the outlets price will take many rounds.
- **Rest days need every competition.** Coppa Italia rounds fall midweek too, so its page is read alongside the European
  ones.
- **Ratings from two reads need reads around each round.** Nothing has been collected since 9 November, so the ratings
  page is the fallback, and it serves this season's earlier rounds too. Those rounds help the raters' comparison, not the
  model's calibration: the calibration sets start at round 10.
- **Base ratings and the league's score.** The ratings page gives base ratings; the league scores the rating plus bonus
  and malus, which the statistics reads already give.
- **A desk's bias against the others, not against performance.** `product.md` asks for each rater's bias against
  performance statistics. Against the other desks is what the pages allow now; against performance needs per-match
  events, which wait for v1's licensed API.
- **Name matching.** The ratings page writes names as Fantacalcio-Online's round page does, so the same resolution
  applies.
- **Terms.** No new site: Fantacalcio-Online with attribution, Fantacalcio.it under the accepted risk, Wikipedia under
  CC BY-SA with attribution.
- **The prompt's budget.** The agent prompt is at 12,911 of 13,000 characters. New rendering rules go into the tools'
  descriptions, as the cards' did.

## Owner decisions

1. **The routes.** Recommendation: Fantadamus reads the new pages itself, under ADR-0006's rules, with Claude as the
   fallback. They are Wikipedia's European competition pages and Coppa Italia page, Fantacalcio.it's injury, unavailable
   and suspension pages, and Fantacalcio-Online's round ratings page, recorded in ADR-0007. No new site and no account.
   The alternative is API-Football's free tier now (every competition's fixtures and injuries in one licensed API), which
   needs an account and a key in the owner's name and is approved for v1.
2. **Context changes no number in this slice.** Recommendation: rest days and injury detail are shown and kept in the
   calibration sets, and a later recalibration can propose an adjustment once the evidence is enough. The alternative is
   a bounded rotation adjustment for European weeks now, as method §A8 allows if it's bounded, logged and shown. But the
   outlets already price rotation, and there's no evidence yet that they underprice it.
3. **Anytime-scorer odds.** Recommendation: the research ADR only in this slice, and a one-round trial with a free Odds API
   key in the owner's name later, if the ADR is approved. The alternative is opening the account now and running the
   trial in this slice.
