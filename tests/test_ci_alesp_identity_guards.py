"""Official identity review remains guarded against conflicting source evidence."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from crawlers.alesp import affiliations, identity, reviewed_identity
from service.ingestion.contracts import IngestionError


@pytest.fixture
def reviewed():
    case = {
        "source_subject_id": "10",
        "matricula": "20",
        "target_public_name": "Nome Público",
        "source_birthday": "29/02",
        "target_political_party_code": "01",
        "evidence_urls": ["https://www.al.sp.gov.br/evidence"],
    }
    profile = {
        "idParlamentar": 10,
        "nuMatricula": 20,
        "txNomeParlamentar": "NOME PUBLICO",
        "biografia": {"dtAniversario": "29/02"},
        "listaFiliacoes": [{"partido": {"nuLegenda": 1}}],
    }
    return case, profile


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("idParlamentar", 99, "REVIEWED_IDENTITY_SUBJECT_MISMATCH"),
        ("nuMatricula", 99, "REVIEWED_IDENTITY_SUBJECT_MISMATCH"),
        ("txNomeParlamentar", "Outra Pessoa", "REVIEWED_IDENTITY_PUBLIC_NAME_CHANGED"),
        ("biografia", {"dtAniversario": "01/01"}, "REVIEWED_SOURCE_BIRTHDAY_CHANGED"),
        ("listaFiliacoes", [], "REVIEWED_IDENTITY_PARTY_EVIDENCE_CHANGED"),
    ],
)
def test_reviewed_profile_requires_all_source_guards(reviewed, field, value, error):
    case, profile = reviewed
    with pytest.raises(IngestionError, match=error):
        reviewed_identity.validate_reviewed_profile(profile | {field: value}, case)


def test_review_resources_are_shared_and_suffix_matches_source_format(reviewed):
    case, _ = reviewed
    api = identity.PROFILE_BASE_URL + "21"
    cases = [case | {"evidence_urls": case["evidence_urls"] + [api]}, case]
    resources = reviewed_identity.plan_reviewed_resources(cases)
    assert len(resources) == 3
    assert resources[api].file_suffix == ".json"
    assert resources[case["evidence_urls"][0]].file_suffix == ".html"


def test_review_assembly_deduplicates_profile_and_evidence_urls(reviewed):
    case, profile = reviewed
    profile_url = identity.PROFILE_BASE_URL + "20"
    evidence_url = case["evidence_urls"][0]
    case = case | {"evidence_urls": [profile_url, evidence_url, evidence_url]}
    acquired = {
        profile_url: (json.dumps(profile).encode(), {"url": profile_url}),
        evidence_url: (b"html", {"url": evidence_url}),
    }
    result = reviewed_identity.assemble_reviewed_identity(
        case, {"reviewed_on": "2024-01-01", "scope": "official"}, acquired
    )
    assert result["sources"] == [{"url": profile_url}, {"url": evidence_url}]
    assert result["affiliations"] == profile["listaFiliacoes"]


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ({"status": "draft"}, "IDENTITY_MAPPING_NOT_REVIEWED"),
        ({"birth_date_changes_allowed": True}, "IDENTITY_MAPPING_CANNOT_CHANGE_BIRTH_DATE"),
    ],
)
def test_unreviewed_or_birth_mutating_registry_cannot_acquire(monkeypatch, change, error):
    registry = {"status": "reviewed_against_official_sources", "birth_date_changes_allowed": False}
    monkeypatch.setattr(reviewed_identity, "load_json", Mock(return_value=registry | change))
    acquire = Mock()
    monkeypatch.setattr(reviewed_identity, "acquire_identity_resource", acquire)
    with pytest.raises(IngestionError, match=error):
        reviewed_identity.collect_reviewed_identities(None, None)
    acquire.assert_not_called()


def test_reviewed_registry_acquires_shared_sources_once(monkeypatch, reviewed):
    case, profile = reviewed
    registry = {
        "status": "reviewed_against_official_sources",
        "birth_date_changes_allowed": False,
        "reviewed_on": "2024-01-01",
        "scope": "official",
        "exceptions": [case, case],
    }
    monkeypatch.setattr(reviewed_identity, "load_json", Mock(return_value=registry))

    def acquire(resource, configuration, client, budget):
        return json.dumps(profile).encode(), {"url": resource.url}

    acquire_mock = Mock(side_effect=acquire)
    monkeypatch.setattr(reviewed_identity, "acquire_identity_resource", acquire_mock)
    assert len(reviewed_identity.collect_reviewed_identities(None, None)) == 2
    assert acquire_mock.call_count == 2
    assert acquire_mock.call_args_list[0].args[3] is acquire_mock.call_args_list[1].args[3]


def test_affiliation_reports_preserve_unknown_end_boundary_and_source(reviewed, monkeypatch):
    case, _ = reviewed
    source = {"url": identity.PROFILE_BASE_URL + "20", "sha256": "hash"}
    subject = {
        "affiliations": [
            {"partido": {"nuLegenda": 1}, "dtInicio": "2020-01-01", "dtFim": "2021-02-01"},
            {"partido": {}, "dtInicio": "2020-01-01"},
            {"partido": {"nuLegenda": 2}},
        ],
        "sources": [source],
    }
    resolutions = [
        {"status": "ambiguous", "person_id": "excluded", "official_subjects": [subject]},
        {"status": "matched", "person_id": "one", "reviewed_crosswalk": subject},
    ]
    reports = affiliations.collect_affiliation_reports(resolutions)
    assert len(reports) == 1
    assert reports[0]["political_party_code"] == "01"
    assert reports[0]["end_boundary"] == "not_documented"
    assert reports[0]["reported_end_date"] == "2021-02-01"
    persist = Mock()
    monkeypatch.setattr(affiliations, "persist_party_evidence", persist)
    assert affiliations.save_alesp_affiliation_reports("db", 1, "url", resolutions) == 1
    assert persist.call_args.args[3] == reports


@pytest.mark.parametrize("field", ["dtInicio", "dtFim"])
def test_affiliation_invalid_report_dates_never_reach_projection(field):
    affiliation = {"partido": {"nuLegenda": 1}, "dtInicio": "2020-01-01", field: "2020-02-30"}
    with pytest.raises(ValueError):
        affiliations.normalize_subject_affiliations({"affiliations": [affiliation]}, "one")


@pytest.mark.parametrize("payload", [b"<broken", b"<Wrong/>", b"<Deputados/>"])
def test_identity_roster_rejects_malformed_or_empty_schema(payload):
    with pytest.raises(IngestionError, match="ALESP_IDENTITY_ROSTER_"):
        identity.parse_identity_roster(payload)


def test_identity_roster_rejects_missing_or_non_numeric_keys():
    payload = b"<Deputados><Deputado><IdDeputado>x</IdDeputado></Deputado></Deputados>"
    with pytest.raises(IngestionError, match="ALESP_IDENTITY_ROSTER_IDENTIFIER_MISSING"):
        identity.parse_identity_roster(payload)


def test_identity_roster_rejects_duplicate_subject_identifiers():
    member = "<Deputado><IdDeputado>1</IdDeputado><Matricula>2</Matricula><IdUA>3</IdUA></Deputado>"
    with pytest.raises(IngestionError, match="ALESP_IDENTITY_ROSTER_DUPLICATE_SUBJECT"):
        identity.parse_identity_roster(("<Deputados>" + member * 2 + "</Deputados>").encode())


@pytest.mark.parametrize(
    "profile",
    [{"listaFiliacoes": {}}, {"listaFiliacoes": [1]}, {"listaFiliacoes": [{"partido": 1}]}],
)
def test_current_party_rejects_schema_changes(profile):
    if profile == {"listaFiliacoes": {}}:
        profile = {"listaFiliacoes": {"unexpected": 1}}
    with pytest.raises(IngestionError, match="ALESP_IDENTITY_PROFILE_SCHEMA_CHANGED"):
        identity.current_party_code(profile)


def test_current_party_ignores_closed_affiliations_and_conflicting_current_codes():
    profile = {
        "listaFiliacoes": [
            {"partido": {"nuLegenda": 1}, "dtFim": "2020-01-01"},
            {"partido": {"nuLegenda": 2}},
        ]
    }
    assert identity.current_party_code(profile) == "02"
    profile["listaFiliacoes"].append({"partido": {"nuLegenda": 3}})
    assert identity.current_party_code(profile) is None


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        (b"invalid json", "ALESP_IDENTITY_PROFILE_INVALID_JSON"),
        (b"[]", "ALESP_IDENTITY_PROFILE_SUBJECT_MISMATCH"),
        (
            b'{"nuMatricula":2,"idParlamentar":1,"biografia":[1]}',
            "ALESP_IDENTITY_PROFILE_SCHEMA_CHANGED",
        ),
        (
            b'{"nuMatricula":2,"idParlamentar":1,"biografia":{"dtAniversario":"11/05"}}',
            "ALESP_IDENTITY_BIRTHDAY_CONFLICT",
        ),
    ],
)
def test_member_profile_guards_identifiers_schema_and_birthday(payload, error):
    member = {"Matricula": "2", "IdDeputado": "1", "Aniversario": "10/05"}
    with pytest.raises(IngestionError, match=error):
        identity.parse_member_profile(payload, member)


@pytest.mark.parametrize(
    ("html", "error"),
    [
        ("<p>Responsável:</p>", "ALESP_TELEPHONE_RESPONSIBLE_AMBIGUOUS"),
        (
            '<p>Responsável: Pessoa</p><a href="/deputado/?matricula=99">link</a>',
            "ALESP_TELEPHONE_MATRICULA_MISMATCH",
        ),
        ("<p>Responsável: Pessoa</p>", "ALESP_TELEPHONE_GABINET_MISSING"),
    ],
)
def test_telephone_evidence_guards_responsible_identity_and_office(html, error):
    with pytest.raises(IngestionError, match=error):
        identity.parse_telephone_evidence(html.encode(), "2")


def test_source_errors_preserve_safe_codes_but_exhausted_download_budget_is_fatal(monkeypatch):
    member = {"IdDeputado": "1", "Matricula": "2", "IdUA": "3"}
    acquire = Mock(side_effect=IngestionError("HTTP_UNAVAILABLE"))
    monkeypatch.setattr(identity, "acquire_identity_resource", acquire)
    result = identity.collect_member_evidence(member, {}, None, None, None)
    assert [row["code"] for row in result["source_errors"]] == ["HTTP_UNAVAILABLE"] * 2
    acquire.side_effect = IngestionError("RUN_DOWNLOAD_LIMIT_EXCEEDED")
    with pytest.raises(IngestionError, match="RUN_DOWNLOAD_LIMIT_EXCEEDED"):
        identity.collect_member_evidence(member, {}, None, None, None)


def test_identity_collection_persists_progress_with_shared_download_budget(monkeypatch, tmp_path):
    member = {"Matricula": "2"}
    monkeypatch.setattr(identity, "acquire_identity_resource", Mock(return_value=(b"roster", {})))
    monkeypatch.setattr(identity, "parse_identity_roster", Mock(return_value=[member, member]))
    collect = Mock(return_value={"legal_name": "Pessoa"})
    monkeypatch.setattr(identity, "collect_member_evidence", collect)
    save = Mock()
    monkeypatch.setattr(identity, "save_json", save)
    assert (
        len(identity.collect_identity_evidence(SimpleNamespace(storage_directory=tmp_path), None))
        == 2
    )
    assert save.call_count == 2
    assert collect.call_args_list[0].args[-1] is collect.call_args_list[1].args[-1]


def test_acquired_identity_resource_preserves_download_provenance(monkeypatch, tmp_path):
    path = tmp_path / "original"
    path.write_bytes(b"official payload")
    artifact = SimpleNamespace(
        path=path, sha256="hash", fetched_at="2024-01-01", acquisition_status="cached"
    )
    monkeypatch.setattr(identity, "download_resource", Mock(return_value=artifact))
    resource = identity.identity_resource("one", "https://www.al.sp.gov.br/profile", ".json")
    payload, source = identity.acquire_identity_resource(resource, "config", "client", "budget")
    assert payload == b"official payload"
    assert source == {
        "url": resource.url,
        "path": str(path),
        "sha256": "hash",
        "fetched_at": "2024-01-01",
        "acquisition_status": "cached",
    }


def test_combined_member_evidence_retains_distinct_sources_and_confirmed_membership(monkeypatch):
    member = {"IdDeputado": "1", "Matricula": "2", "IdUA": "3", "NomeParlamentar": "Nome Público"}
    profile = {
        "idParlamentar": 1,
        "nuMatricula": 2,
        "isEmExercicio": True,
        "biografia": {"dtAniversario": "10/05"},
    }
    telephone = (
        "<h5>GABINETE DEP. Nome Público</h5><p>Responsável: Nome Civil</p>"
        '<p>Cargo: Deputado(a)</p><a href="/deputado/?matricula=2">Perfil</a>'
    )
    acquire = Mock(
        side_effect=[
            (json.dumps(profile).encode(), {"url": "profile"}),
            (telephone.encode(), {"url": "telephone"}),
        ]
    )
    monkeypatch.setattr(identity, "acquire_identity_resource", acquire)
    result = identity.collect_member_evidence(member, {"url": "roster"}, None, None, None)
    assert result["legal_name"] == "Nome Civil" and result["is_in_office"] is True
    assert result["membership_evidence"]["profile_link_confirmed"] is True
    assert result["membership_evidence"]["role_deputy_confirmed"] is True
    assert len(result["sources"]) == 3 and not result["source_errors"]
