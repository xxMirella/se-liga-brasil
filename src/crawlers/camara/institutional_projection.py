"""Canonical personal evidence precedes provider identifiers and office observations."""

from psycopg.types.json import Jsonb

from service.ingestion.contracts import IngestionError


class CamaraInstitutionalProjectionWriter:
    def __init__(self, writer):
        self.writer = writer

    def project_batch(self, parameters, resource_kind):
        self.writer.execute_statements("personal_identities", parameters)
        conflict = self.writer.connection.execute(
            "SELECT count(*) AS conflicts FROM personal_resolution r "
            "JOIN se_liga_brasil.person_identifier i ON i.source_id=%s "
            "AND i.namespace='federal_deputy' "
            "AND i.external_id=r.normalized_data->>'officialDeputyCode' "
            "WHERE i.person_id<>r.person_id",
            (parameters["source_id"],),
        ).fetchone()["conflicts"]
        if conflict:
            raise IngestionError("CAMARA_INSTITUTIONAL_IDENTITY_CONFLICT")
        self.writer.execute_statements("camara_institutional_identity", parameters)
        rows = self.writer.connection.execute(
            "SELECT normalized_data FROM ingestion_batch"
        ).fetchall()
        canonical = parameters | {
            "records": Jsonb([{"normalizedData": row["normalized_data"]} for row in rows])
        }
        self.writer.execute_statements("camara_common", canonical)
        self.writer.execute_statements("camara_institutional_profile", canonical)
        self.writer.execute_statements("person_current_public_office", canonical)
        self.writer.connection.execute("DROP TABLE personal_resolution")
