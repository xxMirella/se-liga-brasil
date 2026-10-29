"""Link roll calls to curated thematic items by proposition identity plus an ementa guard."""

from service.party_vote_analysis.contracts import PropositionRef
from service.party_vote_analysis.thematic_catalog import CATALOG, ThematicItem


def _build_index(catalog=CATALOG) -> dict[tuple[str, str, int, int], list[ThematicItem]]:
    index: dict[tuple[str, str, int, int], list[ThematicItem]] = {}
    for item in catalog:
        for key in item.keys:
            index.setdefault(key, []).append(item)
    return index


ITEMS_BY_KEY = _build_index()


def match_thematic_items(chamber: str, propositions) -> list[ThematicItem]:
    """Items whose proposition appears in the voting and whose ementa contains a guard word."""
    found: dict[str, ThematicItem] = {}
    for reference in propositions:
        key = (chamber, reference.kind.upper(), reference.number, reference.year)
        for item in ITEMS_BY_KEY.get(key, ()):
            if guard_matches(item, reference):
                found[item.item_id] = item
    return list(found.values())


def guard_matches(item: ThematicItem, reference: PropositionRef) -> bool:
    summary = reference.summary.casefold()
    return any(word.casefold() in summary for word in item.ementa_guard)
