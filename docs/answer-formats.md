# Answer formats

Status: **proposed 2026-10-31**, from the owner's examples (2026-10-30) and the "weather app" vision, for the
owner's review. This page is the shape every answer takes. Each slice builds the formats it needs, and the agent
prompt ([`agent-prompt.md`](agent-prompt.md)) tells Claude how to render them. The samples are illustrative:
the players and numbers are made up; only the shape is real.

## The forecast frame: every answer

An answer reads like a good weather forecast: a chance, why, how sure, how it has moved, how fresh. The numbers
keep moving until the deadline, and, once live forecasts exist, until somebody scores.

1. **One context line first:** the round, when it locks and at which match, and how fresh the facts are.
   `Round 11 · locks Fri 6 Nov 20:45 at Venezia–Udinese · updated 12 minutes ago`
2. **The headline:** the decision in one line, with its margin and a plain label: *coin flip* (under about 0.15
   points), *lean* (0.15 to 0.5) or *clear* (over 0.5).
3. **Why, in one line**, then the few numbers that carry it.
4. **How sure:** each chance carries its confidence: *official*, *agree* (how many sources), *disputed* (how far
   apart) or *one source*.
5. **How it moved:** since the user's last question, or the last 24 hours. "Up from 60% yesterday: Gazzetta now
   has him starting." When nothing moved, say "unchanged since Wednesday".
6. **What would flip it, and what to check before the lock**, in a line each.
7. **Sources at the bottom**, by name, once each.

Rules for all of them:

- Only the tools' numbers, rounded the way people say them (47%, about 1.3, about 6.7).
- Say what's missing and what was assumed; never invent a chance.
- Keep it short, and end by offering the breakdown.
- Context (a new coach, a rumour) widens the uncertainty more than it moves the number, and is shown when used.

## 1. "X or Y?"

Built in `mvp-x-or-y` and `mvp-collect`, for forwards. The next slice extends it to every role.

```text
Round 11 · locks Fri 6 Nov 20:45 at Venezia–Udinese · updated 12 minutes ago

Start Rossi, put Bianchi first on the bench: lean, 0.4 points.

Inter–Como: Inter 58% to win, Como 19%; Inter expected to score about 1.9, Como about 0.9.

Rossi (Inter, centre-forward): starts and takes the penalties
  • Starts 92%: four outlets agree; Bianchi, his rival, is at 35%. Penalties: 3 scored from 3.
  • 45% to score if he starts; worth about 8.1 points.
  • Form: 5 goals, 2 assists in 9; average rating 6.8. Up from 85% on Wednesday: Sky now has him starting.

Bianchi (Genoa, forward): likely starter in a harder match
  • Starts 80%: disputed, outlets between 55% and 95%.
  • 31% to score if he starts; worth about 7.6, less if he only comes on late.
  • Form: 3 goals in 9; average rating 6.4. Unchanged since Wednesday.

Would flip it: Rossi on the bench in the official lineup (about 17:00 Sunday).
Before the lock: neither plays in the deadline match.

Sources: Fantacalcio-Online, round 11 probable lineups · Fantacalcio.it, table · Fantacalcio.it, penalty takers
```

## 2. The full lineup

Next slices (every role, then the full lineup). It needs the user's squad and the league's full rules: allowed
formations, bench and substitution rules, and the scoring thresholds.

