"""Documentary baselines preserve scope, provenance and explicit unknowns."""

from copy import deepcopy

import pytest

from database.office_legal_scopes import prepare_scope_records
from service.office_duties.legal_catalog import build_legal_scope_records, scope_record_hash
from service.public_profile.contracts import OFFICE_KINDS


def test_all_system_office_kinds_and_observed_candidacy_roles_have_records():
    records = build_legal_scope_records()
    kinds = {record["office_kind"] for record in records}
    assert kinds >= OFFICE_KINDS
    assert {"governor", "vice_governor", "vice_mayor", "senator_substitute"} <= kinds
    assert len(records) == len({(row["office_kind"], row["jurisdiction"]) for row in records})
    assert all(row["content_sha256"] == scope_record_hash(row) for row in records)
    assert all(
        row["legal_valid_from"] is None and row["legal_valid_until"] is None for row in records
    )


def test_rules_have_their_own_sources_and_explicit_individual_or_collective_scope():
    for record in build_legal_scope_records():
        for rule in (*record["competencies"], *record["restrictions"]):
            assert rule["scope"] in {"individual", "collective_institution"}
            assert rule["sources"]
            assert all(
                source["reference"] and source["url"].startswith("https://")
                for source in rule["sources"]
            )


def test_unknowns_and_local_law_limits_are_not_completed_with_other_jurisdictions():
    records = {
        (row["office_kind"], row["jurisdiction"]): row for row in build_legal_scope_records()
    }
    assert records["other", "BR"]["coverage_status"] == "unclassified"
    assert records["other", "BR"]["competencies"] == []
    assert records["mayor", "BR"]["coverage_status"] == "local_law_required"
    assert records["mayor", "BR"]["competencies"] == []
    assert records["governor", "SP"]["competencies"]
    assert records["governor", "RJ"]["competencies"]
    assert records["vice_governor", "RJ"]["competencies"]


def test_batch_rejects_invalid_digest_and_same_version_conflicting_content():
    record = build_legal_scope_records()[0]
    altered = deepcopy(record)
    altered["limitations"].append("Different reviewed content")
    with pytest.raises(ValueError, match="HASH_INVALID"):
        prepare_scope_records([altered])
    altered["content_sha256"] = scope_record_hash(altered)
    with pytest.raises(ValueError, match="VERSION_CONFLICT"):
        prepare_scope_records([record, altered])
    assert len(prepare_scope_records([record, record])) == 1
