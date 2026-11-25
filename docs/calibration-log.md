# Calibration log

Each change to a starting value in `engine/constants.py`, from a `fantadamus recalibrate` proposal the owner
approved (mvp-recalibrate R8). Newest first. Aggregates only: no player, club or league is named. A change is
undone the same way: a later proposal, approved, and an entry here.

## 2026-11-24: rounds 10 to 12

Approved by the owner on 2026-11-24, from the proposal on rounds 10 to 12, run from stored facts only (`mvp-cameos`).
Round 10 has no ratings to score, so the evidence is rounds 11 and 12.

| Value | Old | New | Evidence | Where it wasn't fitted |
|---|---|---|---|---|
| `CAMEO_SHARE` | 0.500 | 0.239 | 255 players with a flat cameo who didn't start and could have come on, 61 of whom got a rating; 90% between 0.198 and 0.286 | round 11: Brier 0.149 to 0.120, reliability gap 0.143 to 0.082; round 12: Brier 0.134 to 0.111, reliability gap 0.096 to 0.055 |

Benched defenders and midfielders got a rating a quarter of the time, where the model said half. Forwards and attacking
midfielders have a share of their own from here on (`CAMEO_SHARE_PRICED`), because one share can't fit both kinds.

### What it moves

On round 12's stored facts, from a copy of the lake, at the owner's last answer without an override, just before the
lock and a second before it:

- **The lineup:** the same formation, captain and eleven each time; 2 of 12 bench places change in the first, none in the
  others. The expected score falls by 0.35 in the first and 0.17 in the others, and each threshold's chance moves by at
  most 2 points: fewer substitutes are expected to get a rating.
- **The cards:** of 294 players on the ten cards, no chance of starting moves, and 149 values do, by 0.05 on average and
  0.27 at most. One card's likeliest scorers reorder.
- **The answers' shape** stays the same.

### Not changed

- `CAMEO_SHARE_PRICED`: fitted at 0.648, but on 128 of the 200 players it needs, and on the rounds it wasn't fitted on it
  makes the Brier score slightly worse: 0.106 to 0.108 and 0.133 to 0.151.
- `CAMEO_RATED`: held at the method's 60%. Rated games can't tell it from how often an attacker comes on.
- `START_MAP`: refitted on rounds 10 to 12, it doesn't improve where it wasn't fitted.
- `PENALTY_RATE` and `PENALTY_CONVERSION`: 27 of the 30 penalties they need.
- The yellow- and red-card rates move by a thousandth or less, and weren't asked for.
- The rest waits, with the evidence each needs, as `fantadamus recalibrate` lists it.

## 2026-11-12: rounds 10 and 11

Approved by the owner on 2026-11-12, from the proposal on rounds 10 and 11, run from stored facts only.

| Value | Old | New | Evidence | Where it wasn't fitted |
|---|---|---|---|---|
| `START_MAP` | the identity | 0.007 to 0.015, 0.169 to 0.063, 0.249 to 0.085, 0.326 to 0.196, 0.440 to 0.376, 0.553 to 0.594, 0.647 to 0.619, 0.747 to 0.739, 0.856 to 0.827, 0.913 to 0.925 | 1,033 players whose start is known, over two rounds; the knots rounded to three decimals | round 10: Brier 0.117 to 0.116, reliability gap 0.069 to 0.048; round 11: Brier 0.104 to 0.099, reliability gap 0.089 to 0.064 |
| `YELLOW_PRIOR` | 0.150 | 0.116 | 310 yellow cards in 2,682 outfield appearances, in the statistics read made with the table on 2026-11-04; 90% between 0.106 and 0.126 | a count, not a forecast |

The outlets overstated the chances between about 10% and 40%: a quarter-chance started about one time in eleven.
At the top they were right.

### What it moves

On round 11's stored facts, at its lock:

- **A lineup:** the owner's keeps its formation and captain; one starter changes, and the bench order with
  it. The expected score rises by about a tenth of a point, and each threshold's chance by under a point.
- **The cards:** 299 players' chances of starting move by 0.03 on average and by 0.16 at most. None crosses
  50%, so no likely eleven and no disputed place changes; three of the ten cards reorder their likeliest
  scorers. The match numbers don't move.
- **The answers' shape** stays the same.

### Not changed

- `CAMEO_SHARE`: fitted at 0.248, but on 183 of the 200 players it needs. Held out on half of round 11's
  matches, it lowers the Brier score from 0.136 to 0.120 and from 0.138 to 0.116. It waits for round 12.
- `CAMEO_RATED`: not fitted. Benched attackers got a rating about twice as often as benched defenders and
  midfielders, more than one share allows: one share doesn't fit both kinds of cameo.
- `PENALTY_RATE` (0.110) and `PENALTY_CONVERSION` (0.636): 22 of the 30 penalties they need.
- `PENALTY_SAVED_SHARE` and `RED_RATE`: the stored statistics reads don't count them yet.
- The rest waits, with the evidence each needs, as `fantadamus recalibrate` lists it.
