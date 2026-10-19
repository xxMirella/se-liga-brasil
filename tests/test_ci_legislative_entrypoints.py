"""Bounded historical commands and enrichment composition remain entirely offline."""

import json
from contextlib import nullcontext
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from application import legislative
from service.enrichment import pipeline as enrichment
from service.ingestion.contracts import IngestionError
from service.legislative_collection import sources


def options(**updates):
    return SimpleNamespace(
        **{
            "storage_directory": None,
            "env_file": None,
            "command": "collect-history",
            "source": "camara",
            "start_date": None,
            "end_date": None,
            "person_id": None,
            "limit": 3,
            "proposition_ids": None,
            "years": None,
            "reviewed_identities": None,
            "max_partitions": 1,
            "max_identity_profiles": 0,
        }
        | updates
    )


@pytest.fixture(autouse=True)
def no_database(monkeypatch):
    monkeypatch.setattr(legislative, "connect_database", lambda _: nullcontext("connection"))


def test_history_cli_canonicalizes_person_and_passes_explicit_document_scope(monkeypatch):
    person_id = str(uuid4())
    calls = []
    monkeypatch.setattr(
        legislative,
        "collect_camara_history",
        lambda *args, **kwargs: calls.append((args, kwargs)) or {"ok": True},
    )
    assert legislative.execute_historical_command(
        options(
            person_id=person_id,
            start_date="2026-05-01",
            end_date="2026-05-27",
            proposition_ids="1,,2",
        )
    ) == {"ok": True}
    assert calls[0][0][2] == [person_id]
    assert calls[0][1] == {
        "limit": 3,
        "start": date(2026, 5, 1),
        "end": date(2026, 5, 27),
        "proposition_ids": ("1", "2"),
    }


@pytest.mark.parametrize(
    "start,end", [("2026-05-01", None), (None, "2026-05-27"), ("2026-05-27", "2026-05-01")]
)
def test_camara_partial_or_reversed_interval_is_rejected(start, end):
    with pytest.raises(IngestionError, match="INVALID_LEGISLATIVE_INTERVAL"):
        legislative.execute_historical_command(options(start_date=start, end_date=end))


@pytest.mark.parametrize(
    "source,start,end",
    [
        ("camara", "2026-05-01", "2026-05-27"),
        ("senado", None, "2026-05-27"),
        ("senado", "2026-05-01", None),
    ],
)
def test_votes_command_requires_supported_source_and_explicit_dates(source, start, end):
    with pytest.raises(IngestionError, match="SELECT_SENADO_AND_EXPLICIT_VOTING_DATES"):
        legislative.execute_historical_command(
            options(command="collect-votes", source=source, start_date=start, end_date=end)
        )


def test_votes_command_forwards_limits_without_source_identity_persistence(monkeypatch):
    calls = []
    monkeypatch.setattr(
        legislative,
        "collect_senate_voting_partitions",
        lambda *args, **kwargs: calls.append((args, kwargs)) or {"ok": True},
    )
    legislative.execute_historical_command(
        options(
            command="collect-votes", source="senado", start_date="2026-05-01", end_date="2026-05-27"
        )
    )
    assert calls[0][1] == {
        "max_partitions": 1,
        "max_votings": 3,
        "max_identity_profile_downloads": 0,
    }


@pytest.mark.parametrize("year", [None, "all"])
def test_cmsp_cli_requires_explicit_year(year):
    with pytest.raises(IngestionError, match="SELECT_SUPPORTED_HISTORICAL_SOURCE_AND_SCOPE"):
        legislative.execute_historical_command(options(source="cmsp", years=year))


def test_reviewed_identity_bindings_are_explicit_and_size_bounded(tmp_path):
    assert legislative.read_reviewed_bindings(None) == ()
    path = tmp_path / "review.json"
    person_id = str(uuid4())
    path.write_text(
        json.dumps(
            [
                {
                    "person_id": person_id,
                    "official_author_name": "Pessoa Teste",
                    "artifact_sha256": "a" * 64,
                    "evidence_reference": "official-record",
                }
            ]
        )
    )
    assert str(legislative.read_reviewed_bindings(path)[0].person_id) == person_id
    path.write_bytes(b" " * (1024 * 1024 + 1))
    with pytest.raises(IngestionError, match="FILE_LIMIT_EXCEEDED"):
        legislative.read_reviewed_bindings(path)


def test_cmsp_cli_loads_reviewed_bindings_and_explicit_years(monkeypatch):
    calls = []
    monkeypatch.setattr(
        legislative,
        "collect_cmsp_history",
        lambda *args, **kwargs: calls.append((args, kwargs)) or {},
    )
    legislative.execute_historical_command(options(source="cmsp", years="2025,2026"))
    assert calls[0][0][2] == [2025, 2026]
    assert calls[0][1] == {"reviewed_bindings": ()}


