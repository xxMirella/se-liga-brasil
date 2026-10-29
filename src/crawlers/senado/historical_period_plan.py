"""Assemble the validated load plan for the 02/10/1992-01/01/1995 Senate window."""

import json
from pathlib import Path

from crawlers.senado.historical_period_archive import SenateArchive
from crawlers.senado.historical_period_contracts import (
    WINDOW_ENDS_BEFORE,
    WINDOW_STARTS_ON,
    LoadPlan,
    PendingItem,
    SenateParty,
    SenatorBundle,
)
from crawlers.senado.historical_period_normalization import (
    as_list,
    normalize_affiliations,
    normalize_identity,
    normalize_mandates,
    normalize_party_catalog,
)
from crawlers.senado.historical_period_validation import (
    ensure_disjoint,
    ensure_exercise_within_term,
    ensure_valid_interval,
    overlaps_window,
)
from crawlers.senado.historical_period_withheld import (
    WITHHELD_SENATORS,
    WITHHOLD_AFFILIATIONS,
    WITHHOLD_ALL,
    WITHHOLD_EXERCISES,
)
from service.ingestion.contracts import IngestionError

INVENTORY_PATH = Path("data/political-orientation/itamar-senate-inventory-1992-1994.json")


def load_inventory_senator_ids(project_root: Path) -> list[str]:
    inventory = json.loads((project_root / INVENTORY_PATH).read_text(encoding="utf-8"))
    return sorted({str(row["source_person_id"]) for row in inventory["people"]}, key=int)


def build_load_plan(
    archive: SenateArchive,
    senator_ids: list[str],
    window_starts_on=WINDOW_STARTS_ON,
    window_ends_before=WINDOW_ENDS_BEFORE,
) -> LoadPlan:
    catalog_document = archive.find("parties")
    catalog = normalize_party_catalog(catalog_document) if catalog_document else {}
    pending = []
    bundles = []
    for senator_id in senator_ids:
        bundle, senator_pending = _senator_bundle(
            archive, senator_id, catalog, (window_starts_on, window_ends_before)
        )
        pending.extend(senator_pending)
        if bundle:
            bundles.append(bundle)
    pending.extend(archive.problems)
    pending.extend(_unlisted_withheld(pending, senator_ids))
    used_codes = {item.senate_party_code for b in bundles for item in b.affiliations}
    parties = sorted((catalog[code] for code in used_codes), key=lambda p: int(p.senate_party_code))
    return LoadPlan(
        window_starts_on,
        window_ends_before,
        bundles,
        [party for party in parties if party.senate_party_code != "163"],
        catalog_document,
        _unique_pending(pending),
        _source_summary(archive, senator_ids),
    )


def _unlisted_withheld(pending, senator_ids) -> list[PendingItem]:
    """Every withheld occupant appears in the report, even one with no term in the window."""
    listed = {i.senator_id for i in pending if i.code == "WITHHELD_BY_DOCUMENTARY_REVIEW"}
    return [
        PendingItem("WITHHELD_BY_DOCUMENTARY_REVIEW", senator_id, reason, scope)
        for senator_id, (scope, reason) in WITHHELD_SENATORS.items()
        if senator_id in senator_ids and senator_id not in listed
    ]


def _unique_pending(items: list[PendingItem]) -> list[PendingItem]:
    return list(dict.fromkeys(items))


def _senator_bundle(archive, senator_id, catalog, window):
    withhold = WITHHELD_SENATORS.get(senator_id)
    if withhold and withhold[0] == WITHHOLD_ALL:
        return None, [PendingItem("WITHHELD_BY_DOCUMENTARY_REVIEW", senator_id, withhold[1], "all")]
    identity_document = archive.find("detail", senator_id)
    mandates_document = archive.find("mandates", senator_id)
    if identity_document is None or mandates_document is None:
        return None, [_missing_documents(senator_id, identity_document, mandates_document)]
    try:
        bundle = SenatorBundle(normalize_identity(identity_document, senator_id))
        terms, exercises, pending = normalize_mandates(mandates_document, senator_id)
    except IngestionError as error:
        return None, [PendingItem(error.code, senator_id, "senator skipped", "all")]
    bundle.mandates_document = mandates_document
    _select_terms(bundle, terms, exercises, window, pending)
    if not bundle.terms:
        pending.append(
            PendingItem(
                "NO_SENATE_TERM_IN_WINDOW",
                senator_id,
                "no holder mandate and no API-documented exercise overlaps the window",
                "all",
            )
        )
        return None, pending
    _apply_withhold(bundle, withhold, pending)
    _select_affiliations(bundle, archive, catalog, window, pending)
    return bundle, pending


def _missing_documents(senator_id, identity_document, mandates_document) -> PendingItem:
    missing = [
        name
        for name, document in (("detail", identity_document), ("mandates", mandates_document))
        if document is None
    ]
    return PendingItem("OFFICIAL_SOURCE_DOCUMENT_MISSING", senator_id, ",".join(missing), "all")


def _select_terms(bundle, terms, exercises, window, pending) -> None:
    in_window_exercises = [
        row for row in exercises if overlaps_window(row.starts_on, row.ends_before, *window)
    ]
    in_window_terms = [t for t in terms if overlaps_window(t.starts_on, t.ends_before, *window)]
    for key, same_key in _group_by_legislature(in_window_terms).items():
        term = _merge_same_mandate(same_key)
        if term is None:
            pending.append(PendingItem("TERM_KEY_COLLISION", same_key[0].senator_id, key))
            continue
        has_exercise = any(row.legislature_key == key for row in in_window_exercises)
        if term.capacity == "substitute" and not has_exercise:
            pending.append(PendingItem("SUBSTITUTE_TERM_WITHOUT_EXERCISE", term.senator_id, key))
            continue
        bundle.terms.append(term)
        if term.capacity is None:
            pending.append(
                PendingItem(
                    "TERM_PARTICIPATION_NOT_PUBLISHED",
                    term.senator_id,
                    f"{key}: holder or alternate unknown; no exercise loaded",
                    "term_capacity",
                )
            )
    _validate_exercises(bundle, in_window_exercises, pending)


