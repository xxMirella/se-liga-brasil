"""Occupants and facts the documentary review did not settle; they are reported, never ingested.

Each entry names what stays out of the database. Lifting a withhold requires a new documented
decision (an act or a dated official record), not a change in the data itself.
"""

WITHHOLD_ALL = "all"
WITHHOLD_AFFILIATIONS = "affiliations"
WITHHOLD_EXERCISES = "exercises"

WITHHELD_SENATORS = {
    "1537": (
        WITHHOLD_ALL,
        "Carlos De' Carli (1537) and Carlos de Carli (1542) are distinct official IDs; whether they"
        " are one person needs person_identity_review, never a name join.",
    ),
    "1542": (
        WITHHOLD_ALL,
        "Carlos de Carli (1542) vs Carlos De' Carli (1537): left to person_identity_review.",
    ),
    "63": (
        WITHHOLD_AFFILIATIONS,
        "Ney Suassuna: printed heading of 11/03/1993 (DCN p. 2111) says PTB, the API says MDB.",
    ),
    "799": (
        WITHHOLD_AFFILIATIONS,
        "Lavoisier Maia: S/Partido in the API against the printed list of April 1994.",
    ),
    "51": (
        WITHHOLD_AFFILIATIONS,
        "Junia Marise: printed list of April 1994 diverges from the API.",
    ),
    "1737": (
        WITHHOLD_EXERCISES,
        "Henrique Almeida (AP): the 1994 seat occupant is contested; no act settles it.",
    ),
    "2": (
        WITHHOLD_EXERCISES,
        "Alexandre Costa (MA): probable return to the Senate without a documented act.",
    ),
    "32": (
        WITHHOLD_EXERCISES,
        "Hugo Napoleao (PI): probable return to the Senate without a documented act.",
    ),
    "85": (
        WITHHOLD_EXERCISES,
        "Jose Eduardo (PR): probable return to the Senate without a documented act.",
    ),
    "1634": (
        WITHHOLD_EXERCISES,
        "Fernando Henrique Cardoso (SP): ministerial office; return to the Senate not proved.",
    ),
}
