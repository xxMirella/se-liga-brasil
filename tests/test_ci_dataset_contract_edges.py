"""Dataset trust boundaries reject inconsistent identity, dates and checkpoint metadata."""

import json
from dataclasses import asdict, replace
from uuid import uuid4

import pytest
from test_daily_voting_dataset import partition, publish
from test_daily_voting_dataset import row as daily_row

from service.analytical_datasets import contracts, storage
from service.analytical_datasets import public_voting_timeline as timeline
from service.daily_voting_dataset.storage import read_daily_manifest
from service.identity_resolution import payroll


def vote(**updates):
    return {
        "person_id": str(uuid4()),
        "voting_id": "1",
        "institution_code": "senado",
        "occurred_on": "2026-05-01",
        "date_precision": "day",
        "vote_choice": "yes",
        "participation_status": "voted",
        "evidence_sha256": "a" * 64,
        "validation_status": "verified",
    } | updates


@pytest.mark.parametrize(
    "institution,year,complete",
    [
        ("../invalid", 2026, False),
        ("senado", True, False),
        ("senado", 2201, False),
        ("senado", 2026, 1),
    ],
)
def test_partition_identifiers_year_and_completeness_are_strict(institution, year, complete):
    with pytest.raises(ValueError):
        contracts.DatasetPartition(institution, year, complete)


@pytest.mark.parametrize(
    "value,precision",
    [(2026, "year"), ("2026", "unknown"), ("2026-5", "month"), ("2026-02-29", "day")],
)
def test_event_date_precision_cannot_be_guessed_or_normalized_silently(value, precision):
    with pytest.raises(ValueError):
        contracts.event_bounds(value, precision)


@pytest.mark.parametrize(
    "updates,match",
    [
        ({"institution_code": "camara"}, "Institution differs"),
        ({"occurred_on": "2025-05-01"}, "partition year"),
        ({"vote_choice": "perhaps"}, "Invalid vote choice"),
        ({"participation_status": "maybe"}, "Invalid participation"),
        ({"vote_choice": "yes", "participation_status": "absent"}, "contradict"),
        ({"vote_choice": None, "participation_status": "voted"}, "contradict"),
        ({"evidence_sha256": "not-hash"}, "Invalid evidence"),
        ({"validation_status": "pending"}, "verified facts"),
        ({"vote_choice": []}, "scalar vote"),
        ({"person_id": None}, "scalar text"),
    ],
)
def test_vote_fact_rejects_inconsistent_evidence(updates, match):
    with pytest.raises(ValueError, match=match):
        contracts.validate_person_vote(vote(**updates), contracts.DatasetPartition("senado", 2026))


@pytest.mark.parametrize(
    "url",
    [
        "http://www.camara.leg.br/test",
        "https://user:pass@www.camara.leg.br/test",
        "https://www.camara.leg.br:443/test",
        "https://www.camara.leg.br/test#anchor",
        "https://leg.br.attacker.invalid/test",
    ],
)
def test_public_official_link_rejects_credential_leaks_or_untrusted_targets(url):
    with pytest.raises(ValueError, match="official HTTPS"):
        timeline.validate_official_url(url)


@pytest.mark.parametrize(
    "description,origin", [(None, "official_text"), ("Text", "unknown"), ("Text", "invented")]
)
def test_description_cannot_claim_official_origin_without_matching_evidence(description, origin):
    with pytest.raises(ValueError):
        timeline.project_description(description, origin)


@pytest.mark.parametrize(
    "origin,expected",
    [("official_text", "official_excerpt"), ("curated_summary", "curated_excerpt")],
)
def test_long_description_is_bounded_and_explicitly_an_excerpt(origin, expected):
    projected = timeline.project_description("X" * 281, origin)
    assert len(projected["short_description"]) == 280
    assert projected["description_kind"] == expected


