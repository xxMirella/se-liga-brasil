"""Reproduce the Senate audit from the archived official roster; no network required."""

import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from crawlers.senado.current_roster_report import parse_current_roster_report
from service.political_dashboard.orientation_composition import orientation_composition
from service.political_dashboard.orientation_timeline import orientation_cell

DIRECTORY = Path("data/political-orientation")
ARCHIVE_PATH = DIRECTORY / "sources/senate-current-roster-20261028.html"
SOURCE_URL = "https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores?formato=html"


def archived_report():
    raw = ARCHIVE_PATH.read_bytes()
    members = parse_current_roster_report(raw.decode())
    matched = re.search(r"28/10/2026 \d{2}:\d{2}:\d{2}", raw.decode())
    if not matched:
        raise ValueError("OFFICIAL_REPORT_GENERATION_DATE_NOT_FOUND")
    generated_at = datetime.strptime(matched[0], "%d/%m/%Y %H:%M:%S").isoformat()
    return raw, members, generated_at


def audited_composition(counts):
    directory = Path("data/political-dashboard")
    manifest = json.loads((directory / "manifest-2026.json").read_text())
    entry = next(row for row in manifest["partitions"]
                 if row["institution_code"] == "senado" and row["territory_code"] == "BR")
    existing = json.loads((directory / entry["file"]).read_text())
    if counts != Counter({g["abbreviation"]: g["count"] for g in existing["political_parties"]}):
        raise ValueError("LOCAL_SENATE_COMPOSITION_DIFFERS_FROM_OFFICIAL_REPORT")
    comparison = {"file": entry["file"], "snapshot_on": existing["snapshot_on"],
                  "party_counts_unchanged": True}
    return dict(existing, snapshot_on="2026-10-28"), comparison


def main():
    raw, members, generated_at = archived_report()
    counts = Counter(row["political_party"] for row in members)
    composition, comparison = audited_composition(counts)
    classified = orientation_composition(composition, 2026)
    report = {
        "schema_version": "senate_orientation_2026_audit.v1", "reference_on": "2026-10-28",
        "official_report_generated_at": generated_at, "source_url": SOURCE_URL,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "hash_scope": "original_http_response_body_bytes", "archive_path": str(ARCHIVE_PATH),
        "total": 81, "expected_seats": 81, "members": members,
        "political_party_counts": dict(counts),
        "orientation_counts": {g["orientation_category"]: g["count"]
                               for g in classified["political_parties"]},
        "orientation_summary": classified["orientation_summary"],
        "timeline_cell": orientation_cell(composition, 2026, "legislative"),
        "local_snapshot_comparison": comparison,
        "limitation": "Síntese editorial: survey 2022 aplicado explicitamente à composição "
                      "oficial de 28/10/2026; PSD/MDB têm autodeclarações divergentes. "
                      "Não rotula individualmente os senadores nem antecipa posse em 2027.",
    }
    output = DIRECTORY / "senate-2026-audit-20261028.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["orientation_summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
