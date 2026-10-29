"""Senate history 1992-1994 load: dry run by default, --apply is explicit and never implicit."""

import json
from datetime import UTC, datetime
from pathlib import Path

from crawlers.senado.historical_period_archive import SenateArchive
from crawlers.senado.historical_period_plan import build_load_plan, load_inventory_senator_ids
from crawlers.senado.historical_period_report import build_report
from database.historical_senate_load import HistoricalSenateWriter
from database.operations import PROJECT_ROOT, connect_database, refresh_person_profiles
from service.ingestion.historical_load import LoadMode, run_historical_load
from storage.files import save_json

REPORT_DIRECTORY = Path("data/political-dashboard")


def execute_senado_history_command(arguments) -> dict:
    mode = LoadMode.APPLY if arguments.apply else LoadMode.DRY_RUN
    archive = SenateArchive(PROJECT_ROOT, arguments.source_directory)
    plan = build_load_plan(archive, load_inventory_senator_ids(PROJECT_ROOT))
    today = datetime.now(UTC).strftime("%Y%m%d")
    with connect_database(arguments.env_file) as connection:
        run = run_historical_load(
            connection,
            HistoricalSenateWriter(connection, _reviewed_links(arguments.reviewed_identities)),
            plan,
            mode,
            after_commit=refresh_person_profiles,
        )
    report = build_report(plan, run, today)
    path = arguments.report_file or PROJECT_ROOT / REPORT_DIRECTORY / (
        f"senate-history-1992-1994-{mode}-report-{today}.json"
    )
    save_json(path, report)
    inserted_key = "inserted" if run.committed else "would_insert"
    return {
        "mode": str(mode),
        "committed": run.committed,
        "idempotent": run.idempotent,
        inserted_key: report[inserted_key],
        "second_pass_inserted": report["second_pass_inserted"],
        "pending_codes": {code: item["count"] for code, item in report["pending"].items()},
        "report": str(path),
    }


def _reviewed_links(path: Path | None) -> dict[str, str]:
    """{"senado_links": [{"senator_id": "17", "person_id": "<uuid>"}]}: approved by a person."""
    if path is None:
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))["senado_links"]
    return {str(row["senator_id"]): str(row["person_id"]) for row in rows}
