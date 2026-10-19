"""Institution-specific identity and bounded collection behavior without external I/O."""

from contextlib import nullcontext
from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace

import pytest

from crawlers.alerj import pipeline as alerj
from crawlers.senado import pipeline as senate
from crawlers.senado import voting_pipeline as votes
from normalization.identity import normalize_person_name
from service.ingestion.contracts import DownloadedArtifact, IngestionError, Resource


def member(name="Pessoa Teste", code="1"):
    return {
        "IdentificacaoParlamentar": {"NomeCompletoParlamentar": name, "CodigoParlamentar": code}
    }


@pytest.fixture
def evidence(tmp_path):
    path = tmp_path / "original.html"
    path.write_bytes(b"original")
    resource = Resource("id", "original", "https://example.invalid", "profile", 2026, "institution")
    return DownloadedArtifact(resource, path, "a" * 64, "2026-05-27T12:00:00Z", 8)


@pytest.mark.parametrize("module", [alerj, senate])
def test_unsupported_fields_do_not_construct_repository(module, tmp_path):
    if module is alerj:
        result = module.collect_alerj_enrichment(None, tmp_path, [{}], ["attendance"])
    else:
        result = module.collect_senado_enrichment(None, tmp_path, [{}], ["attendance"])
    assert result["people"] == []
    assert result["unsupported_fields"] == ["attendance"]


def test_alerj_empty_scope_requires_no_network(tmp_path):
    assert alerj.collect_alerj_enrichment(None, tmp_path, []) == {
        "status": "completed",
        "people": [],
        "deferred_person_ids": [],
    }


def test_name_prefilter_does_not_resolve_ambiguous_people():
    people = [
        {"person_id": "one", "civil_name": "Pessoa Teste"},
        {"person_id": "two", "display_name": "Pessoa Teste"},
    ]
    assert alerj.match_roster_targets([{"display_name": "Pessoa Teste"}], people) == []
    people[1]["display_name"] = "Outra Pessoa"
    assert (
        alerj.match_roster_targets([{"display_name": "PESSOA TESTE"}], people)[0][0]["person_id"]
        == "one"
    )


@pytest.mark.parametrize("payroll", [{}, {"PESSOA TESTE": {}, "OUTRO NOME": {}}])
def test_alerj_salary_requires_exactly_one_civil_name_match(payroll):
    with pytest.raises(IngestionError, match="IDENTITY_REVIEW_REQUIRED"):
        alerj.select_person_payroll(
            {"civil_name": "Pessoa Teste", "civil_names": ["Outro Nome"]},
            {normalize_person_name(key): value for key, value in payroll.items()},
        )


def test_alerj_shared_evidence_skips_payroll_when_no_roster_target(monkeypatch, evidence):
    calls = []
    acquisition = SimpleNamespace(acquire=lambda *args: calls.append(args) or evidence)
    monkeypatch.setattr(alerj, "parse_roster", lambda _: [{"display_name": "Unknown"}])
    members, targets, payroll, document, roster = alerj.collect_shared_evidence(acquisition, [])
    assert len(members) == 1
    assert (targets, payroll, document, roster) == ([], {}, None, evidence)
    assert len(calls) == 1


@pytest.mark.parametrize("actual_month", ["2026-05", "2026-04"])
def test_alerj_shared_payroll_rejects_wrong_competence(monkeypatch, evidence, actual_month):
    monkeypatch.setattr(alerj, "parse_roster", lambda _: [{"display_name": "Pessoa Teste"}])
    monkeypatch.setattr(
        alerj, "latest_payroll_document", lambda _: ("2026-05", "https://example.invalid/payroll")
    )
    monkeypatch.setattr(alerj, "extract_pdf_text", lambda _: "text")
    monkeypatch.setattr(
        alerj, "parse_deputy_payroll", lambda _: {"PESSOA TESTE": {"competence": actual_month}}
    )
    acquisition = SimpleNamespace(acquire=lambda *args: evidence)
    if actual_month != "2026-05":
        with pytest.raises(IngestionError, match="COMPETENCE_MISMATCH"):
            alerj.collect_shared_evidence(
                acquisition, [{"person_id": "one", "civil_name": "Pessoa Teste"}]
            )
    else:
        result = alerj.collect_shared_evidence(
            acquisition, [{"person_id": "one", "civil_name": "Pessoa Teste"}]
        )
        assert result[1][0][0]["person_id"] == "one"
        assert result[3] is evidence


