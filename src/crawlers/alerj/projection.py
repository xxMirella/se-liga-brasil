"""Apply ALERJ facts and payroll through the generic batch writer."""


class AlerjProjectionWriter:
    def __init__(self, writer):
        self.writer = writer

    def project_batch(self, parameters, resource_kind):
        self.writer.execute_statements("alerj_common", parameters)
        self.writer.execute_statements(resource_kind, parameters)
        self.writer.execute_statements("person_current_public_office", parameters)