def _group_by_legislature(terms) -> dict:
    groups: dict[str, list] = {}
    for term in terms:
        groups.setdefault(term.legislature_key, []).append(term)
    return groups


def _merge_same_mandate(same_key):
    """Older API entries repeat a mandate without code or participation; they add nothing."""
    shape = {(t.represented_uf, t.starts_on, t.ends_before) for t in same_key}
    capacities = {t.capacity for t in same_key if t.capacity}
    if len(shape) != 1 or len(capacities) > 1:
        return None
    return max(same_key, key=lambda t: (t.capacity is not None, t.mandate_code is not None))


def _validate_exercises(bundle, exercises, pending) -> None:
    terms = {term.legislature_key: term for term in bundle.terms}
    kept = [row for row in exercises if row.legislature_key in terms and row.capacity]
    try:
        for row in kept:
            ensure_valid_interval(row.starts_on, row.ends_before, str(row.starts_on))
            ensure_exercise_within_term(row.starts_on, row.ends_before, terms[row.legislature_key])
        ensure_disjoint([(r.starts_on, r.ends_before, str(r.starts_on)) for r in kept])
    except IngestionError as error:
        pending.append(
            PendingItem(
                error.code,
                bundle.identity.senator_id,
                json.dumps(error.details),
                WITHHOLD_EXERCISES,
            )
        )
        return
    bundle.exercises.extend(kept)


def _apply_withhold(bundle, withhold, pending) -> None:
    if not withhold or withhold[0] != WITHHOLD_EXERCISES:
        return
    pending.append(
        PendingItem(
            "WITHHELD_BY_DOCUMENTARY_REVIEW",
            bundle.identity.senator_id,
            f"{withhold[1]} Skipped API exercises: {len(bundle.exercises)}",
            WITHHOLD_EXERCISES,
        )
    )
    bundle.exercises.clear()


def _select_affiliations(bundle, archive, catalog, window, pending) -> None:
    senator_id = bundle.identity.senator_id
    withhold = WITHHELD_SENATORS.get(senator_id)
    document = archive.find("affiliations", senator_id)
    if withhold and withhold[0] == WITHHOLD_AFFILIATIONS:
        pending.append(
            PendingItem(
                "WITHHELD_BY_DOCUMENTARY_REVIEW", senator_id, withhold[1], WITHHOLD_AFFILIATIONS
            )
        )
        return
    if document is None:
        pending.append(PendingItem("AFFILIATIONS_DOCUMENT_MISSING", senator_id, "", "affiliations"))
        return
    try:
        affiliations, year_only, row_pending = normalize_affiliations(document, senator_id)
    except IngestionError as error:
        pending.append(PendingItem(error.code, senator_id, "", "affiliations"))
        return
    pending.extend(row_pending)
    bundle.affiliations_document = document
    _keep_valid_affiliations(bundle, affiliations, catalog, window, pending)
    bundle.year_only_claims = [claim for claim in year_only if _year_claim_in_window(claim, window)]


def _year_claim_in_window(claim, window) -> bool:
    starts = claim.year_from or 0
    ends = claim.year_until or 9999
    return starts < window[1].year and ends >= window[0].year


def _keep_valid_affiliations(bundle, affiliations, catalog, window, pending) -> None:
    senator_id = bundle.identity.senator_id
    candidates = [
        row for row in affiliations if overlaps_window(row.starts_on, row.ends_before, *window)
    ]
    unknown = [row for row in candidates if not _catalog_agrees(row, catalog)]
    for row in unknown:
        pending.append(
            PendingItem(
                "AFFILIATION_PARTY_NOT_IN_SENATE_CATALOG",
                senator_id,
                f"{row.senate_party_code}/{row.abbreviation} from {row.starts_on}",
                "affiliations",
            )
        )
    try:
        for row in candidates:
            ensure_valid_interval(row.starts_on, row.ends_before, str(row.starts_on))
        ensure_disjoint(
            [
                (r.starts_on, r.ends_before, f"{r.abbreviation} {r.starts_on}")
                for r in candidates
                if r not in unknown
            ]
        )
    except IngestionError as error:
        pending.append(
            PendingItem(error.code, senator_id, json.dumps(error.details), "affiliations")
        )
        return
    bundle.affiliations.extend(row for row in candidates if row not in unknown)


def _catalog_agrees(row, catalog: dict[str, SenateParty]) -> bool:
    party = catalog.get(row.senate_party_code)
    return party is not None and party.abbreviation == row.abbreviation


def _source_summary(archive, senator_ids) -> dict:
    roster = archive.find("legislature-49")
    roster_ids = set()
    if roster:
        rows = as_list(
            roster.payload["ListaParlamentarLegislatura"]["Parlamentares"]["Parlamentar"]
        )
        roster_ids = {str(r["IdentificacaoParlamentar"]["CodigoParlamentar"]) for r in rows}
    return {
        "inventory_senator_ids": len(senator_ids),
        "legislature_49_roster_ids": len(roster_ids),
        "legislature_49_roster_ids_outside_inventory": sorted(
            roster_ids - set(senator_ids), key=int
        ),
    }
