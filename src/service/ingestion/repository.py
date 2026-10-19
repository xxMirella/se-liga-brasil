"""Transactional artifacts, immutable versions and provenance-aware projections."""

from dataclasses import asdict
from itertools import batched

from psycopg.types.json import Jsonb

from service.ingestion.contracts import (
    PARSER_VERSION,
    IngestionError,
    IngestionSummary,
    ValidatedArtifact,
)
from service.ingestion.sql_batches import TEMP_BATCH_SQL, SqlBatchWriter
from storage.files import hash_content, hash_file, read_json_lines

ARTIFACT_LOOKUP = """
SELECT id,status FROM se_liga_brasil.ingestion_artifact WHERE source_id=%(source_id)s
AND resource_id=%(resource_id)s AND content_sha256=%(archive_hash)s
AND parser_version=%(parser_version)s AND scope_key=%(scope_key)s
"""
ARTIFACT_UPSERT = """
INSERT INTO se_liga_brasil.ingestion_artifact(source_id,resource_id,dataset_name,resource_kind,
 source_url,content_sha256,storage_reference,fetched_at,parser_version,scope_key,status)
VALUES(%(source_id)s,%(resource_id)s,%(dataset)s,%(kind)s,%(source_url)s,%(archive_hash)s,
 %(archive_path)s,%(fetched_at)s,%(parser_version)s,%(scope_key)s,'ingesting')
ON CONFLICT(source_id,resource_id,content_sha256,parser_version,scope_key)
DO UPDATE SET status='ingesting' RETURNING id
"""
REJECTION_INSERT = """
INSERT INTO se_liga_brasil.ingestion_rejection(run_id,artifact_id,resource_id,entry_name,
 row_number,reason_code,payload_sha256,details)
SELECT %(run_id)s,%(artifact_id)s,r->>'resourceId',r->>'entryName',(r->>'rowNumber')::int,
 r->>'reasonCode',r->>'payloadSha256',coalesce(r->'details','{}'::jsonb)
FROM jsonb_array_elements(%(rejections)s::jsonb) r
"""


def verify_staging_files(
    validated: ValidatedArtifact, expected_parser_version: str = PARSER_VERSION
) -> None:
    if validated.parser_version != expected_parser_version:
        raise IngestionError("PARSER_VERSION_MISMATCH")
    checksums = (
        (validated.records_path, validated.records_sha256),
        (validated.rejected_path, validated.rejected_sha256),
        (validated.artifact.path, validated.artifact.sha256),
    )
    if any(hash_file(path) != expected for path, expected in checksums):
        raise IngestionError("VALIDATION_CHECKSUM_MISMATCH")


def verify_staged_record(record: dict) -> None:
    data = record["normalizedData"]
    hash_data = {key: value for key, value in data.items() if key != "storageReference"}
    if hash_content(hash_data) != record["contentSha256"]:
        raise IngestionError("STAGED_RECORD_HASH_MISMATCH")
    if "documentSha256" in data:
        from pathlib import Path

        if hash_file(Path(data["storageReference"])) != data["documentSha256"]:
            raise IngestionError("DOCUMENT_CHECKSUM_MISMATCH")


