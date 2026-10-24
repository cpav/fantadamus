# Fantacalcio advisor: the decision method

Status: **the owner's method, 2026-10-24.** The `decision-engine` spec implements it, and its acceptance
tests come from §A9. Numbers marked *(start)* are starting values, calibrated from the logged predictions
(§A8). The chat agent's system prompt (Part B of the same brief) is in [agent-prompt.md](agent-prompt.md).

## A1. What we optimise

The user's league rules decide everything: bonuses and maluses (per role, if the league sets them that way),
goal thresholds, substitutions, bench size, allowed formations and modifiers. Never hardcode a league.

The target is the expected number of fantasy goals: the score converted through the league's thresholds.
Report the expected score and the chance of reaching each threshold alongside it.

## A2. Three outcomes for every player

| Outcome | Probability | What it's worth |
|---|---|---|
| Starts | p_start | E_start |
| Comes on and gets a rating | p_cameo | E_cameo, and it **blocks** his substitute |
| No rating | 1 − p_start − p_cameo | nothing: the first bench player in his role with a rating replaces him |

Availability: an official lineup overrides everything. Otherwise use the consensus of the probable-lineup
sources, and keep their disagreement as uncertainty rather than averaging it away.

## A3. The ordering rule

```
key = (p_start × E_start + p_cameo × E_cameo) / (p_start + p_cameo)
```

- Sort each role by the key. The eleven is the top of each role; the bench is the rest, in the same order.
- The chance of no rating does **not** enter the key, because the bench covers it. A doubtful high scorer
  ahead of a certain lower scorer is a free option, unless he only comes on late. That's why E_cameo
  matters.
- The rule breaks only when the bench can't cover: no bench player left in that role, or the substitution
  cap reached. The simulation (§A7) handles both.

## A4. Expected score if he starts

```
E_start = expected vote + bonus_goal × E[goals] + bonus_assist × E[assists] − malus_yellow × P(yellow)
```

Price the bonus separately from the vote. Never shrink a single average fantavoto, or a striker's scoring
run gets averaged away.

**Expected vote.** A role baseline of 6.0 shrunk toward his season average:
`6.0 + n/(n + k_vote) × (MV − 6.0)`, with k_vote ≈ 10 *(start)*. Fixture effect:
`+ 0.3 × (P(win) − P(loss))` from the 1X2 line *(start)*. The vote moves only about ±0.15 with the result;
win probability predicts clean sheets, not bonuses.

**Expected goals and assists.**

```
E[goals]   = team xG × goal share × minutes share   (+ penalty term for the designated taker)
E[assists] = team xG × assist share × minutes share
P(scores)  = 1 − e^(−E[goals])
```

- **Team xG** for the fixture is fitted from the betting lines (1X2, over/under 2.5, both teams to score)
  with a Poisson model and a Dixon-Coles low-score correction. Without lines, use regressed team form
  (§A5).
- **Goal share** is his share of the team's goals while he's on the pitch, shrunk toward a role prior:
  `(prior × W + his goals) / (W + team goals in his games)`. Use xG share instead of goals when it's
  available; it settles much faster.
  - Goal-share priors *(start)*: centre-forward 0.30, second striker 0.20, attacking midfielder or wide
    forward 0.15, central midfielder 0.06, wing-back 0.04, full-back 0.03, aerial centre-back 0.05.
  - Assist-share priors *(start)*: attackers 0.10–0.12, midfielders and wing-backs 0.08, other defenders
    0.02–0.06.
  - Prior weight W: 15 team goals for attackers and midfielders, 25 for defenders *(start)*.
- **Minutes share** if he starts: about 0.85 for forwards, 0.80 for attacking midfielders, 0.95 for
  defenders *(start)*. Use the player's own minutes once there's enough data.
- **Penalties**, for the designated taker only: P(team gets a penalty) ≈ 0.15 per match × conversion ≈ 0.78
  × his minutes share *(start)*.
- **Check against the market.** Compare P(scores) with de-margined anytime-scorer odds where a permitted
  source exists. A large gap is a flag to investigate, not something to average.

