"""Consolidate verified ALESP committee attendance from official XML snapshots."""

from collections import defaultdict
from datetime import UTC, date, datetime
from hashlib import sha256

from crawlers.alesp.local_records import verified_author_index, xml_rows
from service.ingestion.contracts import IngestionError
from storage.files import hash_content, hash_file, load_json, save_json

EXPORT_URL = (
    "https://www.al.sp.gov.br/repositorioDados/processo_legislativo/"
    "comissoes_permanentes_presencas.xml"
)


def archived_attendance_exports(storage_directory):
    research = storage_directory / "research"
    entries = load_json(research / "catalog-download-manifest.json", [])
    entries += sorted(
        (load_json(path, {}) for path in (storage_directory / "attendance").glob("*.json")),
        key=lambda entry: entry.get("collected_at", ""),
    )
    for entry in entries:
        if entry.get("url") != EXPORT_URL:
            continue
        path = research / entry["file"]
        if not path.is_file():
            continue
        if hash_file(path) != entry["sha256"]:
            raise IngestionError("ALESP_LOCAL_EVIDENCE_CHECKSUM_MISMATCH")
        yield {
            "path": str(path), "url": EXPORT_URL, "sha256": entry["sha256"],
            "fetched_at": entry["collected_at"],
        }


def attendance_identity_index(resolutions, person_ids, roster_path):
    """Committee exports use SPL IDs, bridged by the official deputy roster."""
    return verified_author_index(roster_path, resolutions, person_ids)


def committee_attendance_rows(paths, identity_index):
    meetings = defaultdict(set)
    for path in paths:
        for row in xml_rows(path, "ReuniaoComissaoPresenca"):
            person_id = identity_index.get(row.get("IdDeputado"))
            if not person_id or not row.get("IdReuniao") or not row.get("IdComissao"):
                continue
            try:
                day = date.fromisoformat(row["DataReuniao"][:10]).isoformat()
            except (KeyError, ValueError):
                continue
            meetings[person_id, day[:7]].add((day, row["IdComissao"], row["IdReuniao"]))
    return [
        {
            "personId": person_id, "officialKey": "spl-v2:" + period, "institution": "alesp",
            "period": period, "scope": "committee_presence_observed",
            "identityMethod": "official_profile_to_roster_IdSPL",
            "present": len(events),
            "meetings": [
                {"date": day, "committeeId": committee, "meetingId": meeting}
                for day, committee, meeting in sorted(events)
            ],
        }
        for (person_id, period), events in sorted(meetings.items())
    ]


def fetch_attendance_export(storage_directory, transport):
    content = transport.fetch_bytes(EXPORT_URL, max_bytes=32 * 1024**2)
    digest = sha256(content).hexdigest()
    directory = storage_directory / "attendance"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (digest + ".xml")
    path.write_bytes(content)
    collected_at = datetime.now(UTC).isoformat()
    save_json(directory / (hash_content([digest, collected_at]) + ".json"), {
        "url": EXPORT_URL, "file": str(path.resolve()), "sha256": digest,
        "collected_at": collected_at,
    })
    return {"path": str(path), "url": EXPORT_URL, "sha256": digest, "fetched_at": collected_at}
