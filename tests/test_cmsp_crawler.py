"""Anonymous official-shape fixtures; no real people or production database writes."""

import json
from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
from test_senado_integration import create_test_person

from crawlers.cmsp.acquisition import MunicipalAcquisition, annual_resources
from crawlers.cmsp.configuration import OFFICIAL_HOSTS, PARSER_VERSION, SOURCE, CrawlerConfiguration
from crawlers.cmsp.identity import ReviewedAuthorBinding, index_reviewed_bindings
from crawlers.cmsp.normalization import attach_reviewed_authors, normalize_project
from crawlers.cmsp.parsing import iter_projects
from crawlers.cmsp.pipeline import collect_municipal_legislation
from crawlers.cmsp.projection import MunicipalProjectionWriter
from crawlers.cmsp.staging import stage_partition
from service.acquisition.http_client import OfficialHttpClient
from service.ingestion.contracts import DownloadedArtifact, IngestionError
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter
from storage.files import hash_file

PROJECT = """<Projeto><Chave>source-key</Chave><Tipo>PL</Tipo><Numero>1</Numero><Ano>2021</Ano>
<Data>01/02/2021</Data><Ementa>Descrição demonstrativa</Ementa>
<Autores><Autor><Chave>123</Chave><Nome>Pessoa Fictícia</Nome></Autor></Autores>
<Subscritores><Autor><Nome>Outro Exemplo</Nome></Autor></Subscritores>
<Deliberacoes><Deliberacao><Resultado>Aprovado</Resultado></Deliberacao></Deliberacoes>
</Projeto>"""


def xml_document(projects=PROJECT):
    return '<ArrayOfProjeto xmlns="http://saopaulo.sp.leg.br">' + projects + "</ArrayOfProjeto>"


def artifact_fixture(tmp_path, content=None):
    path = tmp_path / "original.xml"
    path.write_text(xml_document() if content is None else content)
    resource = next(annual_resources([2021], ["projects"]))
    return DownloadedArtifact(
        resource, path, hash_file(path), "2026-10-17T00:00:00+00:00", path.stat().st_size
    )


def test_partition_plan_deduplicates_and_uses_documented_parameter_case():
    resources = list(annual_resources([2021, 2021]))
    assert len(resources) == 3
    assert resources[0].url.endswith("ProjetosPorAno?Ano=2021")
    assert resources[1].url.endswith("ProjetosAutores?ano=2021&tipo=&numero=")
    assert resources[2].url.endswith("FasesDeDeliberacao?ano=2021")


def test_unknown_domain_fails_before_network():
    with pytest.raises(IngestionError, match="CMSP_UNSUPPORTED_DOMAIN"):
        list(annual_resources([2021], ["invented"]))


def test_collective_result_does_not_create_vote_or_approval(tmp_path):
    artifact = artifact_fixture(tmp_path)
    project = next(iter_projects(artifact.path, max_records=10))
    normalized = normalize_project(project, 2021)
    assert normalized["officialKey"] == "PL:1:2021"
    assert normalized["introducedOn"] == "2021-02-01"
    assert normalized["currentStatus"] == "unknown"
    assert normalized["verifiedAuthors"] == []
    assert normalized["authorNames"] == ["Pessoa Fictícia"]
    assert normalized["deliberationObservations"][0]["occurredAt"] is None
    assert normalized["deliberationObservations"][0]["individualVote"] is None
    assert "source-key" not in json.dumps(normalized)
    assert "123" not in json.dumps(normalized)


def test_reviewed_identity_requires_exact_artifact_and_unique_name(tmp_path):
    artifact = artifact_fixture(tmp_path)
    binding = ReviewedAuthorBinding(UUID(int=1), "Pessoa Fictícia", artifact.sha256, "review:test")
    indexed = index_reviewed_bindings([binding])
    project = next(iter_projects(artifact.path, max_records=10))
    normalized = attach_reviewed_authors(normalize_project(project, 2021), indexed, artifact.sha256)
    assert normalized["verifiedAuthors"][0]["personId"] == str(UUID(int=1))
    with pytest.raises(IngestionError, match="CMSP_AMBIGUOUS_REVIEWED_AUTHOR"):
        index_reviewed_bindings([binding, binding])
    with pytest.raises(IngestionError, match="CMSP_REVIEWED_ARTIFACT_CHANGED"):
        attach_reviewed_authors(normalized, indexed, "0" * 64)
    with pytest.raises(IngestionError, match="CMSP_UNVERIFIED_AUTHOR_BINDING"):
        index_reviewed_bindings([replace(binding, method="name_only")])


