"""Explicit finite monthly staff payroll collection; public profile reads never crawl."""

from crawlers.senado.cabinet_collection import collect_cabinet_payroll
from database.operations import PROJECT_ROOT, connect_database
from storage.files import save_json


def execute_cabinet_payroll_command(arguments):
    storage = (
        arguments.storage_directory or PROJECT_ROOT / "data/senado-cabinet-payroll"
    ).resolve()
    with connect_database(arguments.env_file) as connection:
        result = collect_cabinet_payroll(
            connection,
            storage,
            arguments.months.split(",") if arguments.months else None,
            maximum=arguments.max_partitions,
        )
    save_json(storage / "collection-result.json", result)
    return result