class IngestionRepository:
    def __init__(
        self, connection, source, projector, progress=None, parser_version=PARSER_VERSION
    ) -> None:
        self.connection = connection
        self.source = source
        self.projector = projector
        self.lock_key = f"se_liga_brasil:ingestion:{source.code}"
        self.batch_writer = SqlBatchWriter(connection)
        self.source_id: int | None = None
        self.run_id: str | None = None
        self.progress = progress
        self.parser_version = parser_version

    def begin_run(self, run_id: str, configuration: dict) -> None:
        locked = self.connection.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s)) AS acquired", (self.lock_key,)
        ).fetchone()["acquired"]
        if not locked:
            raise IngestionError("CRAWLER_ALREADY_RUNNING_IN_DATABASE")
        self.connection.execute(
            """
            UPDATE se_liga_brasil.ingestion_run 
                SET status='interrupted',finished_at=now()
            WHERE status='running' AND configuration->>'source_code'=%s
        """,
            (self.source.code,),
        )
        self.connection.execute(
            """
            INSERT INTO se_liga_brasil.ingestion_run(id,status,configuration)
                VALUES(%s,'running',%s)
        """,
            (run_id, Jsonb(configuration | {"source_code": self.source.code})),
        )
        self.run_id = run_id
        self.source_id = self.connection.execute(
            """
            INSERT INTO se_liga_brasil.source(code,publisher,official_url,acquisition_method)
            VALUES(%s,%s,%s,%s)
            ON CONFLICT(code) DO UPDATE SET publisher=excluded.publisher RETURNING id
        """,
            (
                self.source.code,
                self.source.publisher,
                self.source.official_url,
                self.source.acquisition_method,
            ),
        ).fetchone()["id"]

    def finish_run(self, status: str, summary: dict) -> None:
        self.connection.execute(
            """
            UPDATE se_liga_brasil.ingestion_run
            SET status=%s,finished_at=now(),summary=%s WHERE id=%s
        """,
            (status, Jsonb(summary), self.run_id),
        )
        self.connection.execute("SELECT pg_advisory_unlock(hashtext(%s))", (self.lock_key,))

    def build_artifact_parameters(self, validated: ValidatedArtifact) -> dict:
        artifact = validated.artifact
        resource = artifact.resource
        return {
            "source_id": self.source_id,
            "run_id": self.run_id,
            "resource_id": resource.resource_id,
            "dataset": resource.dataset,
            "kind": resource.kind,
            "source_url": resource.url,
            "archive_hash": artifact.sha256,
            "archive_path": str(artifact.path),
            "fetched_at": artifact.fetched_at,
            "parser_version": validated.parser_version,
            "scope_key": validated.scope_key,
        }

    def ingest_validated_artifact(
        self, validated: ValidatedArtifact, batch_size: int
    ) -> IngestionSummary:
        verify_staging_files(validated, self.parser_version)
        parameters = self.build_artifact_parameters(validated)
        existing = self.connection.execute(ARTIFACT_LOOKUP, parameters).fetchone()
        if existing and existing["status"] == "completed":
            return IngestionSummary(unchanged=validated.summary["valid"], skipped_artifact=True)
        with self.connection.transaction():
            self.connection.execute("SET LOCAL statement_timeout='60s'")
            parameters["artifact_id"] = self.connection.execute(
                ARTIFACT_UPSERT, parameters
            ).fetchone()["id"]
            self.connection.execute(TEMP_BATCH_SQL)
            summary = self.ingest_staged_batches(validated, parameters, batch_size)
            self.save_validation_rejections(validated, parameters, batch_size)
            summary.rejected = self.count_artifact_rejections(parameters)
            self.complete_artifact(parameters, summary)
            self.connection.execute("DROP TABLE pg_temp.ingestion_batch")
        return summary

    def ingest_staged_batches(self, validated, parameters, batch_size) -> IngestionSummary:
        summary = IngestionSummary()
        ingested_records = 0
        for records in batched(read_json_lines(validated.records_path), batch_size):
            for record in records:
                verify_staged_record(record)
            batch_parameters = parameters | {"records": Jsonb(records)}
            self.batch_writer.execute_statements("reconcile", batch_parameters)
            classifications = self.batch_writer.summarize_batch()
            self.projector.project_batch(batch_parameters, validated.artifact.resource.kind)
            accepted = self.batch_writer.summarize_batch()
            for category in ("new", "changed", "unchanged", "stale"):
                setattr(
                    summary,
                    category,
                    getattr(summary, category)
                    + (classifications if category == "stale" else accepted).get(category, 0),
                )
            ingested_records += len(records)
            if self.progress:
                self.progress(
                    "ingest_progress",
                    processed_records=ingested_records,
                    total_records=validated.summary["valid"],
                )
        return summary

    def save_validation_rejections(self, validated, parameters, batch_size) -> None:
        for rejections in batched(read_json_lines(validated.rejected_path), batch_size):
            self.connection.execute(
                REJECTION_INSERT, parameters | {"rejections": Jsonb(rejections)}
            )

    def count_artifact_rejections(self, parameters) -> int:
        return self.connection.execute(
            """
            SELECT count(*)::int AS count FROM se_liga_brasil.ingestion_rejection
            WHERE run_id=%(run_id)s AND artifact_id=%(artifact_id)s
        """,
            parameters,
        ).fetchone()["count"]

    def iter_resource_rejections(self, resource_id: str):
        last_id = 0
        while True:
            rows = self.connection.execute(
                """
                SELECT id,entry_name,row_number,reason_code,details
                FROM se_liga_brasil.ingestion_rejection
                WHERE run_id=%s AND resource_id=%s AND id>%s ORDER BY id LIMIT 500
                """,
                (self.run_id, resource_id, last_id),
            ).fetchall()
            if not rows:
                return
            yield from rows
            last_id = rows[-1]["id"]

    def complete_artifact(self, parameters, summary: IngestionSummary) -> None:
        status = "partial" if summary.rejected else "completed"
        self.connection.execute(
            """
            UPDATE se_liga_brasil.ingestion_artifact 
                SET status=%s,ingested_at=now(),summary=%s WHERE id=%s
        """,
            (status, Jsonb(asdict(summary)), parameters["artifact_id"]),
        )

    def reject_resource(self, resource_id: str, error: IngestionError) -> None:
        rejection = {"resourceId": resource_id, "reasonCode": error.code, "details": error.details}
        self.connection.execute(
            REJECTION_INSERT,
            {"run_id": self.run_id, "artifact_id": None, "rejections": Jsonb([rejection])},
        )