@pytest.mark.parametrize(
    "content,code",
    [
        ('<!DOCTYPE x [<!ENTITY name "x">]><x/>', "CMSP_UNSAFE_XML"),
        ("<html>Unavailable</html>", "CMSP_XML_SCHEMA_CHANGED"),
        ('<ArrayOfProjeto xmlns="http://saopaulo.sp.leg.br"><Projeto>', "CMSP_INVALID_XML"),
    ],
)
def test_invalid_partition_never_leaves_ingestible_files(tmp_path, content, code):
    artifact = artifact_fixture(tmp_path, content)
    with pytest.raises(IngestionError, match=code):
        stage_partition(artifact, CrawlerConfiguration(tmp_path / "storage"), {})
    assert not list((tmp_path / "storage").rglob("*.ndjson"))
    assert artifact.path.read_text() == content


def test_record_limit_is_failure_not_silent_truncation(tmp_path):
    artifact = artifact_fixture(tmp_path, xml_document(PROJECT * 2))
    configuration = CrawlerConfiguration(tmp_path / "storage", max_records_per_resource=1)
    with pytest.raises(IngestionError, match="CMSP_RECORD_LIMIT_EXCEEDED"):
        stage_partition(artifact, configuration, {})
    assert not list(configuration.storage_directory.rglob("records.ndjson"))


def test_identical_records_are_deduplicated(tmp_path):
    artifact = artifact_fixture(tmp_path, xml_document(PROJECT * 2))
    validated = stage_partition(artifact, CrawlerConfiguration(tmp_path / "storage"), {})
    assert validated.summary == {"valid": 1, "rejected": 0}
    assert len(validated.records_path.read_text().splitlines()) == 1
    assert hash_file(artifact.path) == artifact.sha256


def test_wrong_year_is_rejected_without_false_complete_coverage(tmp_path):
    artifact = artifact_fixture(tmp_path, xml_document(PROJECT.replace("<Ano>2021", "<Ano>2020")))
    acquisition = SimpleNamespace(
        configuration=CrawlerConfiguration(tmp_path / "storage"), acquire=lambda resource: artifact
    )
    result = list(collect_municipal_legislation(acquisition, [2021], domains=["projects"]))[0]
    assert result["coverage"] == "partial"
    assert result["records"] == {"valid": 0, "rejected": 1}


def test_bounded_collection_stops_before_extra_request(tmp_path):
    artifact = artifact_fixture(tmp_path)
    calls = []
    configuration = CrawlerConfiguration(tmp_path / "storage", max_resources=1)
    acquisition = SimpleNamespace(
        configuration=configuration, acquire=lambda resource: calls.append(resource) or artifact
    )
    collection = collect_municipal_legislation(acquisition, [2021])
    assert next(collection)["historicalCompleteness"] == "not_asserted"
    with pytest.raises(IngestionError, match="CMSP_RESOURCE_LIMIT_EXCEEDED"):
        next(collection)
    assert len(calls) == 1


def test_immutable_cache_avoids_repeated_http(tmp_path):
    calls = []

    def response(request):
        calls.append(str(request.url))
        return httpx.Response(200, content=xml_document().encode())

    configuration = CrawlerConfiguration(tmp_path, request_min_interval_seconds=0)
    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        official = OfficialHttpClient(configuration, client, OFFICIAL_HOSTS)
        acquisition = MunicipalAcquisition(configuration, official)
        resource = next(annual_resources([2021], ["projects"]))
        first, second = acquisition.acquire(resource), acquisition.acquire(resource)
    assert len(calls) == 1
    assert first.sha256 == second.sha256
    assert second.acquisition_status == "cached"


def test_projection_dispatches_only_supported_domain():
    calls = []
    writer = SimpleNamespace(execute_statements=lambda name, parameters: calls.append(name))
    projection = MunicipalProjectionWriter(writer)
    projection.project_batch({}, "cmsp_projects")
    assert calls == ["cmsp_propositions"]
    with pytest.raises(IngestionError, match="CMSP_UNSUPPORTED_DOMAIN"):
        projection.project_batch({}, "guessed_votes")