**Cameo value.**
- Defenders and holding midfielders: about 5.5 *(start)*.
- Attackers need a priced cameo. Their chance of scoring in about 25 minutes uses the same formula with
  minutes share ≈ 0.28. A cameo with a goal is worth about 9.8. Without a goal he gets a rating about 60%
  of the time, worth about 5.75 *(start)*.
- Replace these with the player's own substitute record (`bench_impact`) once there's enough of it.

## A5. Shrink and regress everything

- **Player form:** weight n/(n + k) toward the role prior. Small samples are mostly noise.
- **Team form:** regress attack and defence the same way, with weight ≈ n/(n + 12) *(start)*. The betting
  lines are the best prior. Five games of team goals are as noisy as five games of a player's.

## A6. Keepers

```
E = expected vote + clean-sheet bonus × P(clean sheet) − malus per goal × expected goals conceded
```

- Price the opponent's attack from the lines, not the venue. Take P(clean sheet) from the same fit.
- **Read the vote net of goals conceded.** Skill = MV + β × goals conceded per game, shrunk with k ≈ 9.
  Expected vote = skill − β × expected goals conceded, with β ≈ 0.35 *(start)*. Otherwise a season average
  mixes the keeper with his defence.
- A backup keeper from the same club plays exactly when the starter doesn't. Put him first on the bench and
  the slot is covered.

## A7. Formation, simulation and timing

- **The formation falls out of the sort.** Compare the marginal players: the 4th defender, the 4th
  midfielder and the 3rd forward.
- **Simulate every allowed formation** with the league's real substitution rules (role for role, first
  bench player with a rating, the cap), goals and assists drawn as Poisson, noise on the vote, and the
  league's thresholds. Report the expected score, expected fantasy goals, and the chance of reaching each
  threshold.
- **Model same-match links.** A keeper's goals conceded include the opposing striker's goals. Links like
  this don't change expectations, but they do change the spread.
- **Close calls.** When options are within about 0.15, call it a coin flip and let the user's situation
  decide: variance helps an underdog.
- **Information timing.** Players in the deadline match have official lineups before the lock. Prefer them
  for doubtful slots, and recheck about 45 minutes before the lock. Information older than 24 hours before
  the deadline is stale.

## A8. Context, overrides and calibration

- **Context** (coach changes, dressing-room rows, rumours, tactical shifts) mostly widens the uncertainty
  on who plays. Any shift in the expected score must be bounded, logged and shown. Midweek European
  fixtures are the most reliable sign of rotation.
- **Overrides.** When a user goes against the advice, show the cost once, in points and in probability, and
  then help with their choice.
- **Audit decisions, not results.** Log every published probability (p_start, P(scores), P(clean sheet))
  with its as-of time. After each round, score them (Brier score, reliability by probability bucket) next
  to the market's numbers and the users' overrides, and recalibrate the *(start)* constants.

## A9. Tests, from real decisions in 2026/27

1. A brute force over every ordering of random squads shows that sorting by the key is optimal in 100% of
   cases.
2. With a flat 5.5 cameo, attackers at (p_start 0.55, p_cameo 0.35, E 7.2) and (0.90, 0.05, 6.6) tie at
   6.54. Ranking by p_start × E + p_cameo × 5.5 (5.88 vs 6.21) is rejected.
3. Two keepers come out within about 0.1 on regressed team form, where raw five-game form gave one of them
   +0.9.
4. A centre-forward with 4 goals in 5 starts, team xG 1.35 and 88% to start is about 32% to score. A
   rotation striker at 25% to start with team xG 1.1 is about 10%. The first ranks ahead for the last
   forward place.
5. A striker's goal against your own keeper still nets about +2.5, or about +1.5 if it breaks the clean
   sheet. The link narrows the spread and raises the chance of reaching the first threshold.
6. In an "X or Y?" where X is ahead if he plays but only about 55% to get a rating, the answer is "start X,
   Y first on the bench". It changes if there's no bench cover.