@pytest.mark.parametrize("code", ["IDENTITY_MISMATCH", "HTTP_ERROR", "SOURCE_COOLDOWN_ACTIVE"])
def test_alerj_continues_identity_errors_but_stops_source_failures(monkeypatch, code):
    people = [{"person_id": "one"}, {"person_id": "two"}, {"person_id": "unmatched"}]
    targets = [(people[0], {}), (people[1], {})]
    monkeypatch.setattr(
        alerj, "collect_shared_evidence", lambda *args: ([{}, {}], targets, {}, None, None)
    )

    def fail(*args):
        raise IngestionError(code)

    monkeypatch.setattr(alerj, "collect_verified_person", fail)
    acquisition = SimpleNamespace(configuration=SimpleNamespace(max_people=1))
    if code != "IDENTITY_MISMATCH":
        with pytest.raises(IngestionError, match=code):
            alerj.collect_targets(acquisition, None, people)
    else:
        result = alerj.collect_targets(acquisition, None, people)
        assert result["identity_unresolved"] == [{"person_id": "one", "reason": code}]
        assert result["deferred_person_ids"] == ["two"]
        assert result["unmatched_person_ids"] == ["unmatched"]
        assert result["status"] == "partial"


def test_senate_member_aliases_deduplicate_same_person_but_not_homonyms():
    first = member()
    index = senate.index_members([first, member(code="2")])
    assert senate.select_member({"civil_name": "Pessoa Teste"}, index) is None
    index = senate.index_members([first])
    assert (
        senate.select_member({"civil_name": "Pessoa Teste", "civil_names": ["PESSOA TESTE"]}, index)
        == first
    )
    assert senate.select_member({"civil_name": None}, index) is None


@pytest.mark.parametrize("failure_status", [None, 429])
def test_senate_profile_budget_counts_failed_attempts_and_defers_after_rate_limit(
    monkeypatch, failure_status
):
    people = [{"person_id": str(number), "civil_name": f"Pessoa {number}"} for number in range(4)]
    members = [member(f"Pessoa {number}", str(number)) for number in range(3)]
    monkeypatch.setattr(senate, "current_members", lambda _: members)
    monkeypatch.setattr(
        senate, "describe_error", lambda _: {"code": "FAIL", "status": failure_status}
    )
    calls = []

    def collect(repository, acquisition, person, *args):
        calls.append(person["person_id"])
        raise IngestionError("FAIL")

    monkeypatch.setattr(senate, "collect_profile", collect)
    acquisition = SimpleNamespace(
        json_document=lambda *args: ({}, None), configuration=SimpleNamespace(max_people=1)
    )
    result = senate.collect_profiles(None, acquisition, people)
    assert calls == ["0"]
    assert result["deferred_person_ids"] == (["1", "2", "3"] if failure_status else ["1", "2"])
    assert result["unmatched_person_ids"] == ([] if failure_status else ["3"])


def test_senate_profile_success_is_recorded(monkeypatch):
    monkeypatch.setattr(senate, "current_members", lambda _: [member()])
    monkeypatch.setattr(senate, "collect_profile", lambda *args: {"person_id": "one"})
    acquisition = SimpleNamespace(
        json_document=lambda *args: ({}, None), configuration=SimpleNamespace(max_people=1)
    )
    assert senate.collect_profiles(
        None, acquisition, [{"person_id": "one", "civil_name": "Pessoa Teste"}]
    )["people"] == [{"person_id": "one"}]


@pytest.mark.parametrize(
    "module,failed", [(alerj, False), (alerj, True), (senate, False), (senate, True)]
)
def test_institution_run_lifecycle_marks_failure_and_reraises(
    monkeypatch, tmp_path, module, failed
):
    states = []
    repository = SimpleNamespace(
        begin_run=lambda *args: states.append("begin"),
        finish_run=lambda state, result: states.append(state),
    )
    monkeypatch.setattr(module, "IngestionRepository", lambda *args, **kwargs: repository)
    monkeypatch.setattr(module, "SqlBatchWriter", lambda _: None)
    monkeypatch.setattr(module, "OfficialHttpClient", lambda *args: None)
    monkeypatch.setattr(module.httpx, "Client", lambda **kwargs: nullcontext(None))

    def collect(*args):
        if failed:
            raise RuntimeError("offline failure")
        return {"status": "completed", "people": [], "failures": []}

    if module is alerj:
        monkeypatch.setattr(module, "AlerjProjectionWriter", lambda _: None)
        monkeypatch.setattr(module, "AlerjAcquisition", lambda *args: None)
        monkeypatch.setattr(module, "collect_targets", collect)
        invoke = module.collect_alerj_enrichment
    else:
        monkeypatch.setattr(module, "SenateProjectionWriter", lambda _: None)
        monkeypatch.setattr(module, "SenateAcquisition", lambda *args: None)
        monkeypatch.setattr(module, "collect_profiles", collect)
        invoke = module.collect_senado_enrichment
    if failed:
        with pytest.raises(RuntimeError, match="offline failure"):
            invoke(None, tmp_path, [{}])
    else:
        assert invoke(None, tmp_path, [{}])["people"] == []
    assert states == ["begin", "failed" if failed else "completed"]


