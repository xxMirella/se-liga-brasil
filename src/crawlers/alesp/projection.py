"""ALESP payroll strategy over the shared reconciliation and batch writer."""


class AlespProjectionWriter:
    def __init__(self, writer) -> None:
        self.writer = writer

    def project_batch(self, parameters: dict, resource_kind: str) -> None:
        if resource_kind == "deputy_payroll":
            self.writer.execute_statements("payroll_payments", parameters)
            return
        if resource_kind not in {"alesp_profile", "alesp_propositions"}:
            raise ValueError("Unsupported ALESP resource kind")
        self.writer.execute_statements("alesp_common", parameters)
        self.writer.execute_statements(resource_kind, parameters)
        if resource_kind == "alesp_profile":
            self.writer.execute_statements("person_current_public_office", parameters)
