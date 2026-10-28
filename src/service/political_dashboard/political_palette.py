"""Stable party colors from the approved visual design, independent from ranking or year."""

from hashlib import sha256
from unicodedata import normalize

PALETTE = ("#236049", "#56866c", "#aaa24d", "#c79d58", "#678798", "#9b8b9f", "#a7b5a1")
PARTY_COLORS = {
    "PSD": PALETTE[0],
    "PL": PALETTE[1],
    "MDB": PALETTE[2],
    "PMDB": PALETTE[2],
    "PT": PALETTE[3],
    "UNIAO": PALETTE[4],
    "UNIAO BRASIL": PALETTE[4],
    "PP": PALETTE[5],
    "REPUBLICANOS": PALETTE[6],
    "PRB": PALETTE[6],
    "PSB": PALETTE[0],
    "PODE": PALETTE[1],
    "PODEMOS": PALETTE[1],
    "PSDB": PALETTE[2],
}
UNKNOWN_COLOR = "#89978e"


def political_group_color(abbreviation, *, identified=True):
    if not identified:
        return UNKNOWN_COLOR
    key = normalize("NFKD", str(abbreviation)).encode("ascii", "ignore").decode().upper().strip()
    return (
        PARTY_COLORS.get(key)
        or PALETTE[int.from_bytes(sha256(key.encode()).digest()[:2]) % len(PALETTE)]
    )


MIXED_COLOR = "#b5bdb2"


def political_party_color(abbreviation):
    label = str(abbreviation or "").strip().casefold()
    unknown = not label or label.startswith(
        ("filiação", "sem partido", "partidos proibidos", "partidos extintos",
         "monarquia", "não informad", "unknown")
    )
    return political_group_color(abbreviation, identified=not unknown)
