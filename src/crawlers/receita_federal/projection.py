"""Project CNPJ facts through the existing ingestion batch writer."""

from service.ingestion.contracts import IngestionError


class BusinessProjectionWriter:
    def __init__(self, writer):
        self.writer = writer

    def project_batch(self, parameters, resource_kind):
        if resource_kind not in {"companies", "establishments", "partners"}:
            raise IngestionError("CNPJ_UNSUPPORTED_KIND")
        self.writer.execute_statements("receita_federal_business", parameters)
