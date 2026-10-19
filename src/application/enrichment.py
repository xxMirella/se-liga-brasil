"""Service commands separate missing-data diagnosis from source collection."""

from database.operations import PROJECT_ROOT, connect_database
from service.completeness.assessment import assess_completeness
from service.legislative_collection.coverage import career_collectors
from service.maintenance.data_gap_cleanup import purge_processed_gaps
from service.orchestration.data_collection import orchestrate_collection


def execute_enrichment_command(arguments) -> dict:
    storage = arguments.storage_directory or PROJECT_ROOT / "data/enrichment"
    with connect_database(arguments.env_file) as connection:
        if arguments.command == "purge-gaps":
            return purge_processed_gaps(connection)
        if arguments.command == "audit-completeness":
            return assess_completeness(connection, storage.resolve(), arguments.person_id)
        return orchestrate_collection(
            connection,
            storage.resolve(),
            arguments.person_id,
            refresh_assessment=arguments.command != "dispatch",
            field_names=arguments.fields.split(",") if getattr(arguments, "fields", None) else None,
            career_collectors=career_collectors(connection, storage.resolve())
            if getattr(arguments, "include_career", False)
            else None,
        )
