"""Explicit administrative API collection; reads never implicitly crawl."""

from crawlers.senado.payroll_collection import collect_senado_payroll
from database.operations import PROJECT_ROOT, connect_database
from service.completeness.assessment import assess_completeness
from storage.files import save_json


def execute_senado_payroll_command(arguments):
    storage = (arguments.storage_directory or PROJECT_ROOT / "data/senado-payroll").resolve()
    with connect_database(arguments.env_file) as connection:
        result = collect_senado_payroll(
            connection, storage, arguments.limit, arguments.person_id
        )
        for person in result["people"]:
            assess_completeness(connection, storage, person["person_id"])
    save_json(storage / "collection-result.json", result)
    return result
