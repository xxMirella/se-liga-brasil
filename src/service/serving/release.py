"""Release bookkeeping: which build of a serving dataset is currently valid."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

SERVING_SCHEMA = "se_liga_brasil_serving"
RELEASE_TABLE = f"{SERVING_SCHEMA}.dataset_release"


@dataclass(frozen=True)
class DatasetRelease:
    name: str
    version: str
    built_at: datetime
    as_of: date
    row_count: int


def current_release(connection, name, as_of, max_age_days=1) -> DatasetRelease | None:
    """Return the release of `name` if it is at most `max_age_days` older than `as_of`.

    None means "serve from the canonical tables": no release, a stale one, or a database
    where the serving migration has not been applied yet.
    """
    row = _fetch_release_row(connection, name)
    if row is None or as_of - row["as_of"] > timedelta(days=max_age_days):
        return None
    return DatasetRelease(
        name=row["name"],
        version=row["version"],
        built_at=row["built_at"],
        as_of=row["as_of"],
        row_count=row["row_count"],
    )


def _fetch_release_row(connection, name):
    if not _release_table_exists(connection):
        return None
    return connection.execute(
        f"SELECT name,version,built_at,as_of,row_count FROM {RELEASE_TABLE} WHERE name=%s",
        (name,),
    ).fetchone()


def _release_table_exists(connection) -> bool:
    row = connection.execute(
        f"SELECT to_regclass('{RELEASE_TABLE}') IS NOT NULL AS installed"
    ).fetchone()
    return bool(row["installed"])
