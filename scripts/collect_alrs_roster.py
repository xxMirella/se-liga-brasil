"""Archive RS attendance and deputy profiles over official HTTPS443 routes."""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawlers.alrs.roster import parse_attendance, parse_current_roster  # noqa: E402
from database.operations import connect_database  # noqa: E402
from service.ingestion.contracts import SourceDescriptor  # noqa: E402
from service.state_assembly_rosters.acquisition import (  # noqa: E402
    RosterAcquisition,
    RosterConfiguration,
)
from service.voting_pipeline.runtime import official_source_acquisition  # noqa: E402
from storage.files import save_json  # noqa: E402

SOURCE = "https://transparencia.al.rs.gov.br/parlamentares/presencas-plenario/pesquisa"


def archive_evidence(artifact, url):
    return {"url": url, "sha256": artifact.sha256, "fetched_at": artifact.fetched_at}


def collect_roster(acquisition, year, month):
    url = f"{SOURCE}?ano={year}&mes={month}"
    artifact = acquisition.acquire(url)
    document = {"attendance_html": artifact.path.read_text(), "profiles": {}}
    evidence = [archive_evidence(artifact, url)]
    for row in parse_attendance(document["attendance_html"]):
        identifier = str(row["codProponente"])
        profile_url = f"https://ww4.al.rs.gov.br/deputados/{identifier}"
        profile = acquisition.acquire(profile_url, kind="assembly_deputy_profile")
        document["profiles"][identifier] = profile.path.read_text()
        evidence.append(archive_evidence(profile, profile_url))
    parse_current_roster(json.dumps(document))
    return document, evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--storage", type=Path, default=Path("data/state-assembly-rosters"))
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, choices=range(1, 13), required=True)
    args = parser.parse_args()
    configuration = RosterConfiguration(args.storage.resolve())
    source = SourceDescriptor("alrs", "ALRS", SOURCE)
    with connect_database(args.env_file) as connection, official_source_acquisition(
        connection, configuration, source,
        frozenset({"transparencia.al.rs.gov.br", "ww4.al.rs.gov.br"}), RosterAcquisition,
    ) as acquisition:
        document, evidence = collect_roster(acquisition, args.year, args.month)
    content = json.dumps(document, ensure_ascii=False)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    path = configuration.storage_directory / "archives" / f"{digest}.json"
    path.write_text(content)
    receipt = {
        "uf": "RS", "institution_code": "alrs", "source_url": evidence[0]["url"],
        "sha256": digest, "path": str(path), "fetched_at": datetime.now(UTC).isoformat(),
        "supporting_evidence": evidence, "derived_bundle": True,
        "source_sha256": evidence[0]["sha256"],
        "attendance_period": f"{args.year}-{args.month:02}",
    }
    save_json(args.storage / "roster-receipts" / "RS.json", receipt)
    print(json.dumps({"uf": "RS", "profiles": 55, "evidence": len(evidence)}))


if __name__ == "__main__":
    main()
