"""TSE-specific projections; the generic ingestion engine knows no electoral entities."""

from service.ingestion.sql_batches import SqlBatchWriter


class TseProjectionWriter:
    def __init__(self, writer: SqlBatchWriter) -> None:
        self.writer = writer

    def project_batch(self, parameters: dict, resource_kind: str) -> None:
        parameters = parameters | {"is_history": resource_kind == "history"}
        if resource_kind in {"candidate", "history"}:
            self.writer.execute_statements("personal_identities", parameters)
            self.writer.execute_statements("identities", parameters)
        self.writer.execute_statements("facts", parameters)
        if resource_kind in {"candidate", "history"}:
            self.writer.execute_statements("political_parties", parameters)
        projections = {
            "asset": "assets",
            "government_proposal": "documents",
            "criminal_certificate": "documents",
        }
        if resource_kind in projections:
            self.writer.execute_statements(projections[resource_kind], parameters)
        self.writer.execute_statements("activity_context", parameters)
        self.writer.connection.execute("DROP TABLE resolved_batch_identity")
