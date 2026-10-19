"""Câmara helper contracts reject weak identity fallback and misleading voting evidence."""

import hashlib
import json
from datetime import date
from types import SimpleNamespace

import pytest

from crawlers.camara import acquisition, voting_acquisition, voting_identity, voting_normalization
from crawlers.camara.configuration import API_BASE
from service.ingestion.contracts import DownloadedArtifact, IngestionError, Resource


def event(key="1", **updates):
    return {"id": key, "uri": API_BASE + "votacoes/" + key, "data": "2026-05-01"} | updates


def profile_artifact(tmp_path, *, key="1", url=None, profile=None):
    body = (
        {"id": key, "nomeCivil": "Pessoa Teste", "dataNascimento": "1980-01-01"}
        if profile is None
        else profile
    )
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"dados": body}))
    resource = Resource(
        "resource", "profile", url or API_BASE + "deputados/" + key, "profile", 2026, "camara"
    )
    return DownloadedArtifact(
        resource,
        path,
        hashlib.sha256(path.read_bytes()).hexdigest(),
        "2026-05-01T00:00:00Z",
        path.stat().st_size,
    )


@pytest.mark.parametrize(
    "row", [{}, {"deputado_": None}, {"deputado_": []}, {"deputado_": {"id": None}}]
)
def test_voter_without_profile_key_does_not_invent_identity(row):
    assert voting_identity.voter_profile_key(row) is None


def test_profile_requests_deduplicate_and_reject_malformed_person_vote():
    assert voting_identity.requested_profile_keys(
        [{"votes": [{"deputado_": {"id": "1"}}, {"deputado_": {"id": "1"}}, {}]}]
    ) == {"1"}
    with pytest.raises(IngestionError, match="PERSON_VOTE_SCHEMA_CHANGED"):
        voting_identity.requested_profile_keys([{"votes": [None]}])


@pytest.mark.parametrize(
    "url", [API_BASE + "deputados/0", "https://www.camara.leg.br/api/v2/deputados/1"]
)
def test_identity_profile_requires_exact_api_resource_path(tmp_path, url):
    artifact = profile_artifact(tmp_path, url=url)
    with pytest.raises(IngestionError, match="UNTRUSTED_CAMARA_IDENTITY_PROFILE"):
        voting_identity.profile_evidence(artifact)


def test_identity_rejects_mutated_archive_and_mismatched_profile_subject(tmp_path):
    artifact = profile_artifact(tmp_path, profile={"id": "2"})
    with pytest.raises(IngestionError, match="PROFILE_KEY_MISMATCH"):
        voting_identity.profile_evidence(artifact)
    artifact.path.write_text("{}")
    with pytest.raises(IngestionError, match="ARTIFACT_CHANGED"):
        voting_identity.profile_evidence(artifact)


def test_identity_without_birth_evidence_is_not_usable(tmp_path):
    assert (
        voting_identity.profile_evidence(
            profile_artifact(tmp_path, profile={"id": "1", "nomeCivil": "Pessoa Teste"})
        )
        is None
    )


@pytest.mark.parametrize("cpf", [None, "invalid", "00000000000"])
def test_invalid_or_absent_document_cannot_produce_identity_fingerprint(cpf):
    assert voting_identity.profile_document_fingerprint({"cpf": cpf}) is None


def test_valid_document_fingerprint_uses_private_builder_without_persisting_document(monkeypatch):
    from normalization import identity

    captured = []
    monkeypatch.setattr(identity, "normalize_cpf", lambda value: "validated-document")
    monkeypatch.setattr(voting_identity, "load_identity_key", lambda: b"offline-key")
    monkeypatch.setattr(
        voting_identity,
        "IdentityEvidenceBuilder",
        lambda key: SimpleNamespace(
            build_evidence=lambda name, **kwargs: (
                captured.append((name, kwargs)) or {"documentFingerprint": "fingerprint"}
            )
        ),
    )
    assert (
        voting_identity.profile_document_fingerprint({"cpf": "input", "nomeCivil": "Pessoa Teste"})
        == "fingerprint"
    )
    assert captured == [("Pessoa Teste", {"cpf": "validated-document"})]


@pytest.mark.parametrize("document_match", [None, "canonical-by-document"])
def test_document_present_never_falls_back_to_weaker_name_match(monkeypatch, document_match):
    evidence = {
        "transient_key": "1",
        "document_fingerprint": "fingerprint",
        "normalized_name": "person",
        "birth_date": "1980-01-01",
        "artifact": "artifact",
    }
    monkeypatch.setattr(voting_identity, "profile_evidence", lambda _: evidence)
    monkeypatch.setattr(
        voting_identity,
        "lookup_unique_people_by_document",
        lambda *args: {"fingerprint": document_match} if document_match else {},
    )
    calls = []
    monkeypatch.setattr(
        voting_identity,
        "lookup_unique_people_by_name_birth",
        lambda connection, rows: calls.append(rows) or {("person", "1980-01-01"): "wrong-person"},
    )
    result = voting_identity.resolve_voting_people(None, {"1": "artifact"})
    assert calls == [[]]
    assert result == (
        {}
        if document_match is None
        else {"1": {"person_id": document_match, "artifact": "artifact"}}
    )