@pytest.mark.parametrize(
    "field,value",
    [("matter_year", True), ("matter_year", 1700), ("round_number", True), ("round_number", 101)],
)
def test_public_timeline_rejects_invalid_matter_year_or_round(field, value):
    record = daily_row()
    record.pop("source_observed_at")
    record[field] = value
    with pytest.raises(ValueError):
        timeline.project_public_voting_timeline(record, contracts.DatasetPartition("senado", 2026))


@pytest.mark.parametrize(
    "update,match",
    [
        ({"schema_version": "unknown"}, "Unsupported analytical schema"),
        ({"input_sha256": "bad"}, "Invalid manifest content hash"),
        ({"parquet_file": "../escape.parquet"}, "Invalid manifest file name"),
        ({"row_count": True}, "Invalid manifest row count"),
        ({"row_count": -1}, "Invalid manifest row count"),
    ],
)
def test_analytical_manifest_cannot_activate_unsafe_file_or_invalid_count(update, match):
    manifest = storage.DatasetManifest(
        "person_votes.v1",
        "parser-v1",
        "senado",
        2026,
        False,
        "a" * 64,
        "b" * 64,
        "b" * 64 + ".parquet",
        0,
    )
    with pytest.raises(ValueError, match=match):
        storage.validate_manifest(replace(manifest, **update))


@pytest.mark.parametrize(
    "updates,match",
    [
        ({"occurred_on": "2026-10-13"}, "voting day mismatch"),
        ({"institution_code": "camara"}, "partition mismatch"),
        ({"year": 2025}, "partition mismatch"),
        ({"private_state_sha256": "bad"}, "Invalid private checkpoint hash"),
        ({"private_state_file": "../escape.parquet"}, "Invalid private checkpoint path"),
    ],
)
def test_daily_checkpoint_rejects_partition_and_private_path_mismatches(tmp_path, updates, match):
    manifest = publish(tmp_path, [daily_row()])
    directory = tmp_path / "derived" / partition().relative_path
    (directory / "manifest.json").write_text(json.dumps(asdict(replace(manifest, **updates))))
    with pytest.raises(ValueError, match=match):
        read_daily_manifest(directory, partition())


def test_daily_checkpoint_integrity_checks_private_file_as_well_as_public(tmp_path):
    manifest = publish(tmp_path, [daily_row()])
    directory = tmp_path / "derived" / partition().relative_path
    (directory / manifest.private_state_file).write_bytes(b"modified")
    with pytest.raises(ValueError, match="integrity mismatch"):
        read_daily_manifest(directory, partition())


def test_optional_analytical_dependency_failure_explains_installation(monkeypatch, tmp_path):
    def missing(module):
        raise ModuleNotFoundError(module)

    monkeypatch.setattr(storage.importlib, "import_module", missing)
    with pytest.raises(RuntimeError, match="optional analytical dependency"):
        storage.connect_analytical_engine(tmp_path)


