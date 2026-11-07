# Calibration report: round 10

2026-11-07 · `mvp-lineup` task 9.3 · Aggregates only: no player's figures

Round 10 is the first real round Fantadamus has scored, so this is the report Phase 2's gate asks for. It's a small
first look: only the chance of starting could be scored, and the reading below has one large caveat.

## What was scored

Fantadamus scored the round on 2026-11-06, from the finished round's page, which marks who really started.

### The model on everyone

Every player on the round's page, with official lineups left out. **Chance of starting: Brier 0.117 over 527 players,
against 0.243 for always guessing the average.** Lower is better.

| Said | Average said | Happened | Players |
|---|---:|---:|---:|
| 0% to 10% | 1.1% | 2.6% | 116 |
| 10% to 20% | 16.9% | 2.8% | 36 |
| 20% to 30% | 24.8% | 3.8% | 52 |
| 30% to 40% | 32.6% | 24.5% | 53 |
| 40% to 50% | 44.2% | 46.3% | 41 |
| 50% to 60% | 55.2% | 64.0% | 25 |
| 60% to 70% | 64.6% | 34.8% | 23 |
| 70% to 80% | 74.5% | 72.4% | 29 |
| 80% to 90% | 85.7% | 80.9% | 47 |
| 90% to 100% | 90.8% | 92.4% | 105 |

### What users were told

Chance of starting: Brier 0.005, but over 2 players, which is too few to mean anything. Overrides: none.

## What couldn't be scored

| What | Why | Count |
|---|---|---:|
| Getting a rating, scoring and clean sheets | No facts held before the kickoffs, because Fantadamus wasn't yet reading before this round | 535 |
| Everything about a player | On the round's page but not on the statistics page | 16 |
| Starting | His club's lineup doesn't name every starter | 11 |
| Getting a rating, from the users' set | Logged before that chance was | 2 |
| Getting a rating, from the model's set | No statistics read before the round | 3 |
| Scoring if he started, in each set | No statistics read before the round | 1 each |

So **only the chance of starting has been scored on real data so far**.

## The two open questions

- **Was 12 hours long enough for the statistics page?** Not answered. Round 10 was scored days after it finished.
- **Does a finished page keep the outlets' last percentages?** Not answered, because nothing was read before round 10's
  kickoffs to compare it with.

**The second one is the caveat.** Round 10's chances come from the finished page. If that page changes its percentages once
the lineups are known, the table above looks better than the forecasts really were. Round 11 was read before its kickoffs,
so it can answer both questions.

## Starting values

**No change proposed.** One round and one kind of chance isn't enough, and the caveat above applies. Two things to look at
in the recalibration slice:

- **10% to 30% looks overstated:** 88 players averaged about 22%, and about 3% of them started.
- **60% to 70% looks odd:** it's lower than the band below it, on only 23 players.

## What the owner's playbook adds

The owner's private playbook logs forecasts and results from the same method, worked out in a chat before Fantadamus could
do it. It isn't Fantadamus's code, so it doesn't score this software, but it does cover what round 10 can't. Both samples
are small.

- **Round totals, five rounds with a forecast:** the first threshold was reached in 4 of 5, against about 84% forecast. The
  forecast's average miss was about 1 point too high: four rounds within 4 points and one about 10 below. The misses
  spread by about 5 points, near the simulation's own spread of about 6.
- **Chances of scoring, 19 forecasts over two rounds:** 3.9 goalscorers expected and 6 happened, which is within the noise
  of about 1.7. Brier 0.224, against 0.216 for always guessing the average. So on this sample there's no sign of bias, and
  no sign of skill either.

## For the recalibration slice

Reading the playbook beside this season's figures turned up two things to settle first:

- **The penalty term looks too generous.** The model assumes a penalty in 15% of team-matches, scored 78% of the time. This
  season so far: 22 in 200 team-matches (11%), 14 scored (64%). The −3 for a miss is stored in each league's rules, but the
  model doesn't price it. On this season's figures a first taker's term is worth about a quarter of what the model gives.
  22 penalties is a small sample, so this needs shrinking, not copying. In a replay of round 11, it was enough to change
  one starter.
- **How an outlet's silence counts.** An outlet that doesn't list a player counts as about 5% to start, while the round page's
  own average leaves that outlet out. On one page, the two can differ by more than 10 points. Round 11 can show which is
  closer to what happens.

## Round 11

The owner decided not to wait for round 11 to close this slice (2026-11-07). The gate is met without it. It scores itself at
the first question or `fantadamus collect --due` from about 12 hours after its last kickoff, and it should be run before round
12 starts, because the statistics read after a round has to come before the next round's ratings. Its report feeds the
recalibration slice.