def test_identity_profile_budget_uses_cache_before_network_and_counts_deferred(monkeypatch):
    monkeypatch.setattr(
        voting_identity,
        "cached_profile_artifact",
        lambda config, key: "cached" if key == "2" else None,
    )
    acquisition = SimpleNamespace(json_document=lambda path, kind: ({}, "downloaded"))
    config = SimpleNamespace(max_identity_profiles=1)
    events = [{"votes": [{"deputado_": {"id": key}} for key in ["1", "2", "3"]]}]
    artifacts, summary = voting_identity.collect_identity_profiles(acquisition, events, config)
    assert artifacts == {"1": "downloaded", "2": "cached"}
    assert summary == {"identity_profile_requests": 1, "identity_profiles_deferred": 1}


def test_supplied_identity_profile_only_reused_for_requested_subject(monkeypatch):
    monkeypatch.setattr(
        voting_identity, "profile_evidence", lambda artifact: {"transient_key": artifact}
    )
    monkeypatch.setattr(
        voting_identity,
        "cached_profile_artifact",
        lambda *args: pytest.fail("Supplied profile should avoid cache lookup"),
    )
    artifacts, summary = voting_identity.collect_identity_profiles(
        None,
        [{"votes": [{"deputado_": {"id": "1"}}]}],
        SimpleNamespace(max_identity_profiles=0),
        supplied=("1", "2"),
    )
    assert artifacts == {"1": "1"}
    assert summary["identity_profile_requests"] == 0


@pytest.mark.parametrize(
    "updates,code",
    [
        ({"id": "../escape"}, "INVALID_CAMARA_VOTING_IDENTIFIER"),
        ({"uri": "https://attacker.invalid"}, "URI_MISMATCH"),
    ],
)
def test_voting_identifier_rejects_path_or_uri_substitution(updates, code):
    with pytest.raises(IngestionError, match=code):
        voting_normalization.voting_identifier(event(**updates))


@pytest.mark.parametrize(
    "discovered,detailed,code",
    [
        (event(), event("2"), "DETAIL_MISMATCH"),
        (event(data="bad"), event(data="bad"), "DATE_CHANGED"),
    ],
)
def test_voting_detail_must_match_discovery_and_valid_date(discovered, detailed, code):
    with pytest.raises(IngestionError, match=code):
        voting_normalization.normalize_voting_event(discovered, detailed)


@pytest.mark.parametrize(
    "uri",
    [
        API_BASE + "proposicoes/../private",
        "https://attacker.invalid/proposicoes/1",
        API_BASE + "proposicoes/0",
    ],
)
def test_matter_uri_only_accepts_positive_document_keys_on_official_api(uri):
    with pytest.raises(IngestionError, match="PROPOSITION_URI_MISMATCH"):
        voting_normalization.identified_matter_uri({"uriProposicaoObjeto": uri})


@pytest.mark.parametrize("year", [True, "2026", 1700])
def test_matter_year_schema_change_is_explicit(year):
    with pytest.raises(IngestionError, match="PROPOSITION_YEAR_CHANGED"):
        voting_normalization.matter_fields({"ano": year}, None)


def test_multiple_affected_matters_do_not_create_guessed_relationship():
    assert (
        voting_normalization.related_matter_uri(
            {
                "discovery": {},
                "detail": {
                    "proposicoesAfetadas": [
                        {"uri": API_BASE + "proposicoes/1"},
                        {"uri": API_BASE + "proposicoes/2"},
                    ]
                },
            }
        )
        is None
    )


@pytest.mark.parametrize(
    "row,code",
    [(event(data="bad"), "DATE_CHANGED"), (event(data="2026-04-30"), "OUTSIDE_PARTITION")],
)
def test_discovered_vote_date_cannot_escape_interval(row, code):
    with pytest.raises(IngestionError, match=code):
        voting_acquisition.validate_discovered_voting(row, date(2026, 5, 1), date(2026, 5, 2))


