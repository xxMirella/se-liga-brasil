"""P1-D: serving dataset with the finished majority panorama document (one row)."""

from datetime import date

from service.majority_panorama.builder import build_majority_panorama
from service.majority_panorama.document_codec import encode_document
from service.serving.builder import DatasetSpec
from service.serving.release import SERVING_SCHEMA

DATASET_NAME = "majority_panorama_document"
DOCUMENT_TABLE = f"{SERVING_SCHEMA}.{DATASET_NAME}"
COLUMNS_DDL = "document jsonb NOT NULL, generated_on date NOT NULL"
COLUMNS = ("document", "generated_on")


def assemble_panorama(connection, today):
    """The same assembly the live reader does, fed by this connection (no process cache)."""
    from types import SimpleNamespace

    from application.majority_panorama_reader import DashboardPanoramaSource
    from application.political_dashboard_reader import PoliticalDashboardReader

    dashboard = PoliticalDashboardReader(
        SimpleNamespace(read=lambda operation: operation(connection)), lambda: today
    )
    return build_majority_panorama(DashboardPanoramaSource(dashboard.fetch, today), today)


def majority_panorama_spec(connection, as_of: date, *, today: date | None = None) -> DatasetSpec:
    """`today` is the portal's calendar day (America/Belem); `as_of` stays the release day."""
    today = today or _portal_today()
    panorama = assemble_panorama(connection, today)
    return DatasetSpec(
        name=DATASET_NAME,
        columns_ddl=COLUMNS_DDL,
        columns=COLUMNS,
        rows=[(encode_document(panorama), panorama.generated_on)],
    )


def _portal_today() -> date:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("America/Belem")).date()


def read_panorama_document(connection):
    """The stored document (parsed jsonb) or None when the table has no row."""
    row = connection.execute(f"SELECT document FROM {DOCUMENT_TABLE} LIMIT 1").fetchone()
    return None if row is None else row["document"]
