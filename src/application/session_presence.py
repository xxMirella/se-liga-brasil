"""Explicit, bounded collection of published daily plenary frequencies."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from crawlers.camara.acquisition import CamaraAcquisition
from crawlers.camara.configuration import OFFICIAL_HOSTS, SOURCE, CrawlerConfiguration
from database.operations import PROJECT_ROOT, connect_database
from service.attendance.session_presence import collect_daily_presence, publish_daily_presence
from service.dataset_storage.supabase import SupabaseDatasetStorage, load_storage_configuration
from service.voting_pipeline.runtime import official_source_acquisition


def execute_session_presence_command(arguments):
    from datetime import date

    if not arguments.start_date:
        raise ValueError("An explicit presence date is required")
    start = date.fromisoformat(arguments.start_date)
    end = date.fromisoformat(arguments.end_date or arguments.start_date)
    today = datetime.now(ZoneInfo("America/Belem")).date()
    if start < date(2000, 1, 1) or end > today or not 0 <= (end - start).days < 31:
        raise ValueError("Select at most 31 published days since 2000")
    directory = arguments.storage_directory or PROJECT_ROOT / "data/enrichment"
    configuration = CrawlerConfiguration(directory.resolve())
    results = []
    with connect_database(arguments.env_file) as connection, httpx.Client(timeout=60) as client:
        storage = SupabaseDatasetStorage(load_storage_configuration(arguments.env_file), client)
        storage.ensure_private_bucket()
        with official_source_acquisition(
            connection,
            configuration,
            SOURCE,
            OFFICIAL_HOSTS,
            CamaraAcquisition,
        ) as acquisition:
            for offset in range((end - start).days + 1):
                day = start + timedelta(days=offset)
                rows, coverage = collect_daily_presence(acquisition, connection, day)
                manifest = publish_daily_presence(
                    directory / "datasets", storage, day, rows, coverage
                )
                results.append({"day": day.isoformat(), "rows": manifest["row_count"], **coverage})
    return {
        "days": results,
        "status": "partial",
        "coverage": "plenary_sessions_not_vote_eligibility",
    }
