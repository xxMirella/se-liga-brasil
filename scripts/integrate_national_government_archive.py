"""Normalize one archived official article while preserving all existing governor observations."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from service.ingestion.contracts import DownloadedArtifact, Resource  # noqa: E402
from service.national_government_history.archive_integration import (  # noqa: E402
    merge_archived_observation,
    normalize_catalog_archive,
)
from storage.files import hash_file, save_json  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("data/national-government-history/historical-executive-evidence.json"),
    )
    options = parser.parse_args()
    manifest = json.loads(options.manifest.read_text())
    path = Path(manifest["path"])
    if hash_file(path) != manifest["sha256"]:
        raise ValueError("OFFICIAL_GOVERNMENT_ARCHIVE_HASH_MISMATCH")
    resource = Resource(
        "archived-official-observation",
        "Government observation",
        manifest["source_url"],
        "government_observation",
        2026,
        "national-government-history",
        file_suffix=".html",
    )
    artifact = DownloadedArtifact(
        resource, path, manifest["sha256"], manifest["fetched_at"], path.stat().st_size, "cached"
    )
    record = normalize_catalog_archive(artifact)
    result = merge_archived_observation(json.loads(options.evidence.read_text()), record)
    save_json(options.evidence, result)
    print(
        json.dumps(
            {
                "observations": len(result["exercises"]),
                "uf": record["territory_code"],
                "observed_on": record["source_observed_on"],
                "political_party_status": record["political_party_status"],
            }
        )
    )


if __name__ == "__main__":
    main()