@pytest.mark.parametrize("maximum", [0, 10001])
def test_senate_voting_budget_invalid_before_collection(tmp_path, maximum):
    with pytest.raises(IngestionError, match="RECORD_LIMIT_EXCEEDED"):
        votes.collect_senate_voting_partitions(
            None, tmp_path, date(2026, 5, 1), date(2026, 5, 2), max_votings=maximum
        )


def test_senate_cached_profiles_reused_when_no_explicit_profiles(monkeypatch, tmp_path):
    effects = []
    monkeypatch.setattr(
        votes, "cached_identity_profiles", lambda storage: effects.append("cache") or ["profile"]
    )
    monkeypatch.setattr(
        votes,
        "resolve_profile_identities",
        lambda connection, profiles: effects.append(profiles) or {},
    )
    monkeypatch.setattr(
        votes.IdentityProfileAcquisition,
        "mark_cached_profiles",
        lambda self, profiles, config: effects.append("marked"),
    )
    monkeypatch.setattr(votes, "run_official_collection", lambda *args: {"ready": True})
    assert votes.collect_senate_voting_partitions(
        None, tmp_path, date(2026, 5, 1), date(2026, 5, 2)
    ) == {"ready": True}
    assert effects == ["cache", ["profile"], "marked"]


def test_senate_explicit_empty_identity_list_does_not_read_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(
        votes,
        "cached_identity_profiles",
        lambda _: pytest.fail("Explicit identity scope must prevail"),
    )
    monkeypatch.setattr(votes, "resolve_profile_identities", lambda *args: {})
    monkeypatch.setattr(
        votes.IdentityProfileAcquisition, "mark_cached_profiles", lambda *args: None
    )
    monkeypatch.setattr(votes, "run_official_collection", lambda *args: {"ready": True})
    assert votes.collect_senate_voting_partitions(
        None, tmp_path, date(2026, 5, 1), date(2026, 5, 2), identity_profiles=[]
    )["ready"]


@dataclass
class Summary:
    new: int = 1


def test_senate_voting_ingests_resolved_votes_and_retains_unresolved_count(
    monkeypatch, tmp_path, evidence
):
    phases = []
    monkeypatch.setattr(votes, "select_unique_votings", lambda *args: ["row"])
    monkeypatch.setattr(votes, "normalize_voting_record", lambda row: {"source_key": "vote"})
    monkeypatch.setattr(votes, "resolve_voting_individuals", lambda *args: (["resolved-vote"], 2))
    monkeypatch.setattr(
        votes, "stage_voting_records", lambda *args: phases.append("stage") or "staged"
    )
    repository = SimpleNamespace(
        connection=None,
        ingest_validated_artifact=lambda staged, size: phases.append((staged, size)) or Summary(),
    )
    acquisition = SimpleNamespace(json_document=lambda *args: ({}, evidence))
    profile_acquisition = SimpleNamespace(
        extend_resolved_index=lambda *args: phases.append("identify"),
        summary=lambda: {"profiles_downloaded": 0},
    )
    result = votes.ingest_voting_partitions(
        None,
        SimpleNamespace(storage_directory=tmp_path, batch_size=10),
        acquisition,
        repository,
        partitions=[(date(2026, 5, 1), date(2026, 5, 27))],
        profile_index={"source": ("canonical", "verified")},
        maximum=100,
        profile_acquisition=profile_acquisition,
    )
    assert phases == ["identify", "stage", ("staged", 10)]
    assert result["identity_unresolved"] == 2
    assert result["resolved_person_ids"] == ["canonical"]
    assert result["artifacts"][0]["checked_on"] == "2026-05-27"
    assert result["artifacts"][0]["resolved_votes"] == 1