def test_discovery_duplicates_are_skipped_but_changed_same_key_rejected():
    selected, seen = [], {}
    row = event()
    assert (
        voting_acquisition.select_discovery_page(
            [row, row], selected, seen, date(2026, 5, 1), date(2026, 5, 2), 1
        )
        is False
    )
    assert selected == [row]
    with pytest.raises(IngestionError, match="SNAPSHOT_CONFLICT"):
        voting_acquisition.select_discovery_page(
            [row | {"description": "changed"}],
            selected,
            seen,
            date(2026, 5, 1),
            date(2026, 5, 2),
            1,
        )
    assert (
        voting_acquisition.select_discovery_page(
            [event("2")], selected, seen, date(2026, 5, 1), date(2026, 5, 2), 1
        )
        is True
    )


@pytest.mark.parametrize(
    "detail,max_votes,code",
    [
        ({"dados": []}, 100, "DETAIL_SCHEMA_CHANGED"),
        ({"dados": event()}, 0, "PERSON_VOTE_BUDGET_EXCEEDED"),
    ],
)
def test_detail_and_vote_budget_fail_before_staging(detail, max_votes, code):
    acquisition = SimpleNamespace(
        json_document=lambda *args: (detail, None), pages=lambda *args: [([{}], None)]
    )
    with pytest.raises(IngestionError, match=code):
        voting_acquisition.collect_voting_documents(acquisition, [event()], max_votes)


@pytest.mark.parametrize("embedded", [True, False])
def test_embedded_matter_reuses_evidence_and_deduplicates_shared_document(embedded):
    uri = API_BASE + "proposicoes/1"
    data = {"uri": uri, "ementa": "Official text"}
    item = {
        "discovery": {"uriProposicaoObjeto": uri},
        "detail": {"objetosPossiveis": [data] if embedded else []},
    }
    calls = []
    acquisition = SimpleNamespace(
        json_document=lambda *args: calls.append(args) or ({"dados": data}, "artifact")
    )
    matters, artifacts, deferred = voting_acquisition.collect_identified_matters(
        acquisition, [item, item], 1
    )
    assert matters == {uri: data}
    assert len(calls) == (0 if embedded else 1)
    assert len(artifacts) == (0 if embedded else 1)
    assert deferred == 0


def test_matter_budget_defers_once_and_bad_response_is_not_projected():
    uri = API_BASE + "proposicoes/1"
    item = {"discovery": {"uriProposicaoObjeto": uri}, "detail": {}}
    acquisition = SimpleNamespace(json_document=lambda *args: ({"dados": {"uri": "wrong"}}, None))
    assert voting_acquisition.collect_identified_matters(acquisition, [item, item], 0) == (
        {},
        {},
        1,
    )
    with pytest.raises(IngestionError, match="PROPOSITION_SCHEMA_CHANGED"):
        voting_acquisition.collect_identified_matters(acquisition, [item], 1)


def test_camara_acquisition_download_reuses_one_shared_budget(monkeypatch):
    calls = []
    monkeypatch.setattr(
        acquisition, "download_resource", lambda *args: calls.append(args) or "artifact"
    )
    source = acquisition.CamaraAcquisition("config", "client")
    assert source.acquire(API_BASE + "deputados/1", "profile") == "artifact"
    assert source.acquire(API_BASE + "deputados/2", "profile") == "artifact"
    assert calls[0][3] is calls[1][3] is source.budget
    assert calls[0][0].url == API_BASE + "deputados/1"


@pytest.mark.parametrize(
    "mode,code",
    [
        ("cycle", "PAGINATION_CYCLE"),
        ("schema", "API_SCHEMA_CHANGED"),
        ("budget", "PAGE_LIMIT_EXCEEDED"),
    ],
)
def test_camara_pagination_cycle_schema_and_budget_are_explicit(monkeypatch, mode, code):
    source = acquisition.CamaraAcquisition(
        SimpleNamespace(max_pages=1 if mode == "budget" else 3), None
    )
    payload = {"dados": [] if mode != "schema" else {}, "links": [{"rel": "next", "href": "same"}]}
    monkeypatch.setattr(source, "json_document", lambda *args: (payload, "artifact"))
    with pytest.raises(IngestionError, match=code):
        list(source.pages("same", "kind"))


@pytest.mark.parametrize("path", ["deputados/1", API_BASE + "deputados/1"])
def test_camara_json_document_resolves_relative_and_official_absolute_urls(
    monkeypatch, tmp_path, path
):
    artifact = profile_artifact(tmp_path)
    source = acquisition.CamaraAcquisition(None, None)
    calls = []
    monkeypatch.setattr(source, "acquire", lambda url, kind: calls.append(url) or artifact)
    document, returned = source.json_document(path, "profile")
    assert returned is artifact and document["dados"]["id"] == "1"
    assert calls == [API_BASE + "deputados/1"]


