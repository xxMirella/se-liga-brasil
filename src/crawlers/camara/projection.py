"""Source projections over the shared batch reconciliation engine."""


class CamaraProjectionWriter:
    def __init__(self, writer) -> None:
        self.writer = writer

    def project_batch(self, parameters, resource_kind) -> None:
        if resource_kind == "camara_attendance":
            self.writer.execute_statements("camara_attendance", parameters)
            return
        projections = {
            "camara_profile": "camara_profile",
            "camara_propositions": "camara_propositions",
            "camara_payroll": "camara_payroll",
        }
        if resource_kind.startswith("camara_legislative_"):
            self.writer.execute_statements("camara_legislative_history", parameters)
            return
        self.writer.execute_statements("camara_common", parameters)
        self.writer.execute_statements(projections[resource_kind], parameters)
        if resource_kind == "camara_profile":
            self.writer.execute_statements("person_current_public_office", parameters)
