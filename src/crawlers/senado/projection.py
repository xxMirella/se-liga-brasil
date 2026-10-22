"""Senate profile projection with the shared canonical office snapshot."""


class SenateProjectionWriter:
    def __init__(self, writer):
        self.writer = writer

    def project_batch(self, parameters, resource_kind):
        self.writer.execute_statements("senado_common", parameters)
        if resource_kind == "senado_payroll":
            self.writer.execute_statements("senado_payroll", parameters)
            return
        self.writer.execute_statements("senado_profile", parameters)
        self.writer.execute_statements("person_current_public_office", parameters)
