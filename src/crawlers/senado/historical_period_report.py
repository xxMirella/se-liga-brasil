"""Auditable report of what the Senate load inserts, skips and leaves for review."""

from collections import Counter, defaultdict

from crawlers.senado.historical_period_contracts import LoadPlan
from crawlers.senado.historical_period_rows import bundle_documents


def build_report(plan: LoadPlan, run, generated_on: str) -> dict:
    first, second = run.first_pass, run.second_pass
    return {
        "load": "senate_history_1992_1994",
        "generated_on": generated_on,
        "mode": str(run.mode),
        "committed": run.committed,
        "window": {
            "starts_on": plan.window_starts_on.isoformat(),
            "ends_before": plan.window_ends_before.isoformat(),
            "end_semantics": "exclusive; the Senate's inclusive last day became the next day",
        },
        "would_insert" if not run.committed else "inserted": _counts(first.inserted),
        "second_pass_inserted": _counts(second.inserted),
        "idempotent": run.idempotent,
        "senators": {
            "in_inventory": plan.source_summary["inventory_senator_ids"],
            "in_plan": len(plan.senators),
            "written": first.senators_written,
            "linked_to_existing_official_identity": first.senators_linked_to_existing_identity,
        },
        "plan": _plan_statistics(plan),
        "party_abbreviations": first.party_abbreviations,
        "existing_row_conflicts": first.conflicts,
        "identity_review_required": [_item(i) for i in first.review_required],
        "pending": _pending_by_code(plan, first),
        "legislature_49_roster_ids_outside_inventory": plan.source_summary[
            "legislature_49_roster_ids_outside_inventory"
        ],
        "source_documents": _documents(plan),
    }


def _counts(counter) -> dict:
    return {key: counter.get(key, 0) for key in sorted(counter)}


def _plan_statistics(plan: LoadPlan) -> dict:
    bundles = plan.senators
    affiliations = [a for b in bundles for a in b.affiliations]
    return {
        "terms": sum(len(b.terms) for b in bundles),
        "terms_with_unpublished_participation": sum(
            1 for b in bundles for t in b.terms if t.capacity is None
        ),
        "exercises": sum(len(b.exercises) for b in bundles),
        "affiliations_with_party": sum(1 for a in affiliations if not a.is_without_party),
        "intervals_without_party": sum(1 for a in affiliations if a.is_without_party),
        "year_precision_claims_kept_as_facts": sum(len(b.year_only_claims) for b in bundles),
        "open_ended_affiliations": sorted(
            {
                a.senator_id
                for a in affiliations
                if a.ends_before is None and not a.is_without_party
            },
            key=int,
        ),
        "historical_parties": [
            {"senate_code": p.senate_party_code, "abbreviation": p.abbreviation, "name": p.name}
            for p in plan.parties
        ],
    }


def _item(item) -> dict:
    return {
        "code": item.code,
        "senator_id": item.senator_id,
        "detail": item.detail,
        "scope": item.withheld_scope,
    }


def _pending_by_code(plan: LoadPlan, outcome) -> dict:
    grouped = defaultdict(list)
    for item in [*plan.pending, *outcome.review_required]:
        grouped[item.code].append(_item(item))
    return {code: {"count": len(items), "items": items} for code, items in sorted(grouped.items())}


def _documents(plan: LoadPlan) -> dict:
    documents = [d for b in plan.senators for d in bundle_documents(b)]
    if plan.party_catalog_document:
        documents.append(plan.party_catalog_document)
    counts = Counter(d.kind for d in documents)
    return {
        "by_kind": dict(counts),
        "files": [
            {"kind": d.kind, "senator_id": d.senator_id, "sha256": d.sha256, "path": d.archive_path}
            for d in documents
        ],
    }
