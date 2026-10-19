"""Collect a daily official cohort and publish canonical, explicitly scoped frequency."""

import json
from collections import Counter
from datetime import date
from urllib.parse import urlencode

from crawlers.camara.session_presence import parse_daily_session_presence, parse_presence_roster
from crawlers.camara.voting_identity import cached_profile_artifact, resolve_voting_people
from normalization.text import fold_text
from service.analytical_datasets.storage import connect_analytical_engine, file_sha256
from service.ingestion.contracts import IngestionError
from storage.files import create_private_directory, hash_content, save_json


def collect_daily_presence(acquisition, connection, day):
    query = urlencode(
        {
            "data": day.strftime("%d/%m/%Y"),
            "numMatriculaParlamentar": "",
            "siglaPartido": "",
            "siglaUF": "",
        }
    )
    base = "https://www.camara.leg.br/SitCamaraWS/"
    artifact = acquisition.acquire(
        base + "sessoesreunioes.asmx/ListarPresencasDia?" + query,
        "camara_daily_session_presence",
        ".xml",
    )
    cohort, legislature = parse_daily_session_presence(artifact.path.read_bytes(), day)
    roster_artifact = acquisition.acquire(
        base + "Deputados.asmx/ObterDeputados", "camara_legacy_roster", ".xml"
    )
    roster = parse_presence_roster(roster_artifact.path.read_bytes())
    roster_year = date.fromisoformat(roster_artifact.fetched_at[:10]).year
    if legislature != 51 + (roster_year - 1999) // 4:
        raise IngestionError("CAMARA_HISTORICAL_CARD_MAPPING_UNVERIFIED")
    profiles = {}
    for member in roster.values():
        profile = cached_profile_artifact(acquisition.configuration, member["key"])
        if profile:
            profiles[member["key"]] = profile
    identities = resolve_voting_people(connection, profiles)
    rows = canonical_presence_records(cohort, roster, identities, artifact, roster_artifact, day)
    return rows, {
        "source_people": len(cohort),
        "resolved_people": len(rows),
        "unresolved_people": len(cohort) - len(rows),
        "source_status_counts": dict(Counter(row["presence_status"] for row in cohort)),
        "scope": "plenary_day_and_sessions_not_individual_vote",
        "expected_voters_by_committee": "not_verified",
        "evidence_sha256": artifact.sha256,
    }


def canonical_presence_records(cohort, roster, identities, artifact, roster_artifact, day):
    rows, people = [], set()
    for source in cohort:
        member = roster.get(source["card"])
        if not member or fold_text(member["name"] or "") != fold_text(source["name"] or ""):
            continue
        if member["uf"] != source["uf"] or member["key"] not in identities:
            continue
        identity = identities[member["key"]]
        if identity["person_id"] in people:
            raise IngestionError("CAMARA_SESSION_DUPLICATE_CANONICAL_PERSON")
        people.add(identity["person_id"])
        rows.append(
            {
                "person_id": identity["person_id"],
                "occurred_on": day.isoformat(),
                "institution_code": "camara",
                "presence_status": source["presence_status"],
                "sessions": source["sessions"],
                "scope": "plenary_day",
                "evidence_sha256": hash_content(
                    [artifact.sha256, roster_artifact.sha256, identity["artifact"].sha256]
                ),
            }
        )
    return rows


def publish_daily_presence(directory, storage, day, rows, coverage):
    relative = f"attendance/camara/daily/year={day.year}/month={day.month:02}/day={day.day:02}"
    partition = directory / relative
    create_private_directory(partition)
    manifest = {
        "schema_version": "person-session-presence-v1",
        "coverage": coverage,
        "occurred_on": day.isoformat(),
        "row_count": len(rows),
    }
    if rows:
        source = partition / "records.ndjson"
        source.write_text("".join(json.dumps(row) + "\n" for row in rows))
        source.chmod(0o600)
        temporary = partition / "building.parquet"
        with connect_analytical_engine(directory / "temporary") as engine:
            engine.execute("CREATE TABLE records AS SELECT * FROM read_json_auto(?)", [str(source)])
            engine.execute("COPY records TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(temporary)])
        digest = file_sha256(temporary)
        output = partition / f"presence-{digest}.parquet"
        temporary.replace(output)
        output.chmod(0o600)
        storage.upload_immutable(relative + "/" + output.name, output, digest)
        manifest.update(parquet_file=output.name, parquet_sha256=digest)
    response = storage.request(
        "POST",
        storage.object_path(relative + "/manifest.json"),
        content=json.dumps(manifest).encode(),
        headers={"Content-Type": "application/json", "x-upsert": "true"},
    )
    response.raise_for_status()
    save_json(partition / "manifest.json", manifest)
    return manifest
