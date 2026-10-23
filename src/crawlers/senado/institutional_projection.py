"""National institutional identities use the shared canonical personal resolver."""

from psycopg.types.json import Jsonb

from crawlers.senado.projection import SenateProjectionWriter
from service.ingestion.contracts import IngestionError


class SenateInstitutionalProjectionWriter:
    def __init__(self, writer):
        self.writer = writer

    def project_batch(self, parameters, resource_kind):
        self.writer.execute_statements("personal_identities", parameters)
        self.verify_source_identity_conflicts(parameters["source_id"])
        self.writer.execute_statements("senado_institutional_identity", parameters)
        rows = self.writer.connection.execute(
            "SELECT normalized_data FROM ingestion_batch"
        ).fetchall()
        canonical_records = [{"normalizedData": row["normalized_data"]} for row in rows]
        SenateProjectionWriter(self.writer).project_batch(
            parameters | {"records": Jsonb(canonical_records)}, resource_kind
        )
        self.writer.connection.execute("DROP TABLE personal_resolution")

    def verify_source_identity_conflicts(self, source_id):
        row = self.writer.connection.execute(
            """SELECT count(*) AS conflicts FROM personal_resolution r
            JOIN se_liga_brasil.person_identifier i ON i.source_id=%s
              AND i.namespace='senator'
              AND i.external_id=r.normalized_data->>'officialSenatorCode'
            WHERE i.person_id<>r.person_id""",
            (source_id,),
        ).fetchone()
        if row["conflicts"]:
            raise IngestionError("SENATE_INSTITUTIONAL_IDENTITY_CONFLICT")
