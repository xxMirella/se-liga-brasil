"""Project supported facts while undated deliberations remain source observations."""

from service.ingestion.contracts import IngestionError


class MunicipalProjectionWriter:
    def __init__(self, writer):
        self.writer = writer

    def project_batch(self, parameters, resource_kind):
        if resource_kind not in {"cmsp_projects", "cmsp_authorship", "cmsp_deliberations"}:
            raise IngestionError("CMSP_UNSUPPORTED_DOMAIN")
        self.writer.execute_statements("cmsp_propositions", parameters)