@pytest.mark.parametrize("keys", [("../escape",), tuple(str(value) for value in range(101))])
def test_source_document_scope_is_bounded_before_database_or_http(tmp_path, keys):
    with pytest.raises(ValueError, match="Invalid bounded proposition"):
        sources.collect_camara_history(None, tmp_path, proposition_ids=keys)


@pytest.mark.parametrize("explicit", [False, True])
def test_camara_adapter_selects_registered_scope_or_explicit_document_urls(
    monkeypatch, tmp_path, explicit
):
    selected = []
    monkeypatch.setattr(
        sources,
        "select_proposition_keys",
        lambda *args, **kwargs: selected.append((args, kwargs)) or ["known-document"],
    )
    monkeypatch.setattr(
        sources,
        "run_official_collection",
        lambda connection, config, definition, callback: callback.keywords,
    )
    result = sources.collect_camara_history(
        None, tmp_path, ["canonical"], limit=4, proposition_ids=("123",) if explicit else ()
    )
    assert result["keys"] == (
        ["https://dadosabertos.camara.leg.br/api/v2/proposicoes/123"]
        if explicit
        else ["known-document"]
    )
    assert result["maximum"] == 4
    assert len(selected) == (0 if explicit else 1)


def test_camara_history_reuses_prepared_author_identity_resolver(monkeypatch):
    from crawlers.camara import author_identity

    resolver = object()
    calls = []
    monkeypatch.setattr(
        author_identity,
        "prepare_author_resolver",
        lambda *args: (resolver, {"identity_unresolved": 2}),
    )
    monkeypatch.setattr(
        sources,
        "collect_legislative_history",
        lambda *args, **kwargs: calls.append(kwargs) or ["document"],
    )
    result = sources.camara_pipeline(
        None, None, None, SimpleNamespace(connection=None), keys=["key"], maximum=4
    )
    assert calls == [{"resolve_person": resolver, "max_propositions": 4}]
    assert result["documents"] == ["document"]
    assert result["identity_unresolved"] == 2
    assert result["coverage"] == "known_documents_only"


@pytest.mark.parametrize("years", [[], [2024, 2025, 2026]])
def test_cmsp_adapter_prevents_unbounded_annual_backfill(tmp_path, years):
    with pytest.raises(ValueError, match="one or two municipal"):
        sources.collect_cmsp_history(None, tmp_path, years)


def test_cmsp_adapter_deduplicates_years_before_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(
        sources,
        "run_official_collection",
        lambda connection, config, definition, callback: callback.keywords,
    )
    assert sources.collect_cmsp_history(None, tmp_path, [2026, 2025, 2026])["years"] == (2025, 2026)


def test_municipal_summary_preserves_coverage_and_artifact_hash(monkeypatch):
    monkeypatch.setattr(
        sources,
        "collect_municipal_legislation",
        lambda *args, **kwargs: [
            {
                "ingestion": {"new": 1},
                "year": 2026,
                "domain": "proposals",
                "artifactSha256": "a" * 64,
                "coverage": "partial",
            }
        ],
    )
    result = sources.municipal_pipeline(None, None, None, None, years=(2026,), bindings=())
    assert result["artifacts"][0]["artifact_sha256"] == "a" * 64
    assert result["artifacts"][0]["coverage"] == "partial"
    assert result["identity_unresolved"] is True


@pytest.mark.parametrize(
    "federal,recent,fields,expected",
    [
        (False, False, [], False),
        (True, True, [], False),
        (True, True, ["political_activity"], True),
        (True, False, [], True),
    ],
)
def test_requested_gaps_override_profile_freshness_but_not_office_scope(
    federal, recent, fields, expected
):
    assert (
        enrichment.should_collect_candidate(
            {
                "has_federal_candidacy": federal,
                "recently_checked": recent,
                "requested_fields": fields,
            }
        )
        is expected
    )


@pytest.mark.parametrize("failure_status", [None, 429])
def test_enrichment_attempt_budget_and_source_errors_defer_remaining_people(
    monkeypatch, failure_status
):
    candidates = [
        {"person_id": str(value), "has_federal_candidacy": True, "recently_checked": False}
        for value in range(4)
    ]
    acquisition = SimpleNamespace(
        pages=lambda *args: [(["member"], None)], configuration=SimpleNamespace(max_people=1)
    )
    monkeypatch.setattr(enrichment, "index_current_members", lambda rows: rows)
    monkeypatch.setattr(
        enrichment,
        "select_member",
        lambda person, index: None if person["person_id"] == "3" else "member",
    )
    monkeypatch.setattr(enrichment, "emit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        enrichment, "describe_error", lambda _: {"code": "FAIL", "status": failure_status}
    )

    def fail(*args):
        raise IngestionError("FAIL")

    monkeypatch.setattr(enrichment, "enrich_person", fail)
    result = enrichment.collect_enrichment_plan(None, acquisition, candidates)
    assert len(result["failures"]) == 1
    assert result["deferred_person_ids"] == (["1", "2", "3"] if failure_status else ["1", "2"])
    assert result["unmatched_person_ids"] == ([] if failure_status else ["3"])


