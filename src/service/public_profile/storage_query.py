"""Parameterized queries over bounded, hash-verified local public Parquets."""

from datetime import date, timedelta
from tempfile import TemporaryDirectory

from service.analytical_datasets.public_voting_timeline import (
    LEGACY_PUBLIC_TIMELINE_COLUMNS,
    PUBLIC_TIMELINE_COLUMNS,
)
from service.analytical_datasets.storage import connect_analytical_engine
from service.daily_voting_dataset.contracts import DailyVotingPartition
from service.dataset_storage.read import DatasetReadError
from service.public_profile.contracts import PublicProfileError

MAX_PERIOD_DAYS = 31
SOURCES = ("camara", "senado")


def daily_partitions(query):
    days = (query.end_on - query.start_on).days + 1
    if days > MAX_PERIOD_DAYS:
        raise PublicProfileError("DATASET_PERIOD_TOO_LARGE")
    return [
        DailyVotingPartition(source, query.start_on + timedelta(days=offset))
        for source in SOURCES
        for offset in range(days)
    ]


def exercise_predicate(query, exercises):
    if query.office_kind is None and query.exercise_id is None:
        return "TRUE", []
    clauses, parameters = [], []
    for exercise in exercises[:100]:
        clauses.append("(institution_code=? AND occurred_on>=? AND occurred_on<?)")
        parameters.extend(
            [
                exercise["institution_code"],
                str(exercise["starts_on"]),
                str(exercise["ends_before"] or date.max),
            ]
        )
    return "(" + " OR ".join(clauses) + ")" if clauses else "FALSE", parameters


def validate_public_parquet(engine, path, manifest):
    fields = {
        row[0]: row[1]
        for row in engine.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]).fetchall()
    }
    expected = (PUBLIC_TIMELINE_COLUMNS if manifest["schema_version"].endswith(".v2")
                else LEGACY_PUBLIC_TIMELINE_COLUMNS)
    if fields != expected:
        raise DatasetReadError("DATASET_PUBLIC_SCHEMA_INVALID")
    invalid = engine.execute(
        "SELECT count(*),count(*) FILTER (WHERE institution_code IS DISTINCT FROM ? "
        "OR occurred_on IS DISTINCT FROM ? OR date_precision IS DISTINCT FROM 'day') "
        "FROM read_parquet(?)",
        [manifest["institution_code"], manifest["occurred_on"], str(path)],
    ).fetchone()
    if invalid != (manifest["row_count"], 0):
        raise DatasetReadError("DATASET_PUBLIC_PARTITION_INVALID")


def query_snapshot(reader, snapshot, query, cursor, exercises):
    if not snapshot["entries"]:
        return []
    paths = []
    with (
        TemporaryDirectory(dir=reader.directory) as temporary,
        connect_analytical_engine(temporary) as engine,
    ):
        for entry in snapshot["entries"]:
            manifest = entry["manifest"]
            partition = DailyVotingPartition(
                entry["source"], date.fromisoformat(manifest["occurred_on"])
            )
            path = reader.parquet_path(partition, manifest)
            validate_public_parquet(engine, path, manifest)
            paths.append(str(path))
        office_sql, office_parameters = exercise_predicate(query, exercises)
        cursor_sql = "AND (occurred_on,voting_id)<(?,?)" if cursor else ""
        parameters = [
            paths,
            query.person_id,
            str(query.start_on),
            str(query.end_on),
            *office_parameters,
        ]
        if cursor:
            parameters.extend([cursor["date"], cursor["id"]])
        parameters.append(query.limit + 1)
        columns = compatible_timeline_selection(engine, paths)
        result = engine.execute(
            f"SELECT {columns} FROM read_parquet(?, union_by_name=true) WHERE person_id=? "
            f"AND occurred_on BETWEEN ? AND ? AND {office_sql} {cursor_sql} "
            "ORDER BY occurred_on DESC,voting_id DESC LIMIT ?",
            parameters,
        )
        names = [column[0] for column in result.description]
        return [dict(zip(names, row, strict=True)) for row in result.fetchall()]


def compatible_timeline_selection(engine, paths):
    available = {row[0] for row in engine.execute(
        "DESCRIBE SELECT * FROM read_parquet(?, union_by_name=true)", [paths]
    ).fetchall()}
    return ",".join(
        f"NULL::VARCHAR AS {column}" if column not in available else column
        for column in PUBLIC_TIMELINE_COLUMNS
    )
