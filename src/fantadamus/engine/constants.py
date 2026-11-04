"""Every starting value the method marks (start), with where it comes from (design C8).

Calibration from the decision log (method §A8) changes this file and nothing else.
"""

from __future__ import annotations

from typing import NamedTuple

# Availability (R3.2 to R3.4, design C5)
P_START_STARTER = 0.90  # an outlet lists him among the starters
P_START_BENCH = 0.05  # an outlet lists him on the bench, or doesn't mention him
CAMEO_SHARE = 0.5  # p_cameo = 0.5 * (1 - p_start) for an available player
DISPUTED_SPREAD = 0.30  # outlets at least this far apart mark him disputed
CONTESTED_PERCENT = (31, 69)  # two of one role between these, making 100, are in a ballottaggio (the sheets'
# defaults, 90 and 30 or 95 and 5, also make 100, and would pair every starter with every bench player)

# Many sources, compared (mvp-collect R5.3, design C12)
ODDS_DISPUTED_SPREAD = 0.10  # odds pages' de-margined 1X2 at least this far apart are disputed

# Team xG from the betting lines (R5.2, R5.3, method §A4 and §A5, design C7)
DIXON_COLES_RHO = -0.10  # the low-score correction; negative adds 0-0 and 1-1 draws
MAX_GOALS = 10  # a team's goals counted up to this in the 1X2
XG_RANGE = (0.20, 4.00)  # the team xG searched
TEAM_FORM_WEIGHT = 12  # regressed team form weighs n / (n + 12) matches, without odds

# The outfield model (R9, method §A4; every role: mvp-roles R2)
VOTE_BASELINE = 6.0  # an outfield player's expected vote before his own ratings count
VOTE_WEIGHT = 10  # k_vote: his average counts n / (n + 10) of rated appearances
FIXTURE_EFFECT = 0.3  # the vote moves 0.3 x (P(win) - P(loss))
SHARE_WEIGHT = 15  # W: shares shrink toward the prior with the weight of 15 team goals
DEFENDER_SHARE_WEIGHT = 25  # and a defender's with 25


class RolePriors(NamedTuple):
    goal: float  # goal share
    assist: float  # assist share
    minutes: float  # minutes share if he starts
    priced_cameo: bool  # an attacker's cameo is priced; anyone else's is CAMEO_FLAT


ROLE_PRIORS = {  # by first Mantra role (mvp-roles R2.1)
    "Pc": RolePriors(0.30, 0.11, 0.85, True),  # centre-forward
    "A": RolePriors(0.20, 0.11, 0.85, True),  # second striker
    "W": RolePriors(0.15, 0.11, 0.85, True),  # wide forward
    "T": RolePriors(0.15, 0.11, 0.80, True),  # attacking midfielder
    "C": RolePriors(0.06, 0.08, 0.85, False),  # central midfielder; 0.85 minutes: the method gives none
    "M": RolePriors(0.06, 0.08, 0.85, False),  # holding midfielder; likewise
    "E": RolePriors(0.04, 0.08, 0.85, False),  # wing-back; likewise
    "Dd": RolePriors(0.03, 0.06, 0.95, False),  # full-back
    "Ds": RolePriors(0.03, 0.06, 0.95, False),
    "Dc": RolePriors(0.05, 0.02, 0.95, False),  # centre-back
    "B": RolePriors(0.05, 0.02, 0.95, False),
}
USUAL_MANTRA_ROLE = {"A": "A", "C": "C", "D": "Dc"}  # by Classic role, when his Mantra role is unknown (R2.2)
MINUTES_CAMEO = 0.28  # an attacker's minutes share if he comes on
PENALTY_RATE = 0.15  # P(his team gets a penalty) per match
PENALTY_CONVERSION = 0.78
YELLOW_PRIOR = 0.15  # yellow cards per appearance, before his own count
YELLOW_WEIGHT = 10  # appearances' weight of that prior
CAMEO_GOAL_VALUE = 9.8  # a cameo with a goal
CAMEO_RATED = 0.6  # a cameo without a goal gets a rating this often
CAMEO_RATING = 5.75  # and is worth this
CAMEO_FLAT = 5.5  # anyone else's cameo (method §A4)

# The keeper model (method §A6; mvp-roles R3)
KEEPER_BETA = 0.35  # a goal conceded costs his rating this much
KEEPER_SKILL_WEIGHT = 9  # his skill counts n / (n + 9) of rated appearances
LEAGUE_GOALS_PER_MATCH = 1.3  # each team's goals per match, before the table has any

# The answer (R10.2, method §A7)
COIN_FLIP = 0.15  # a margin below this is a coin flip
CLEAR = 0.5  # above this, clear; in between, a lean

# Freshness (R7.3): how long a fact counts, and the tighter target within a day of the match
FRESH_FOR_HOURS = {
    "probable_lineups": 12,
    "match_odds": 24,
    "player_season": 48,  # a round's ratings count before the next round (mvp-roles R1.4)
    "team_season": 7 * 24,
    "penalty_takers": 7 * 24,
    "fixtures": 7 * 24,
}
FRESH_NEAR_MATCH_HOURS = {"probable_lineups": 3, "match_odds": 6}
NEAR_MATCH_HOURS = 24
