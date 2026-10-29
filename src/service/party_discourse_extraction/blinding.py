"""Blind coding: party names, acronyms, links and leaders are masked before text leaves the machine.

The model must judge the passage, not the party it already knows. The mask is best effort: context
can still reveal the author, and the limit is documented with the pilot results.
"""

import re
from collections import Counter
from dataclasses import dataclass

PARTY_PLACEHOLDER = "[PARTIDO]"
LEADER_PLACEHOLDER = "[LIDERANÇA]"
LINK_PLACEHOLDER = "[LINK]"
# Case-sensitive acronyms avoid masking ordinary words ("novo"); names are matched ignoring case.
PARTY_PATTERNS: dict[str, tuple[str, ...]] = {
    "PT": (
        r"(?i:Partido dos Trabalhadores)",
        r"\bPT\b",
        r"(?i:\bpetistas?\b)",
        r"(?i:\bpetismo\b)",
    ),
    "NOVO": (r"(?i:Partido Novo)", r"\bNOVO\b", r"(?i:\bnovistas?\b)"),
    "MDB": (
        r"(?i:Partido do Movimento Democr[aá]tico Brasileiro)",
        r"(?i:Movimento Democr[aá]tico Brasileiro)",
        r"\bP?MDB\b",
        r"(?i:\bemedebistas?\b)",
        r"(?i:Funda[cç][aã]o Ulysses Guimar[aã]es)",
    ),
}
LEADER_PATTERNS: dict[str, tuple[str, ...]] = {
    "PT": (r"Lula", r"Dilma(?: Rousseff)?"),
    "NOVO": (r"Jo[aã]o Amo[eê]do", r"Romeu Zema"),
    "MDB": (r"Michel Temer", r"Ulysses Guimar[aã]es", r"Baleia Rossi"),
}
LINK_PATTERN = re.compile(r"(?:https?://|www\.)\S+|\b[\w.-]+\.(?:org|com|gov)\.br\b\S*")


@dataclass(frozen=True)
class BlindedText:
    text: str
    masked_counts: dict[str, int]


def _mask(text: str, patterns: tuple[str, ...], placeholder: str, counts: Counter):
    for pattern in patterns:
        text, occurrences = re.subn(pattern, placeholder, text)
        counts[placeholder] += occurrences
    return text


def blind_text(text: str, political_party: str) -> BlindedText:
    if political_party not in PARTY_PATTERNS:
        raise ValueError("DISCOURSE_BLINDING_PARTY_UNKNOWN")
    counts: Counter = Counter()
    text, links = LINK_PATTERN.subn(LINK_PLACEHOLDER, text)
    counts[LINK_PLACEHOLDER] = links
    text = _mask(text, PARTY_PATTERNS[political_party], PARTY_PLACEHOLDER, counts)
    text = _mask(text, LEADER_PATTERNS[political_party], LEADER_PLACEHOLDER, counts)
    return BlindedText(text, {key: value for key, value in counts.items() if value})
