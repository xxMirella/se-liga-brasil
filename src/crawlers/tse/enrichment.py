"""Backfill missing declarations in source batches, never one download per person."""

from dataclasses import asdict, dataclass, replace
from uuid import uuid4

import httpx

from crawlers.tse.configuration import TSE_SOURCE, CrawlerConfiguration
from crawlers.tse.discovery import discover_resources
from crawlers.tse.http_client import OfficialHttpClient
from crawlers.tse.projection import TseProjectionWriter
from crawlers.tse.validator import validate_resource
from database.operations import PROJECT_ROOT
from service.crawling.acquisition import download_selected_resources
from service.crawling.source_pipeline import load_selected_downloads
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter
from storage.files import hash_content
from storage.validation_index import ValidationIndex


@dataclass(frozen=True)
class AssetBackfillConfiguration(CrawlerConfiguration):
    target_person_ids: tuple[str, ...] = ()

    @property
    def scope_key(self) -> str:
        return super().scope_key + ";people=" + hash_content(sorted(self.target_person_ids))[:16]


def populate_candidate_scope(connection, index, targets) -> tuple:
    rows = connection.execute(
        """
        SELECT c.election_year,c.candidate_sequence,c.person_id::text,c.office_code
        FROM se_liga_brasil.electoral_candidacy c
        JOIN se_liga_brasil.source s ON s.id=c.source_id AND s.code='tse'
        WHERE c.person_id=ANY(%s::uuid[])
    """,
        ([row["person_id"] for row in targets],),
    ).fetchall()
    years = {row["person_id"]: row["election_year"] for row in targets}
    office_codes = set()
    for row in rows:
        if row["election_year"] == years[row["person_id"]]:
            office_codes.add(row["office_code"])
            index.register_candidate(
                {
                    "electionYear": row["election_year"],
                    "candidateSequence": row["candidate_sequence"],
                }
            )

    return tuple(sorted(office_codes))


def acquire_asset_backfill(configuration, client):
    originals = CrawlerConfiguration(
        storage_directory=PROJECT_ROOT / "data/tse",
        years=configuration.years,
        kinds=configuration.kinds,
        ufs=configuration.ufs,
    )
    downloads = load_selected_downloads(
        originals,
        lambda resource, config: resource.kind in config.kinds and resource.year in config.years,
    )
    expected = {(year, kind) for year in configuration.years for kind in configuration.kinds}
    missing = expected - {(a.resource.year, a.resource.kind) for a in downloads}
    failures = []
    if missing:
        resources = [
            r for r in discover_resources(configuration, client) if (r.year, r.kind) in missing
        ]
        additional, failures = download_selected_resources(configuration, client, resources)
        downloads.extend(additional)
    return downloads, failures


def collect_declared_assets(connection, storage, targets) -> dict:
    requested = [row | {"fields": ["declared_assets", "declared_wealth"]} for row in targets]
    return collect_requested_tse_data(connection, storage, requested)


def build_requested_configuration(connection, storage, targets):
    from crawlers.tse.requested_data import RequestedTseConfiguration, load_requested_personal_scope

    fields = {field for row in targets for field in row["fields"]}
    kinds = tuple(
        kind
        for kind, relevant in (
            ("candidate", {"birth_date", "education_level", "full_name"}),
            ("asset", {"declared_assets", "declared_wealth"}),
        )
        if fields & relevant
    )
    person_ids = sorted({row["person_id"] for row in targets})
    return RequestedTseConfiguration(
        **load_requested_personal_scope(connection, person_ids),
        target_person_ids=tuple(person_ids),
        storage_directory=storage / "tse",
        years=tuple(sorted({row["election_year"] for row in targets})),
        ufs=("SP", "RJ"),
        kinds=kinds,
        office_codes=("5", "6", "7"),
    )


def collect_requested_tse_data(connection, storage, targets) -> dict:
    from crawlers.tse.requested_data import repair_missing_personal_fields

    if not targets:
        return {"target_people": 0, "artifacts": [], "failures": []}
    configuration = build_requested_configuration(connection, storage, targets)
    configuration.storage_directory.mkdir(parents=True, exist_ok=True)
    index_path = configuration.storage_directory / ("scope-" + uuid4().hex + ".sqlite")
    index = ValidationIndex(index_path)
    run_started = False
    try:
        repository = IngestionRepository(
            connection, TSE_SOURCE, TseProjectionWriter(SqlBatchWriter(connection))
        )
        repository.begin_run(str(uuid4()), {"purpose": "requested_tse_data"})
        run_started = True
        office_codes = populate_candidate_scope(connection, index, targets)
        configuration = replace(configuration, office_codes=office_codes)
        with httpx.Client(timeout=configuration.request_timeout_seconds) as client:
            downloads, failures = acquire_asset_backfill(
                configuration, OfficialHttpClient(configuration, client)
            )
        summaries = [
            asdict(
                repository.ingest_validated_artifact(
                    validate_resource(a, configuration, index), 500
                )
            )
            for a in downloads
        ]
        repaired = repair_missing_personal_fields(connection, list(configuration.target_person_ids))
        result = {
            "target_people": len(targets),
            "artifacts": summaries,
            "failures": failures,
            "repaired_personal_fields": len(repaired),
            "declaration_conflicts": find_declaration_conflicts(
                connection, list(configuration.target_person_ids)
            ),
        }
        repository.finish_run(
            "partial" if failures or any(x["rejected"] for x in summaries) else "completed", result
        )
        return result
    except BaseException:
        if run_started:
            repository.finish_run("failed", {})
        raise
    finally:
        index.close()
        index_path.unlink(missing_ok=True)


def find_declaration_conflicts(connection, person_ids):
    return connection.execute(
        """
        SELECT DISTINCT c.person_id::text,c.election_year,
          'DECLARATION_CONFLICT_REQUIRES_REVIEW' AS reason_code
        FROM se_liga_brasil.electoral_candidacy c
        JOIN se_liga_brasil.source_record r ON r.id=c.source_record_id
        WHERE c.person_id=ANY(%s::uuid[]) AND r.payload->>'declaresAssets'='false'
          AND EXISTS(SELECT 1 FROM se_liga_brasil.candidate_asset_declaration a
            WHERE a.person_id=c.person_id AND a.election_year=c.election_year)
        """,
        (person_ids,),
    ).fetchall()
