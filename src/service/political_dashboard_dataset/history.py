"""Reduce annual compositions to what the timeline draws, once, when data is published.

The history of a territory does not depend on the selected year or view, so it is built at
publication time and read by key. Detail (segments, party periods, sources) of an ordinary
year stays in that year's partition; only the fields read by the timeline, the orientation
cells and the presidential explanations remain here.
"""

import base64
import hashlib
import json
import zlib

HISTORY_SCHEMA_VERSION = "political_dashboard_history.v1"
EXECUTIVE_INSTITUTIONS = frozenset(
    {"presidency", "state_government", "district_government", "municipal_government"}
)
LEGISLATIVE_KEPT_FIELDS = (
    "political_parties",
    "expected_seats",
    "documented_vacancies",
    "orientation_policy_version",
    "total",
    "coverage",
    "snapshot_on",
    "institutional_status",
)
EXECUTIVE_KEPT_FIELDS = ("institutional_status",)
HOISTED_FIELDS = ("institution_code", "territory_code", "office_kinds")
PARTY_RECORD_FIELDS = ("political_party", "political_party_status")
PRESIDENTIAL_RECORD_FIELDS = (
    "name",
    "person_id",
    "exercise_id",
    "source_url",
    "starts_on",
    "ends_before",
    "date_precision",
    "exercise_capacity",
    "exercise_capacity_source_url",
)
PRESIDENTIAL_PERIOD_FIELDS = (
    "political_party",
    "starts_on",
    "ends_before",
    "source_url",
    "date_precision",
    "political_party_status",
)
CURRENT_IDENTITY_FIELDS = ("person_id", "exercise_id", "starts_on", "ends_before")


def copy_present(source, fields):
    """Copy only keys that exist, so that null and absent stay distinguishable."""
    return {field: source[field] for field in fields if field in source}


def reduce_party_periods(periods, fields):
    return [copy_present(period, fields) for period in periods]


def reduce_party_record(record, *, detail_fields=(), period_fields=PARTY_RECORD_FIELDS):
    reduced = copy_present(record, (*detail_fields, *PARTY_RECORD_FIELDS))
    if "political_party_periods" in record:
        periods = record["political_party_periods"]
        reduced["political_party_periods"] = (
            reduce_party_periods(periods, period_fields) if isinstance(periods, list) else periods
        )
    return reduced


def executive_record_detail(institution_code, *, presidential_detail):
    """Fields and period fields kept for one executive record, by what a renderer reads."""
    if institution_code != "presidency":
        return (), PARTY_RECORD_FIELDS
    if presidential_detail:
        return PRESIDENTIAL_RECORD_FIELDS, PRESIDENTIAL_PERIOD_FIELDS
    return CURRENT_IDENTITY_FIELDS, PARTY_RECORD_FIELDS


def reduce_executive_records(records, institution_code, *, presidential_detail):
    if not isinstance(records, list):
        return records
    detail_fields, period_fields = executive_record_detail(
        institution_code, presidential_detail=presidential_detail
    )
    return [
        reduce_party_record(record, detail_fields=detail_fields, period_fields=period_fields)
        for record in records
    ]


def reduce_current_record(current, institution_code):
    if not isinstance(current, dict):
        return current
    identity = CURRENT_IDENTITY_FIELDS if institution_code == "presidency" else ()
    return reduce_party_record(current, detail_fields=identity)


def reduce_executive_composition(composition, institution_code, *, presidential_detail):
    reduced = copy_present(composition, EXECUTIVE_KEPT_FIELDS)
    if "current" in composition:
        reduced["current"] = reduce_current_record(composition["current"], institution_code)
    for field in ("segments", "national_observations"):
        if field in composition:
            reduced[field] = reduce_executive_records(
                composition[field], institution_code, presidential_detail=presidential_detail
            )
    if presidential_detail and "government_context_observations" in composition:
        reduced["government_context_observations"] = composition["government_context_observations"]
    return reduced


def presidency_needs_detail(row):
    """True when the page explains this presidential year (names, dates, sources).

    Delegates to the renderer's own predicate so that the reduction cannot drift from it;
    changing the reviewed presidential events therefore requires republishing the history.
    """
    from service.political_dashboard.presidential_explanations import (
        presidential_year_explanation,
    )

    institution = {**row["composition"], "institution_code": "presidency"}
    return presidential_year_explanation({"year": row["year"], "institutions": [institution]})


def reduce_composition(row):
    code = row["institution_code"]
    if code not in EXECUTIVE_INSTITUTIONS:
        return copy_present(row["composition"], LEGISLATIVE_KEPT_FIELDS)
    detail = code == "presidency" and bool(presidency_needs_detail(row))
    return reduce_executive_composition(row["composition"], code, presidential_detail=detail)


def reduce_history_row(row):
    """One annual institution row as stored: hoisted identity fields, reduced composition."""
    reduced = {
        "year": row["year"],
        "institution_code": row["institution_code"],
        "territory_code": row["territory_code"],
        "office_kinds": row.get("office_kinds"),
        "total": row.get("total"),
    }
    if row.get("composition"):
        reduced["composition"] = reduce_composition(row)
    return reduced


def expand_history_row(stored):
    """Restore the row shape consumed by the dashboard aggregation."""
    row = {key: value for key, value in stored.items() if key != "composition"}
    if "composition" in stored:
        row["composition"] = {
            **{field: stored[field] for field in HOISTED_FIELDS},
            **stored["composition"],
        }
    return row


def sort_key(row):
    return row["year"], row["territory_code"], row["institution_code"]


def build_territory_history(source_rows):
    """Deterministic payload of one territory from the annual rows read by the publisher."""
    rows = sorted((reduce_history_row(row) for row in source_rows), key=sort_key)
    return {"schema_version": HISTORY_SCHEMA_VERSION, "rows": rows}


def encode_history(payload):
    content = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return content, hashlib.sha256(content).hexdigest()


def compress_history(content):
    return zlib.compress(content, 9)


def history_entry(territory_code, source_rows):
    """Publishable row of one territory: digest of the canonical JSON plus its compressed form."""
    payload = build_territory_history(source_rows)
    content, digest = encode_history(payload)
    return {
        "territory_code": territory_code,
        "schema_version": HISTORY_SCHEMA_VERSION,
        "content_sha256": digest,
        "row_count": len(payload["rows"]),
        "uncompressed_bytes": len(content),
        "payload_zlib": compress_history(content),
    }


MAX_DECOMPRESSED_HISTORY_BYTES = 16 * 1024 * 1024


def decode_history(payload_zlib):
    """Inverse of compress_history, bounded and validated: a corrupt row never reaches a page."""
    decompressor = zlib.decompressobj()
    try:
        content = decompressor.decompress(payload_zlib, MAX_DECOMPRESSED_HISTORY_BYTES)
    except zlib.error as error:
        raise ValueError("HISTORY_PAYLOAD_INVALID") from error
    if decompressor.unconsumed_tail or decompressor.unused_data or not decompressor.eof:
        raise ValueError("HISTORY_PAYLOAD_INVALID")
    payload = json.loads(content)
    if not isinstance(payload, dict) or payload.get("schema_version") != HISTORY_SCHEMA_VERSION:
        raise ValueError("HISTORY_SCHEMA_UNSUPPORTED")
    rows = payload.get("rows")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("HISTORY_ROWS_INVALID")
    return payload


def decode_history_base64(encoded):
    return decode_history(base64.b64decode(encoded, validate=True))


def dataset_version(history_digests, partition_digests):
    """Short stable identity of the exact published data behind one response."""
    parts = sorted(history_digests) + ["|"] + sorted(partition_digests)
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]