@pytest.mark.parametrize(
    "manifest,intact",
    [
        (None, False),
        ({"fetched_at": "2026-05-01T00:00:00Z"}, False),
        ({"fetched_at": "2026-05-01T00:00:00Z"}, True),
    ],
)
def test_cached_identity_profile_requires_intact_archive(monkeypatch, tmp_path, manifest, intact):
    monkeypatch.setattr(voting_identity, "load_json", lambda path: manifest)
    monkeypatch.setattr(voting_identity, "is_cached_archive_intact", lambda *args: intact)
    monkeypatch.setattr(voting_identity, "build_downloaded_artifact", lambda *args: "cached")
    assert voting_identity.cached_profile_artifact(
        SimpleNamespace(storage_directory=tmp_path), "1"
    ) == ("cached" if manifest and intact else None)


@pytest.mark.parametrize(
    "extra_page,has_next,complete",
    [(False, False, True), (False, True, False), (True, False, False)],
)
def test_discovery_truncation_is_explicit_when_page_or_event_budget_reached(
    tmp_path, extra_page, has_next, complete
):
    path = tmp_path / "page.json"
    path.write_text(json.dumps({"links": [{"rel": "next"}] if has_next else []}))
    artifact = SimpleNamespace(path=path)
    rows = [event(), event("2")] if extra_page else [event()]
    source = SimpleNamespace(pages=lambda *args: [(rows, artifact)])
    selected, artifacts, discovery_complete = voting_acquisition.discover_votings(
        source, date(2026, 5, 1), date(2026, 5, 2), 1
    )
    assert selected == [event()]
    assert artifacts == [artifact]
    assert discovery_complete is complete


def test_profile_without_document_uses_unique_name_birth_match(monkeypatch):
    item = {
        "transient_key": "1",
        "document_fingerprint": None,
        "normalized_name": "person",
        "birth_date": "1980-01-01",
        "artifact": "artifact",
    }
    monkeypatch.setattr(
        voting_identity, "profile_evidence", lambda artifact: item if artifact else None
    )
    monkeypatch.setattr(voting_identity, "lookup_unique_people_by_document", lambda *args: {})
    monkeypatch.setattr(
        voting_identity,
        "lookup_unique_people_by_name_birth",
        lambda connection, rows: {("person", "1980-01-01"): "canonical"},
    )
    assert voting_identity.resolve_voting_people(None, {"1": "artifact", "empty": None}) == {
        "1": {"person_id": "canonical", "artifact": "artifact"}
    }


def test_verified_profile_evidence_carries_no_raw_document(tmp_path):
    artifact = profile_artifact(tmp_path)
    evidence = voting_identity.profile_evidence(artifact)
    assert evidence["transient_key"] == "1"
    assert evidence["birth_date"] == "1980-01-01"
    assert evidence["document_fingerprint"] is None
    assert "cpf" not in evidence


def test_event_round_uses_published_subject_and_unknown_matter_stays_unknown():
    detailed = event(descUltimaAberturaVotacao="Segundo turno")
    normalized = voting_normalization.normalize_voting_event(event(), detailed)
    assert normalized["round_number"] == 2
    assert normalized["occurred_on"] == "2026-05-01"
    assert (
        voting_normalization.matter_fields(None, detailed["uri"])["description_origin"] == "unknown"
    )
    fields = voting_normalization.matter_fields(
        {"siglaTipo": "PL", "numero": "1", "ano": 2026, "ementa": "Texto oficial"}, detailed["uri"]
    )
    assert fields["matter_name"] == "PL 1/2026"
    assert fields["description_origin"] == "official_text"
    uri = API_BASE + "proposicoes/1"
    assert (
        voting_normalization.related_matter_uri(
            {"discovery": {}, "detail": {"proposicoesAfetadas": [{"uri": uri}]}}
        )
        == uri
    )


def test_valid_voting_collection_preserves_all_vote_artifact_dependencies():
    source = SimpleNamespace(
        json_document=lambda *args: ({"dados": event()}, "detail-artifact"),
        pages=lambda *args: [([{"tipoVoto": "Sim"}], "votes-artifact")],
    )
    collected = voting_acquisition.collect_voting_documents(source, [event()], 1)
    assert collected[0]["artifacts"] == ["detail-artifact", "votes-artifact"]
    assert collected[0]["votes"] == [{"tipoVoto": "Sim"}]


def test_camara_pagination_stops_cleanly_when_no_next_link(monkeypatch):
    source = acquisition.CamaraAcquisition(SimpleNamespace(max_pages=2), None)
    monkeypatch.setattr(
        source, "json_document", lambda *args: ({"dados": ["row"], "links": []}, "artifact")
    )
    assert list(source.pages("start", "kind")) == [(["row"], "artifact")]
