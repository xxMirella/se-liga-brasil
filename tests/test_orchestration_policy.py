from types import SimpleNamespace

from service.enrichment import pipeline
from service.ingestion.contracts import IngestionError
from service.orchestration.data_collection import release_deferred_people


def test_rate_limit_stops_remaining_people_in_same_source(monkeypatch):
    calls = []

    def blocked(*args):
        calls.append(args)
        raise IngestionError("HTTP_ERROR", {"status": 429, "retry_after_seconds": 120})

    members = [{"id": 1, "nome": "Pessoa Um"}, {"id": 2, "nome": "Pessoa Dois"}]
    candidates = [
        {
            "person_id": str(row["id"]),
            "civil_name": row["nome"],
            "display_name": row["nome"],
            "civil_names": [row["nome"]],
            "public_names": [],
            "recently_checked": False,
            "has_federal_candidacy": True,
        }
        for row in members
    ]
    acquisition = SimpleNamespace(
        configuration=SimpleNamespace(max_people=25), pages=lambda *args: iter([(members, None)])
    )
    monkeypatch.setattr(pipeline, "enrich_person", blocked)
    result = pipeline.collect_enrichment_plan(None, acquisition, candidates)
    assert len(calls) == 1
    assert result["deferred_person_ids"] == ["2"]
    assert result["failures"][0]["status"] == 429


def test_deferred_people_do_not_bypass_blocked_source_cooldown():
    class NoDatabaseCalls:
        def execute(self, *args):
            raise AssertionError("Cooldown must not be reset after a source failure")

    release_deferred_people(
        NoDatabaseCalls(), {"camara": {"failures": [{"status": 429}], "deferred_person_ids": ["p"]}}
    )


def test_salary_only_request_does_not_fetch_all_propositions(monkeypatch):
    from crawlers.camara import pipeline as camara

    monkeypatch.setattr(camara, "collect_person_profile", lambda *args: ({}, None))
    monkeypatch.setattr(camara, "ingest_collected", lambda *args: {})
    monkeypatch.setattr(camara, "collect_current_salary", lambda *args: {"collected": True})

    def unexpected(*args):
        raise AssertionError("Salary refresh must not fetch unrelated propositions")

    monkeypatch.setattr(camara, "collect_authored_propositions", unexpected)
    result = camara.enrich_person(
        None,
        SimpleNamespace(connection=None),
        {
            "person_id": "internal-person",
            "requested_fields": ["current_salary"],
        },
        {},
    )
    assert result["salary"] == {"collected": True}
    assert "propositions" not in result
