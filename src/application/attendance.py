"""Attendance backfill entry point with shared source locks and durable cooldown."""

from functools import partial

import httpx

from crawlers.camara.acquisition import CamaraAcquisition
from crawlers.camara.configuration import (
    OFFICIAL_HOSTS,
    PARSER_VERSION,
    SOURCE,
    CrawlerConfiguration,
)
from crawlers.camara.projection import CamaraProjectionWriter
from database.operations import PROJECT_ROOT, connect_database
from service.attendance.collection import collect_attendance_batch
from service.attendance.dataset import publish_attendance_dataset
from service.dataset_storage.supabase import SupabaseDatasetStorage, load_storage_configuration
from service.legislative_collection.runtime import CollectionDefinition, run_official_collection


def attendance_pipeline(command, configuration, acquisition, repository, *, limit, person_id):
    return collect_attendance_batch(repository, acquisition, limit=limit, person_id=person_id)


def execute_attendance_command(arguments):
    directory = arguments.storage_directory or PROJECT_ROOT / "data/enrichment"
    configuration = CrawlerConfiguration(directory.resolve())
    definition = CollectionDefinition(
        SOURCE, PARSER_VERSION, OFFICIAL_HOSTS, CamaraProjectionWriter, CamaraAcquisition,
    )
    pipeline = partial(attendance_pipeline, limit=arguments.limit, person_id=arguments.person_id)
    with connect_database(arguments.env_file) as connection:
        result = run_official_collection(connection, configuration, definition, pipeline)
        with httpx.Client(timeout=60) as client:
            storage = SupabaseDatasetStorage(
                load_storage_configuration(arguments.env_file), client,
            )
            result["dataset"] = publish_attendance_dataset(
                connection, directory / "datasets", storage,
            )
        return result | {"status": "partial"}