def test_senate_voting_deduplication_detects_conflicts_and_scope_errors(monkeypatch):
    monkeypatch.setattr(votes, "normalize_voting_record", lambda row: row)
    first = {"source_key": "one", "occurred_on": "2026-05-27", "choice": "yes"}
    seen = {}
    start, end = date(2026, 5, 1), date(2026, 5, 27)
    assert votes.select_unique_votings([first, first], seen, start, end, 1) == [first]
    cases = [
        ({}, "SCHEMA_CHANGED"),
        ([first | {"occurred_on": "2026-04-30"}], "OUTSIDE_PARTITION"),
        ([first | {"choice": "no"}], "SNAPSHOT_CONFLICT"),
        ([first | {"source_key": "two"}], "RECORD_LIMIT_EXCEEDED"),
    ]
    for payload, code in cases:
        with pytest.raises(IngestionError, match=code):
            votes.select_unique_votings(payload, seen, start, end, 1)


@pytest.mark.parametrize(
    "start,end,maximum,code",
    [
        (date(2026, 5, 2), date(2026, 5, 1), 1, "INVALID_SENATE_VOTING_SCOPE"),
        (date(2026, 5, 1), date(2026, 5, 2), 0, "INVALID_SENATE_VOTING_SCOPE"),
        (date(2026, 5, 1), date(2026, 6, 2), 1, "PARTITION_LIMIT_EXCEEDED"),
    ],
)
def test_senate_monthly_scope_never_silently_truncates(start, end, maximum, code):
    with pytest.raises(IngestionError, match=code):
        votes.monthly_partitions(start, end, maximum)


def test_alerj_verified_profile_links_salary_and_three_source_evidences(
    monkeypatch, tmp_path, evidence
):
    captured = []
    acquisition = SimpleNamespace(
        configuration=SimpleNamespace(storage_directory=tmp_path), acquire=lambda *args: evidence
    )
    repository = SimpleNamespace(connection=None)
    monkeypatch.setattr(alerj, "parse_profile", lambda *args: {"birthDate": "1980-01-01"})
    monkeypatch.setattr(
        alerj, "match_official_person", lambda connection, profile, expected: "verified-name-birth"
    )
    monkeypatch.setattr(
        alerj,
        "ingest_records",
        lambda repository, acquisition, artifact, rows: (
            captured.append((artifact, rows[0])) or {"new": 1}
        ),
    )
    result = alerj.collect_verified_person(
        acquisition,
        repository,
        {"person_id": "canonical", "civil_name": "Pessoa Teste"},
        {"url": "https://example.invalid", "display_name": "Pessoa Teste"},
        {normalize_person_name("Pessoa Teste"): {"recipientName": "Pessoa Teste"}},
        evidence,
        evidence,
    )
    assert result["person_id"] == "canonical"
    assert len(captured[0][1]["evidence"]) == 3
    assert captured[0][1]["observedOn"] == "2026-05-27"
    assert captured[1][1]["recipientKey"] == "canonical"
    bundle = alerj.bundle_profile_evidence(acquisition, [evidence, evidence, evidence])
    assert bundle.path == captured[0][0].path
    assert bundle.path.read_bytes() == captured[0][0].path.read_bytes()


def test_alerj_ingestion_uses_configured_batch_size(monkeypatch):
    monkeypatch.setattr(alerj, "stage_records", lambda *args: "validated")
    repository = SimpleNamespace(
        ingest_validated_artifact=lambda artifact, size: (
            Summary(size) if artifact == "validated" else None
        )
    )
    assert alerj.ingest_records(
        repository, SimpleNamespace(configuration=SimpleNamespace(batch_size=17)), None, []
    ) == {"new": 17}


def test_senate_verified_profile_is_staged_only_after_person_match(monkeypatch, evidence):
    phases, staged = [], []
    profile = member() | {"DadosBasicosParlamentar": {"DataNascimento": "1980-01-01"}}
    acquisition = SimpleNamespace(
        configuration=SimpleNamespace(batch_size=10),
        json_document=lambda *args: ({"DetalheParlamentar": {"Parlamentar": profile}}, evidence),
    )
    repository = SimpleNamespace(connection=None, ingest_validated_artifact=lambda *args: Summary())
    monkeypatch.setattr(
        senate, "match_official_person", lambda *args: phases.append("verified") or "name-birth"
    )
    monkeypatch.setattr(
        senate, "normalize_profile", lambda *args: {"personId": args[2], "observedOn": args[4]}
    )
    monkeypatch.setattr(senate, "bundle_artifacts", lambda *args: evidence)
    monkeypatch.setattr(
        senate,
        "stage_records",
        lambda artifact, config, rows: phases.append("staged") or staged.append(rows[0]),
    )
    result = senate.collect_profile(
        repository, acquisition, {"person_id": "canonical"}, member(), evidence
    )
    assert phases == ["verified", "staged"]
    assert result == {"person_id": "canonical", "new": 1}
    assert staged[0]["observedOn"] == "2026-05-27"
    assert len(staged[0]["evidence"]) == 2