```text
Round 11 · locks Fri 6 Nov 20:45 at Venezia–Udinese · updated 12 minutes ago

3-4-3 · expected about 73 points (66 to 80 in eight rounds out of ten)
Chance of reaching 66: 79% · 72: 55% · 78: 29%

Keeper    Ferrari (Napoli v Lazio)        starts 99% official · 6.3 · 34% clean sheet
Defence   Esposito (Inter v Como)         starts 92% agree (4) · 6.6
          Romano (Roma v Sassuolo)        starts 88% agree (4) · 6.4
          Ricci (Milan at Genoa)          starts 85% agree (3) · 6.2
Midfield  Marino (Atalanta at Monza)      starts 95% agree (4) · 7.0 · takes the free kicks
          Greco (Inter v Como)            starts 90% agree (4) · 6.7
          Bruno (Juventus at Fiorentina)  starts 75% disputed (55–90%) · 6.5
          Gallo (Bologna at Parma)        starts 89% agree (4) · 6.4
Attack    Rossi (Inter v Como)            starts 92% agree (4) · 8.1 · 45% to score · penalties
          Bianchi (Genoa v Milan)         starts 80% disputed (55–95%) · 7.6 · 31% to score
          Conti (Lazio at Napoli)         starts 87% agree (4) · 7.4 · 36% to score

Bench, in order
  Keeper    Moretti: plays exactly when Ferrari doesn't, so the slot is covered
  Defence   1. Fontana (6.1)  2. Caruso (5.9)
  Midfield  1. Mancini (6.3)  2. Rizzo (6.0)
  Attack    1. De Luca (7.2): first in if any forward misses out  2. Lombardi (6.8)

The calls
  Formation: your 3rd forward (Conti 7.4) beats a 4th defender (Fontana 6.1) and a 5th midfielder (Mancini 6.3),
  so 3-4-3 is clear.
  3rd forward: Conti 7.4 v De Luca 7.2: lean Conti, though Lazio at Napoli is the harder match; De Luca is first
  off the bench, so Bianchi's disputed place is covered.

Out and doubtful
  Out: Costa (injured until 29 January)
  Doubtful: Bruno 75%, disputed: Juventus play Sunday 20:45, after the lock, so the bench covers him.

Most likely to score: Rossi 45% · Conti 36% · Bianchi 31% · Marino 18% · Esposito 9%

Since your last lineup (Wednesday): Bruno 85% → 75% (Gazzetta now has a ballottaggio); expected 74 → 73.

Before the lock: no player of yours is in Venezia–Udinese, so this lineup is final unless news breaks.

Sources: Fantacalcio-Online, round 11 probable lineups · Fantacalcio.it, table · Fantacalcio.it, penalty takers ·
Fantacalcio.it profiles (11)
```

## 3. The formation call

Part of the full-lineup slice: the formation falls out of the ranking, by comparing the marginal players.

```text
Round 11 · locks Fri 6 Nov 20:45 · updated 12 minutes ago

Stay with 3-4-3: clear, about 1.1 points over 3-5-2.

Your 3rd forward (Conti, 7.4) is worth clearly more than a 4th defender (Fontana, 6.1) or a 5th midfielder
(Mancini, 6.3).
3-4-3: about 73 · 55% to reach 72     3-5-2: about 71.9 · 49%     4-4-2: about 71.7 · 47%
Would flip it: Conti on the bench in the official lineup; then De Luca comes in, still 3-4-3.
```

## 4. One player: "Will he start? Is he worth it?"

Every-role slice: one player's outlook, and the start of every other answer.

```text
Round 11 · Inter–Como, Sun 8 Nov 18:00 · updated 12 minutes ago

Rossi starts 92%: four outlets agree. Bianchi, his rival, is at 35%.
45% to score if he starts; worth about 8.1 points; takes the penalties (3 from 3).
Up from 85% on Wednesday: Sky now has him starting.
Official lineup: about 17:00 Sunday, after your lock; field him.
Sources: Fantacalcio-Online, round 11 probable lineups
```

## 5. The match card

A later slice ("match-up intelligence" in `product.md`): one card per fixture.

```text
Inter–Como · Sun 8 Nov 18:00 · updated 12 minutes ago

Inter 58% · draw 23% · Como 19%. Expected goals: Inter about 1.9, Como about 0.9.
Clean sheets: Inter 41%, Como 15%.
Likely lineups: two places disputed. Inter's right wing (Greco 60% v Mancini 40%), Como's striker.
Out: Inter's Costa (injured). Penalties: Rossi (Inter), Lombardi (Como).
Rest: Inter played Wednesday in the Champions League; rotation risk for the full-backs.
Context: Como's new coach takes his first match. That widens Como's lineup uncertainty; it doesn't move the
numbers.
Most likely to score: Rossi 45%, Greco 22%.
Sources: Fantacalcio-Online, round 11 probable lineups · Fantacalcio.it, table
```

## 6. The bench order

Full-lineup slice: who goes first in each role, and why.

```text
Bench order for round 11. Your league subs like for like, the first bench player with a rating, up to 3.

Attack:   1. De Luca: 81% to start, so he'll have a rating if a starter misses out  2. Lombardi
Defence:  1. Fontana  2. Caruso
Keeper:   Moretti covers Ferrari exactly: same club, so one of the two always plays.
```

## Later, in their own specs

- **Live, during the match:** "Inter 1–0, 34': your projected score 73 → 76; Rossi scored." The data is already
  kept as timestamped snapshots, so this can be added.
- **Alerts:** "Official lineup out: Bruno on the bench; your first defender off the bench comes in." This needs
  a way to reach the user unprompted, which today's tools don't have.
