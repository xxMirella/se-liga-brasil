"""Publish small monthly attendance snapshots, retaining canonical person IDs."""

import json
from collections import defaultdict

from service.analytical_datasets.storage import connect_analytical_engine, file_sha256
from service.crawling.acquisition import local_run_lock
from storage.files import create_private_directory, load_json, save_json


def publish_attendance_dataset(connection, directory, storage):
    with local_run_lock(directory / "publication-lock"):
        return publish_attendance_snapshot(connection, directory, storage)


def publish_attendance_snapshot(connection, directory, storage):
    rows = connection.execute(
        """SELECT DISTINCT ON (person_id,normalized_value->>'period') normalized_value
        FROM se_liga_brasil.person_fact
        WHERE field_name LIKE 'camara_attendance:%%' AND review_status='verified'
        ORDER BY person_id,normalized_value->>'period',
          normalized_value->>'sourceObservedAt' DESC,id DESC"""
    ).fetchall()
    periods = defaultdict(list)
    for row in rows:
        data = row["normalized_value"]
        periods[data["period"]].append(data)
    storage.ensure_private_bucket()
    manifests = []
    for period, records in sorted(periods.items()):
        manifests.append(publish_attendance_month(directory, storage, period, records))
    return {"partitions": len(manifests), "rows": len(rows), "published": True}


def publish_attendance_month(directory, storage, period, records):
    year, month = period.split("-")
    relative = f"attendance/camara/year={year}/month={month}"
    partition = directory / relative
    create_private_directory(partition)
    source = partition / "records.ndjson"
    source.write_text("".join(json.dumps(row) + "\n" for row in records))
    source.chmod(0o600)
    temporary = partition / "building.parquet"
    with connect_analytical_engine(directory / "temporary") as engine:
        engine.execute(
            "CREATE TEMP TABLE attendance AS "
            "SELECT * FROM read_json_auto(?, format='newline_delimited')", [str(source)],
        )
        engine.execute(
            "COPY attendance TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(temporary)],
        )
    digest = file_sha256(temporary)
    output = partition / f"attendance-{digest}.parquet"
    temporary.replace(output)
    output.chmod(0o600)
    manifest = {
        "schema_version": "person-attendance-monthly-v1", "institution": "camara",
        "year": int(year), "month": int(month), "row_count": len(records),
        "parquet_file": output.name, "parquet_sha256": digest,
        "basis": "plenary_days", "coverage": "collected_people_only",
    }
    if load_json(partition / "manifest.json") == manifest:
        return manifest
    storage.upload_immutable(relative + "/" + output.name, output, digest)
    response = storage.request(
        "POST", storage.object_path(relative + "/manifest.json"),
        content=json.dumps(manifest).encode(),
        headers={"Content-Type": "application/json", "x-upsert": "true"},
    )
    response.raise_for_status()
    save_json(partition / "manifest.json", manifest)
    return manifest