def test_successful_enrichment_records_coverage_after_verified_ingestion(monkeypatch):
    phases = []
    candidate = {"person_id": "canonical", "has_federal_candidacy": True, "recently_checked": False}
    acquisition = SimpleNamespace(
        pages=lambda *args: [([], None)], configuration=SimpleNamespace(max_people=1)
    )
    monkeypatch.setattr(enrichment, "index_current_members", lambda rows: {})
    monkeypatch.setattr(enrichment, "select_member", lambda *args: "member")
    monkeypatch.setattr(
        enrichment,
        "enrich_person",
        lambda *args: phases.append("ingest") or {"person_id": "canonical"},
    )
    monkeypatch.setattr(
        enrichment, "save_checked_coverage", lambda *args: phases.append("coverage")
    )
    monkeypatch.setattr(enrichment, "emit_event", lambda *args, **kwargs: None)
    assert enrichment.collect_enrichment_plan(None, acquisition, [candidate])["people"] == [
        {"person_id": "canonical"}
    ]
    assert phases == ["ingest", "coverage"]


def test_coverage_write_links_canonical_person_and_source_record():
    calls = []
    repository = SimpleNamespace(
        source_id="source",
        connection=SimpleNamespace(execute=lambda sql, params: calls.append((sql, params))),
    )
    enrichment.save_checked_coverage(repository, "canonical")
    assert calls[0][1] == ("canonical", "source", "canonical")
    assert "'partial'" in calls[0][0]


@pytest.mark.parametrize("failed,partial", [(False, False), (False, True), (True, False)])
def test_enrichment_runtime_finishes_durably_and_marks_exception_failed(
    monkeypatch, tmp_path, failed, partial
):
    states = []
    repository = SimpleNamespace(
        begin_run=lambda *args: states.append("begin"),
        finish_run=lambda state, result: states.append(state),
    )
    monkeypatch.setattr(enrichment, "IngestionRepository", lambda *args, **kwargs: repository)
    monkeypatch.setattr(enrichment, "SqlBatchWriter", lambda _: None)
    monkeypatch.setattr(enrichment, "CamaraProjectionWriter", lambda _: None)
    monkeypatch.setattr(enrichment, "OfficialHttpClient", lambda *args: None)
    monkeypatch.setattr(enrichment, "CamaraAcquisition", lambda *args: None)
    monkeypatch.setattr(enrichment.httpx, "Client", lambda **kwargs: nullcontext(None))

    def collect(*args):
        if failed:
            raise RuntimeError("offline")
        return {"failures": ["partial"] if partial else []}

    monkeypatch.setattr(enrichment, "collect_enrichment_plan", collect)
    if failed:
        with pytest.raises(RuntimeError, match="offline"):
            enrichment.run_camara_collection(None, tmp_path, [])
    else:
        enrichment.run_camara_collection(None, tmp_path, [])
    assert states == ["begin", "failed" if failed else "partial" if partial else "completed"]


def test_source_collection_failure_becomes_safe_structured_error(monkeypatch):
    monkeypatch.setattr(enrichment, "describe_error", lambda _: {"code": "OFFLINE_FAILURE"})
    monkeypatch.setattr(enrichment, "emit_event", lambda *args, **kwargs: None)

    def fail():
        raise RuntimeError("private internal detail")

    assert enrichment.execute_source_collection(fail) == {
        "status": "failed",
        "failures": [{"code": "OFFLINE_FAILURE"}],
    }
    assert enrichment.execute_source_collection(lambda: {"ok": True}) == {"ok": True}


def test_recent_checked_profile_without_requested_gap_skips_enrichment(monkeypatch):
    acquisition = SimpleNamespace(
        pages=lambda *args: [([], None)], configuration=SimpleNamespace(max_people=1)
    )
    monkeypatch.setattr(enrichment, "index_current_members", lambda rows: {})
    monkeypatch.setattr(
        enrichment,
        "select_member",
        lambda *args: pytest.fail("Recent complete profile must skip lookup"),
    )
    result = enrichment.collect_enrichment_plan(
        None,
        acquisition,
        [{"person_id": "canonical", "has_federal_candidacy": True, "recently_checked": True}],
    )
    assert result["people"] == []
    assert result["failures"] == []
    assert result["deferred"] == 0
