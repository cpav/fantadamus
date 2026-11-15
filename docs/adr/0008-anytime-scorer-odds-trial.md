# ADR-0008: Anytime-scorer odds as a check on the scoring chances, researched, with a one-round trial

- **Status:** Accepted by the owner, 2026-11-15 ("approve the trial", `mvp-sources` task 8.2): the trial, not a route.
  Its first step waits for the owner's API key: only the owner can create the account
- **Deciders:** the owner
- **Specs affected:** `mvp-sources` (research only: no code collects these odds, R6.1)

## Context

Method §A4 prices a player's chance of scoring from his team's expected goals, fitted from the match odds, and his
share of them. The anytime-scorer odds are the market's own view of that chance. The method uses them as a **check**: a
large gap between our chance and the market's is investigated, never averaged into the number. Today Fantadamus has no
source for them. `mvp-sources` R6 asks what checking against the market would take: each route's Serie A coverage, its
cost, its terms and how the method would use it, with a one-round trial for the owner to approve. This ADR is that
research. It decides nothing about collection beyond the trial.

## Options

| Option | Serie A coverage | Cost | Terms | Against |
|---|---|---|---|---|
| A. **The Odds API**, market `player_goal_scorer_anytime` | Listed for Serie A among the soccer player props (with the EPL, Ligue 1, the Bundesliga, La Liga and MLS); "coverage is currently limited to US bookmakers", so how many Serie A matches get a price is unknown until tried | One credit per market, per region, per match: 10 to 20 credits a round, of the free plan's 500 a month | Storing the data and deriving values from it are allowed; reselling it as a feed is not; attribution appreciated, not required | An account and an API key in the owner's name; approved for v1 only (registry D-S4, D-S6); US books may price few Serie A players |
| B. **Betting-news pages** on the reading list | Previews pick a few players a round ("pronostici marcatori"), often as combined bets; no page found lists every player's anytime price | Free | Each site's terms, as for the match odds | Partial and irregular: a check needs the price of every likely starter, not a handful of tips |
| C. **Other feeds** found (SportsGameOdds, TheStatsAPI) | Anytime-goalscorer markets listed for European leagues | Paid plans | Not read | A new paid service, which needs the owner's approval before any trial; nothing suggests they beat A for a first look |
| D. **The bookmakers' own sites** | Every player, every match | Free to read | Bookmakers' terms forbid automated collection | Ruled out, as Sky and Goal were |

## Decision

**A one-round trial of option A**, approved by the owner on 2026-11-15; no collection code is written before it.

The trial, by hand from Claude Code on `main`, for one round:

1. **Coverage first, at no cost.** List the sports, which uses no credits, and confirm Serie A's key. Then, for one match
   of the round, ask the event's odds for `player_goal_scorer_anytime` in the `us` region (one credit). If no bookmaker
   prices it, the trial stops there and the answer is "not yet".
2. **The round.** For each of the round's ten matches, the same request (ten credits, or twenty with a second region):
   each listed player's anytime price, its bookmaker and its time.
3. **The market's chance.** De-margined as the method's match odds are: where a book prices "No" as well, the pair's
   overround is removed; where it prices only "Yes", the match's 1X2 overround from the same book stands in.
4. **The check, not the number.** For every likely starter, our chance of scoring beside the market's. A gap of more than
   a third of the market's chance, or ten points, whichever is larger *(start)*, is a flag to read, never averaged.
5. **After the round.** Each side's Brier score on who scored, from the statistics reads, with the flags read one by one.
   The trial report says whether the market saw something our model doesn't, and how often.

The API key goes in private configuration (`FANTADAMUS_PRIVATE_CONFIG`), never the repository. The trial's prices stay in
`data/private/`. If the trial pays off, a later spec builds the route on The Odds API's free plan; moving to a paid plan
would need the owner's approval.

## Consequences

- **Easier:** a measured answer to whether the market's scoring chances are worth a route, for at most 20 of 500 free
  credits, before any code.
- **Harder:** the owner creates an account and an API key (only the owner can), and keeps it private. US bookmakers may
  not price Serie A players, in which case the trial stops after one credit and option B's partial tips are not worth a
  reader.
- **Not done:** no reader, contract or schedule for these odds; R6.1 holds.

## Sources

- [The Odds API, betting markets](https://the-odds-api.com/sports-odds-data/betting-markets.html): the soccer player-prop
  markets, `player_goal_scorer_anytime`, the leagues listed, and "coverage is currently limited to US bookmakers"
- [The Odds API, documentation v4](https://the-odds-api.com/liveapi/guides/v4/): the event-odds endpoint, regions, and the
  usage cost of one credit per market per region
- [The Odds API, plans](https://the-odds-api.com/): the free plan's 500 credits a month and the paid plans
- [The Odds API, terms and conditions](https://the-odds-api.com/terms-and-conditions.html) (last updated 31 August 2026):
  storing and deriving values allowed, no resale or redistribution as a feed
- [Sisal, pronostici marcatori Serie A](https://www.sisal.it/scommesse-matchpoint/blog/voci-di-spogliatoio/pronostici-marcatori-oggi-serie-a):
  an example of betting-news previews, a few tips a round
- [SportsGameOdds, soccer odds API](https://sportsgameodds.com/sports/soccer-odds-api): another feed listing
  anytime-goalscorer markets, paid
- `docs/method.md` §A4: the market's scoring chance as a check, never averaged
- `docs/source-registry.md`, D-S4 and D-S6: The Odds API's free plan, approved on 2026-10-24 for v1, player markets
  included; its "Still to check" list names this trial: how many of the 10 matches get `player_goal_scorer_anytime`