@pytest.mark.parametrize("reviewed", [False, True])
def test_payroll_identity_resolution_preserves_unresolved_and_applies_reviewed_links(
    monkeypatch, reviewed
):
    effects = []
    cases = [{"scope": "RJ"}] if reviewed else []
    monkeypatch.setattr(payroll, "fetch_electoral_identity_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(payroll, "PersonIdentityIndex", lambda rows: "index")
    monkeypatch.setattr(payroll, "match_source_subject", lambda subject, index: "candidate")
    monkeypatch.setattr(payroll, "fetch_payroll_recipients", lambda *args: ["one", "two"])
    monkeypatch.setattr(
        payroll,
        "resolve_payroll_recipient",
        lambda recipient, *args: {"status": "matched" if recipient == "one" else "unresolved"},
    )
    monkeypatch.setattr(
        payroll, "fetch_reviewed_people", lambda *args: effects.append("reviewed") or []
    )
    monkeypatch.setattr(payroll, "apply_reviewed_crosswalk", lambda resolutions, *args: resolutions)
    monkeypatch.setattr(
        payroll,
        "build_identity_links",
        lambda resolutions, recipients: effects.append("links") or ["link"],
    )
    monkeypatch.setattr(payroll, "apply_payroll_identity_links", lambda *args: {"linked": 1})
    result = payroll.resolve_payroll_identities(
        None,
        "source",
        "https://official.invalid",
        [{}],
        uf="RJ",
        office_code="7",
        reviewed_cases=cases,
    )
    assert result["linked"] == 1
    assert result["unresolved_recipients"] == 1
    assert result["recipients"] == 2
    assert effects == (["reviewed", "links"] if reviewed else ["links"])


@pytest.mark.parametrize(
    "field,value", [("matter_name", ""), ("matter_kind", []), ("matter_number", " " * 4)]
)
def test_timeline_empty_or_container_text_does_not_become_public_label(field, value):
    record = daily_row()
    record.pop("source_observed_at")
    with pytest.raises(ValueError, match="Invalid nullable text"):
        timeline.project_public_voting_timeline(
            record | {field: value}, contracts.DatasetPartition("senado", 2026)
        )


def test_timeline_projection_requires_exact_input_allowlist():
    with pytest.raises(ValueError, match="Unexpected or missing"):
        timeline.project_public_voting_timeline({}, contracts.DatasetPartition("senado", 2026))


def test_null_public_source_link_is_explicitly_unknown():
    assert timeline.validate_official_url(None) is None


@pytest.mark.parametrize(
    "options,match",
    [
        ({"schema_version": "unknown"}, "Unsupported dataset schema"),
        ({"parser_version": ""}, "bounded parser"),
        ({"max_repository_bytes": True}, "positive repository"),
        ({"max_repository_bytes": 0}, "positive repository"),
    ],
)
def test_publication_rejects_invalid_budget_or_parser_before_creating_repository(
    tmp_path, options, match
):
    from service.analytical_datasets.datasets import publish_validated_dataset

    parser = options.pop("parser_version", "parser-v1")
    repository = tmp_path / "absent"
    with pytest.raises(ValueError, match=match):
        publish_validated_dataset(
            tmp_path / "absent-source",
            repository,
            contracts.DatasetPartition("senado", 2026),
            parser,
            **options,
        )
    assert not repository.exists()


def test_snapshot_input_size_budget_stops_before_decoding_large_line(tmp_path, monkeypatch):
    from service.analytical_datasets import datasets

    path = tmp_path / "input"
    path.write_bytes(b"xxxx")
    monkeypatch.setattr(datasets, "MAX_LINE_BYTES", 2)
    with pytest.raises(ValueError, match="input limit exceeded"):
        datasets.write_validated_snapshot(
            path, tmp_path / "output", contracts.DatasetPartition("senado", 2026)
        )


def test_analytical_query_missing_partition_returns_empty_without_engine(tmp_path):
    from datetime import date

    from service.analytical_datasets.query import query_person_votes

    assert (
        query_person_votes(
            tmp_path,
            contracts.DatasetPartition("senado", 2026),
            str(uuid4()),
            date(2026, 1, 1),
            date(2026, 12, 31),
        )
        == []
    )


def test_analytical_query_rejects_modified_public_parquet(tmp_path):
    from datetime import date

    from service.analytical_datasets import publish_person_votes, query_person_votes

    source = tmp_path / "source"
    record = vote()
    source.write_text(json.dumps(record) + "\n")
    partition = contracts.DatasetPartition("senado", 2026)
    manifest = publish_person_votes(source, tmp_path / "derived", partition, "parser-v1")
    (tmp_path / "derived" / partition.relative_path / manifest.parquet_file).write_bytes(
        b"modified"
    )
    with pytest.raises(ValueError, match="partition integrity mismatch"):
        query_person_votes(
            tmp_path / "derived",
            partition,
            record["person_id"],
            date(2026, 1, 1),
            date(2026, 12, 31),
        )
