"""Rule that decides which roll calls are votes on the substance of a proposition.

Reproducible, text-based and independent of how any party voted. Pure functions.
"""

import re

CAMARA_MAIN_TEXT = re.compile(
    r"^(aprovad[oa]s?|rejeitad[oa]s?)\b.*?(projeto|proposta de emenda|medida provis[oó]ria|"
    r"substitutivo|texto-?\s?base)",
    re.IGNORECASE,
)
CAMARA_NOT_MAIN_TEXT = re.compile(
    r"requerimento|reda[cç][aã]o final|emendas? (de reda|n[º°o]|do senado|de plen)|destaque|"
    r"prefer[eê]ncia|urg[eê]ncia|parecer (da|de|do)|mantido|suprimido|subemenda|"
    r"admissibilidade|vota[cç][aã]o parcelada",
    re.IGNORECASE,
)
BASE_TEXT_RESERVING_HIGHLIGHTS = re.compile(
    r"^(aprovad[oa]s?|rejeitad[oa]s?)\b.*ressalvad[oa]s? (os )?destaques?", re.IGNORECASE
)
SENATE_SUBSTANTIVE_KINDS = frozenset({"PEC", "PL", "PLC", "PLS", "PLV", "PLP", "MPV"})
SENATE_NOT_MAIN_TEXT = re.compile(r"^(emendas?|destaque|requerimento|subemenda)\b", re.IGNORECASE)


def is_camara_main_text_vote(description: str) -> bool:
    """Approval or rejection of the principal text (PL, PEC, MPV, substitutivo, texto-base).

    "ressalvados os destaques" marks the Chamber's base-text vote before highlighted
    amendments, so it is main text even when the wording mentions amendments or destaques.
    """
    if BASE_TEXT_RESERVING_HIGHLIGHTS.search(description):
        return True
    return bool(
        CAMARA_MAIN_TEXT.search(description) and not CAMARA_NOT_MAIN_TEXT.search(description)
    )


def is_senate_main_text_vote(proposition_kind: str, description: str) -> bool:
    if proposition_kind.upper() not in SENATE_SUBSTANTIVE_KINDS:
        return False
    return not SENATE_NOT_MAIN_TEXT.search(description.strip())
