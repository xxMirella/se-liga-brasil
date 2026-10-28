"""Source backfill preserves cached evidence and delegates by requested scope."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from crawlers.alesp import local_enrichment
from crawlers.tse import discovery, enrichment
from crawlers.tse.configuration import CrawlerConfiguration
from service.ingestion.contracts import IngestionError, IngestionSummary, Resource
from storage.files import hash_file, load_json, read_json_lines, save_json


def metadata(kind="candidate", identifier="safe-id", uf=""):
    path = (
        f"consulta_cand/consulta_cand_2024{uf}.zip"
        if kind == "candidate"
        else (f"bem_candidato/bem_candidato_2024{uf}.zip")
    )
    return {"id": identifier, "name": "Official", "url": "https://cdn.tse.jus.br/" + path}


@pytest.mark.parametrize(
    ("path", "kind"),
    [
        ("consulta_cand/consulta_cand_2024.zip", "candidate"),
        ("historico_candidatura/data.zip", "history"),
        ("consulta_cand_complementar/data.zip", "complement"),
        ("bem_candidato/data.zip", "asset"),
        ("proposta_governo/data.zip", "government_proposal"),
        ("certidao_criminal/data.zip", "criminal_certificate"),
        ("unknown.zip", None),
    ],
)
def test_catalog_classifies_only_known_official_dataset_paths(path, kind):
    assert discovery.classify_resource("https://cdn.tse.jus.br/" + path) == kind


def test_catalog_rejects_invalid_resource_ids_and_non_candidate_datasets(tmp_path):
    assert (
        discovery.build_resource(metadata(identifier="../../bad"), "candidatos-2024", 2024) is None
    )
    assert discovery.build_resource({"url": "https://cdn.tse.jus.br/other.zip"}, "d", 2024) is None
    assert discovery.select_resources({"name": "other"}, CrawlerConfiguration(tmp_path)) == []


def test_catalog_normalizes_url_prefix_and_scopes_state_and_kind(tmp_path):
    row = metadata("asset", uf="_SP")
    row["url"] = " URL: " + row["url"] + " "
    resource = discovery.build_resource(row, "candidatos-2024", 2024)
    assert resource.uf == "SP"
    config = CrawlerConfiguration(tmp_path, ufs=("RJ",), kinds=("asset",))
    assert not discovery.is_selected_resource(resource, config)
    assert discovery.is_selected_resource(resource, replace(config, ufs=()))
    assert not discovery.is_selected_resource(resource, replace(config, kinds=("candidate",)))


def test_catalog_paginates_names_and_skips_non_electoral_packages(tmp_path):
    client = Mock()
    client.fetch_catalog.side_effect = [
        {"count": 101, "results": [{"name": "candidatos-2024"}, {"name": "irrelevant"}]},
        {"count": 101, "results": [{"name": "candidatos-2020"}]},
    ]
    assert discovery.discover_dataset_names(CrawlerConfiguration(tmp_path, years=()), client) == [
        "candidatos-2024",
        "candidatos-2020",
    ]
    assert "start=100" in client.fetch_catalog.call_args.args[0]


def test_catalog_sorts_newest_year_then_candidate_before_asset_and_keeps_snapshot(tmp_path):
    client = Mock()
    client.fetch_catalog.side_effect = [
        {"name": "candidatos-2020", "resources": [metadata("asset")]},
        {"name": "candidatos-2024", "resources": [metadata("asset"), metadata()]},
    ]
    resources = discovery.discover_resources(
        CrawlerConfiguration(tmp_path, years=(2020, 2024)), client
    )
    assert [(r.year, r.kind) for r in resources] == [
        (2024, "candidate"),
        (2024, "asset"),
        (2020, "asset"),
    ]
    assert load_json(tmp_path / "catalogs/candidatos-2024.json")["dataset"]["name"] == (
        "candidatos-2024"
    )


def test_backfill_reuses_cached_files_without_catalog_or_download(monkeypatch, tmp_path):
    artifact = SimpleNamespace(resource=Resource("r", "n", "u", "asset", 2024, "d"))
    monkeypatch.setattr(enrichment, "load_selected_downloads", Mock(return_value=[artifact]))
    discover = Mock()
    monkeypatch.setattr(enrichment, "discover_resources", discover)
    downloads, failures = enrichment.acquire_asset_backfill(
        CrawlerConfiguration(tmp_path, years=(2024,), kinds=("asset",)), object()
    )
    assert downloads == [artifact] and failures == []
    discover.assert_not_called()


def test_backfill_downloads_only_missing_year_kind_pairs(monkeypatch, tmp_path):
    cached = SimpleNamespace(resource=Resource("r", "n", "u", "asset", 2024, "d"))
    missing = Resource("new", "n", "u", "candidate", 2024, "d")
    monkeypatch.setattr(enrichment, "load_selected_downloads", Mock(return_value=[cached]))
    monkeypatch.setattr(
        enrichment, "discover_resources", Mock(return_value=[cached.resource, missing])
    )
    download = Mock(return_value=(["new artifact"], [{"code": "PARTIAL"}]))
    monkeypatch.setattr(enrichment, "download_selected_resources", download)
    config = CrawlerConfiguration(tmp_path, years=(2024,), kinds=("asset", "candidate"))
    artifacts, failures = enrichment.acquire_asset_backfill(config, "client")
    assert download.call_args.args[2] == [missing]
    assert artifacts == [cached, "new artifact"] and failures == [{"code": "PARTIAL"}]


def test_candidate_scope_registers_only_requested_election_year_and_deduplicates_offices():
    connection = Mock()
    connection.execute.return_value.fetchall.return_value = [
        {"person_id": "one", "election_year": 2024, "candidate_sequence": "a", "office_code": "6"},
        {"person_id": "one", "election_year": 2020, "candidate_sequence": "b", "office_code": "7"},
    ]
    index = Mock()
    assert enrichment.populate_candidate_scope(
        connection, index, [{"person_id": "one", "election_year": 2024}]
    ) == ("6",)
    index.register_candidate.assert_called_once_with(
        {"electionYear": 2024, "candidateSequence": "a"}
    )


def test_asset_scope_is_order_independent_and_asset_helper_requests_both_fields(
    monkeypatch, tmp_path
):
    first = enrichment.AssetBackfillConfiguration(tmp_path, target_person_ids=("b", "a"))
    assert first.scope_key == replace(first, target_person_ids=("a", "b")).scope_key
    collector = Mock(return_value={})
    monkeypatch.setattr(enrichment, "collect_requested_tse_data", collector)
    enrichment.collect_declared_assets("db", tmp_path, [{"person_id": "one"}])
    assert collector.call_args.args[2][0]["fields"] == ["declared_assets", "declared_wealth"]


def evidence(tmp_path):
    path = tmp_path / "original.xml"
    path.write_bytes(b"immutable official data")
    return {
        "path": str(path),
        "sha256": hash_file(path),
        "url": "https://www.al.sp.gov.br/data",
        "fetched_at": "2024-01-01T00:00:00Z",
    }


def test_verified_local_evidence_deduplicates_and_refuses_modified_originals(tmp_path):
    source = evidence(tmp_path)
    resolutions = [{"official_subjects": [{"sources": [source, source]}]}, {}]
    assert local_enrichment.verified_evidence_references(resolutions) == [source]
    (tmp_path / "original.xml").write_bytes(b"changed")
    with pytest.raises(IngestionError, match="ALESP_LOCAL_EVIDENCE_CHECKSUM_MISMATCH"):
        local_enrichment.verified_evidence_references(resolutions)


def test_required_local_dataset_manifest_missing_and_corruption_fail_closed(tmp_path):
    with pytest.raises(IngestionError, match="ALESP_LOCAL_DATASET_MANIFEST_MISSING"):
        local_enrichment.dataset_references(tmp_path)
    research = tmp_path / "research"
    research.mkdir()
    (research / "61_deputados.xml").write_bytes(b"data")
    save_json(
        research / "catalog-download-manifest.json",
        [{"file": "61_deputados.xml", "sha256": "wrong"}],
    )
    with pytest.raises(IngestionError, match="ALESP_LOCAL_EVIDENCE_CHECKSUM_MISMATCH"):
        local_enrichment.dataset_references(tmp_path)


def test_local_dataset_references_include_only_required_files(tmp_path):
    research = tmp_path / "research"
    research.mkdir()
    entries = []
    for name in ("61_deputados.xml", "56_proposituras.zip", "81_documento_autor.zip", "other.zip"):
        path = research / name
        path.write_bytes(b"source")
        entries.append(
            {
                "file": name,
                "sha256": hash_file(path),
                "url": "https://www.al.sp.gov.br/" + name,
                "collected_at": "2024-01-01T00:00:00Z",
            }
        )
    save_json(research / "catalog-download-manifest.json", entries)
    assert len(local_enrichment.dataset_references(tmp_path)) == 3


def test_local_staging_is_scoped_private_and_provenance_complete(tmp_path):
    source = evidence(tmp_path)
    rows = [{"personId": "one", "officialKey": "doc", "observedAt": "2024-02-01"}]
    staged = local_enrichment.stage_local_records(
        tmp_path, "alesp_propositions", iter(rows), [source], ["one"]
    )
    records = list(read_json_lines(staged.records_path))
    assert records[0]["normalizedData"] == rows[0]
    assert records[0]["sourceGeneratedAt"] == "2024-02-01"
    assert staged.summary == {"valid": 1, "rejected": 0}
    assert staged.records_path.stat().st_mode & 0o777 == 0o600
    assert hash_file(staged.artifact.path) == staged.artifact.sha256
    replay = local_enrichment.stage_local_records(
        tmp_path, "alesp_propositions", iter(rows), [source], ["one"]
    )
    assert replay.artifact.path == staged.artifact.path


def test_local_enrichment_without_verified_identity_does_not_project(tmp_path):
    repo = Mock()
    result = local_enrichment.collect_alesp_local_enrichment(repo, tmp_path)
    assert result["status"] == "unavailable"
    repo.ingest_validated_artifact.assert_not_called()


def test_local_enrichment_projects_profiles_and_authorship_without_remote_requests(
    monkeypatch, tmp_path
):
    source = evidence(tmp_path)
    save_json(
        tmp_path / "identity-resolution.json",
        {"resolutions": [{"official_subjects": [{"sources": [source]}]}]},
    )
    monkeypatch.setattr(
        local_enrichment, "institutional_profiles", Mock(return_value=[{"personId": "p"}])
    )
    monkeypatch.setattr(
        local_enrichment,
        "authored_propositions",
        Mock(return_value=[{"personId": "p", "officialKey": "proposal"}]),
    )
    monkeypatch.setattr(local_enrichment, "dataset_references", Mock(return_value=[source]))
    repo = Mock()
    repo.ingest_validated_artifact.return_value = IngestionSummary(new=1)
    result = local_enrichment.collect_alesp_local_enrichment(repo, tmp_path, ["p"])
    assert result["remote_requests"] == 0 and result["staged_authorships"] == 1
    assert repo.ingest_validated_artifact.call_count == 2


def test_empty_tse_request_does_not_open_repository(monkeypatch, tmp_path):
    repository = Mock()
    monkeypatch.setattr(enrichment, "IngestionRepository", repository)
    assert enrichment.collect_requested_tse_data(None, tmp_path, []) == {
        "target_people": 0,
        "artifacts": [],
        "failures": [],
    }
    repository.assert_not_called()


@pytest.mark.parametrize("fails", [False, True])
def test_requested_tse_run_closes_scope_index_on_collection_success_and_failure(
    monkeypatch, tmp_path, fails
):
    from crawlers.tse import requested_data

    config = enrichment.AssetBackfillConfiguration(tmp_path / "tse", target_person_ids=("one",))
    monkeypatch.setattr(enrichment, "build_requested_configuration", Mock(return_value=config))
    index = Mock()
    monkeypatch.setattr(enrichment, "ValidationIndex", Mock(return_value=index))
    repo = Mock()
    repo.ingest_validated_artifact.return_value = IngestionSummary(new=1)
    monkeypatch.setattr(enrichment, "IngestionRepository", Mock(return_value=repo))
    monkeypatch.setattr(enrichment, "populate_candidate_scope", Mock(return_value=("6",)))
    acquire = Mock(return_value=(["artifact"], [{"code": "PARTIAL"}]))
    if fails:
        acquire.side_effect = RuntimeError("source failed")
    monkeypatch.setattr(enrichment, "acquire_asset_backfill", acquire)
    monkeypatch.setattr(enrichment, "validate_resource", Mock(return_value="validated"))
    monkeypatch.setattr(enrichment, "find_declaration_conflicts", Mock(return_value=[]))
    monkeypatch.setattr(
        requested_data, "repair_missing_personal_fields", Mock(return_value=["one"])
    )
    if fails:
        with pytest.raises(RuntimeError, match="source failed"):
            enrichment.collect_requested_tse_data(Mock(), tmp_path, [{"person_id": "one"}])
        repo.finish_run.assert_called_once_with("failed", {})
    else:
        result = enrichment.collect_requested_tse_data(Mock(), tmp_path, [{"person_id": "one"}])
        assert result["repaired_personal_fields"] == 1
        assert repo.finish_run.call_args.args[0] == "partial"
    index.close.assert_called_once()
    assert list((tmp_path / "tse").glob("scope-*.sqlite")) == []


def test_requested_configuration_deduplicates_people_years_and_requested_resource_kinds(
    monkeypatch, tmp_path
):
    from crawlers.tse import requested_data

    monkeypatch.setattr(requested_data, "load_requested_personal_scope", Mock(return_value={}))
    monkeypatch.setattr(requested_data, "load_requested_election_scope", Mock(return_value=[
        {"person_id": "one", "election_year": 2024, "represented_uf": "AC"},
    ]))
    targets = [
        {"person_id": "one", "election_year": 2024, "fields": ["birth_date"]},
        {"person_id": "one", "election_year": 2024, "fields": ["declared_wealth"]},
    ]
    config = enrichment.build_requested_configuration(Mock(), tmp_path, targets)
    assert config.target_person_ids == ("one",) and config.years == (2024,)
    assert config.kinds == ("candidate", "complement", "asset")
    assert config.ufs == ("AC",)
    connection = Mock()
    connection.execute.return_value.fetchall.return_value = [{"reason_code": "CONFLICT"}]
    assert enrichment.find_declaration_conflicts(connection, ["one"]) == [
        {"reason_code": "CONFLICT"}
    ]
    assert connection.execute.call_args.args[1] == (["one"],)


def test_tse_begin_run_failure_still_closes_scope_without_finishing_unowned_run(
    monkeypatch, tmp_path
):
    config = enrichment.AssetBackfillConfiguration(tmp_path / "tse", target_person_ids=("one",))
    monkeypatch.setattr(enrichment, "build_requested_configuration", Mock(return_value=config))
    index = Mock()
    monkeypatch.setattr(enrichment, "ValidationIndex", Mock(return_value=index))
    repo = Mock()
    repo.begin_run.side_effect = IngestionError("CRAWLER_ALREADY_RUNNING_IN_DATABASE")
    monkeypatch.setattr(enrichment, "IngestionRepository", Mock(return_value=repo))
    with pytest.raises(IngestionError, match="CRAWLER_ALREADY_RUNNING_IN_DATABASE"):
        enrichment.collect_requested_tse_data(Mock(), tmp_path, [{"person_id": "one"}])
    index.close.assert_called_once()
    repo.finish_run.assert_not_called()
