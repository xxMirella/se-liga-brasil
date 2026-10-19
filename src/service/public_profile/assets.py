"""Election asset declarations, explicitly separate from current net worth."""

from collections import defaultdict
from urllib.parse import urlsplit

from service.public_profile.contracts import PublicProfileError
from service.public_profile.people_contracts import validate_as_of, validate_person_id


def official_asset_url(value):
    try:
        parsed = urlsplit(value or "")
        host = parsed.hostname or ""
        valid = parsed.scheme == "https" and (host == "tse.jus.br" or host.endswith(".tse.jus.br"))
        valid = valid and not parsed.username and not parsed.password and parsed.port in (None, 443)
    except ValueError:
        valid = False
    return value if valid and len(value) <= 2048 else None


def public_asset_item(row):
    return {
        "asset_type": row["asset_type"],
        "declared_value": str(row["declared_value"]),
        "value_quality_status": row["value_quality_status"],
        "official_url": official_asset_url(row.get("source_url")),
    }


def public_asset_declaration(row, items):
    return {
        "election_year": row["election_year"],
        "kind": "electoral_asset_declaration",
        "currency": "BRL",
        "recorded_total": str(row["recorded_total"]),
        "total_scope": "available_records_only",
        "item_count": row["item_count"],
        "items": items,
        "items_truncated": row["item_count"] > len(items),
        "value_quality_status": "requires_review" if row["review_count"] else "reported",
        "source_generated_at": row["source_generated_at"].isoformat(),
        "source": {"code": "tse", "name": "Tribunal Superior Eleitoral"},
        "coverage": "completeness_unverified",
    }


def get_public_assets(repository, person_id, as_of):
    validate_person_id(person_id)
    validate_as_of(as_of)
    with repository.read_snapshot():
        if repository.fetch_person(person_id) is None:
            raise PublicProfileError("person_not_found", 404)
        years = repository.fetch_asset_years(person_id, as_of)
        rows = (
            repository.fetch_asset_items(person_id, [row["election_year"] for row in years[:100]])
            if years
            else []
        )
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["election_year"]].append(public_asset_item(row))
    declarations = [
        public_asset_declaration(row, grouped[row["election_year"]]) for row in years[:100]
    ]
    return {
        "person_id": person_id,
        "as_of": as_of.isoformat(),
        "declarations": declarations,
        "coverage": {
            "status": "partial" if years else "unknown",
            "years_truncated": len(years) > 100,
        },
        "current_net_worth": {"value": None, "status": "not_established_by_electoral_declarations"},
    }
