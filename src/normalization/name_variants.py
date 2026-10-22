"""Describe common name variations without deciding personal identity."""

from normalization.identity import normalize_person_name

PARTICLES = frozenset({"de", "da", "do", "das", "dos", "e"})
SUFFIXES = {"jr": "junior", "jr.": "junior"}


def name_tokens(value):
    return tuple(
        SUFFIXES.get(token, token.rstrip(".") if len(token.rstrip(".")) == 1 else token)
        for token in normalize_person_name(value).split()
        if token not in PARTICLES
    )


def classify_name_variant(registered_name, published_name):
    """Compatibility is a review hint, never authorization to link people."""
    if normalize_person_name(registered_name) == normalize_person_name(published_name):
        return "normalized_exact"
    registered, published = name_tokens(registered_name), name_tokens(published_name)
    if not registered or not published:
        return "requires_other_evidence"
    if registered == published:
        return "common_suffix_or_particle_variation"
    if len(registered) != len(published):
        return "requires_other_evidence"
    compatible = all(
        left == right or (len(right) == 1 and left.startswith(right))
        for left, right in zip(registered, published, strict=True)
    )
    return "common_initial_abbreviation" if compatible else "requires_other_evidence"