def test_conflicting_duplicate_aborts_whole_partition(tmp_path):
    content = xml_document(PROJECT + PROJECT.replace("Descrição demonstrativa", "Alterada"))
    artifact = artifact_fixture(tmp_path, content)
    configuration = CrawlerConfiguration(tmp_path / "storage")
    with pytest.raises(IngestionError, match="CMSP_CONFLICTING_DUPLICATE_PROPOSITION"):
        stage_partition(artifact, configuration, {})
    assert not list(configuration.storage_directory.rglob("records.ndjson"))


def test_unexpected_collection_child_is_not_empty_coverage(tmp_path):
    artifact = artifact_fixture(tmp_path, xml_document("<Unknown/>"))
    with pytest.raises(IngestionError, match="CMSP_XML_SCHEMA_CHANGED"):
        stage_partition(artifact, CrawlerConfiguration(tmp_path / "storage"), {})


def test_artifact_tampering_blocks_ingestion(tmp_path):
    artifact = artifact_fixture(tmp_path)
    artifact.path.write_text(xml_document(PROJECT.replace("<Numero>1", "<Numero>2")))
    with pytest.raises(IngestionError, match="CMSP_ARTIFACT_CHANGED"):
        stage_partition(artifact, CrawlerConfiguration(tmp_path / "storage"), {})


def test_reviewed_replay_changes_scope_and_entity_key(tmp_path):
    artifact = artifact_fixture(tmp_path)
    configuration = CrawlerConfiguration(tmp_path / "storage")
    unlinked = stage_partition(artifact, configuration, {})
    binding = ReviewedAuthorBinding(UUID(int=1), "Pessoa Fictícia", artifact.sha256, "review:test")
    linked = stage_partition(artifact, configuration, index_reviewed_bindings([binding]))
    assert unlinked.scope_key != linked.scope_key
    first = json.loads(unlinked.records_path.read_text())
    second = json.loads(linked.records_path.read_text())
    assert first["externalKey"] != second["externalKey"]
    assert first["normalizedData"]["officialKey"] == second["normalizedData"]["officialKey"]


@pytest.mark.integration
def test_sql_projection_rejection_and_identity_replay(
    integration_database, tmp_path, configuration, archive_factory, candidate_row
):
    connection = integration_database
    person_id = UUID(
        create_test_person(connection, tmp_path, configuration, archive_factory, candidate_row)
    )
    artifact = artifact_fixture(tmp_path)
    settings = CrawlerConfiguration(tmp_path / "cmsp")
    repository = IngestionRepository(
        connection,
        SOURCE,
        MunicipalProjectionWriter(SqlBatchWriter(connection)),
        parser_version=PARSER_VERSION,
    )
    repository.begin_run(str(uuid4()), {"test": True})
    try:
        unlinked = stage_partition(artifact, settings, {})
        assert repository.ingest_validated_artifact(unlinked, 500).rejected == 0
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM se_liga_brasil.proposition_person"
            ).fetchone()["n"]
            == 0
        )
        binding = ReviewedAuthorBinding(
            person_id, "Pessoa Fictícia", artifact.sha256, "review:test"
        )
        linked = stage_partition(artifact, settings, index_reviewed_bindings([binding]))
        replay = repository.ingest_validated_artifact(linked, 500)
        assert replay.rejected == 0 and not replay.skipped_artifact
        assert repository.ingest_validated_artifact(linked, 500).skipped_artifact
        assert (
            connection.execute("SELECT count(*) AS n FROM se_liga_brasil.proposition").fetchone()[
                "n"
            ]
            == 1
        )
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM se_liga_brasil.proposition_person"
            ).fetchone()["n"]
            == 1
        )
        invalid = replace(artifact, resource=replace(artifact.resource, year=2020))
        rejected = stage_partition(invalid, settings, {})
        assert repository.ingest_validated_artifact(rejected, 500).rejected == 1
        row = connection.execute(
            "SELECT reason_code FROM se_liga_brasil.ingestion_rejection WHERE resource_id=%s",
            (artifact.resource.resource_id,),
        ).fetchone()
        assert row["reason_code"] == "CMSP_PARTITION_YEAR_MISMATCH"
    finally:
        repository.finish_run("completed", {})
