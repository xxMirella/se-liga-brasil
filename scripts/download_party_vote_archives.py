"""Download official roll-call archives (Chamber 1991-2026 probe, Senate 1991-2026).

Resumable: files already in the manifest are not requested again.
Usage: .venv/bin/python scripts/download_party_vote_archives.py [--chamber camara|senado]
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crawlers.camara.nominal_vote_archive import (  # noqa: E402
    SMALL_KINDS,
    VOTES_KIND,
    fetch_annual_file,
)
from crawlers.senado.nominal_vote_archive import fetch_year  # noqa: E402
from service.party_vote_analysis.paths import RAW_DIRECTORY  # noqa: E402
from storage.polite_archive import PoliteArchive  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chamber", choices=["camara", "senado"], required=True)
    parser.add_argument("--first-year", type=int, default=1991)
    parser.add_argument("--last-year", type=int, default=2026)
    arguments = parser.parse_args()
    manifest_name = "manifest.json" if arguments.chamber == "camara" else "manifest-senado.json"
    archive = PoliteArchive(RAW_DIRECTORY, manifest_name=manifest_name)
    try:
        for year in range(arguments.first_year, arguments.last_year + 1):
            if arguments.chamber == "camara":
                for kind in (VOTES_KIND, *SMALL_KINDS):
                    fetched = fetch_annual_file(archive, kind, year)
                    print(
                        "camara",
                        kind,
                        year,
                        "ausente" if fetched is None else fetched.bytes,
                        flush=True,
                    )
            if arguments.chamber == "senado":
                fetched = fetch_year(archive, year)
                print("senado", year, "ausente" if fetched is None else fetched.bytes, flush=True)
    finally:
        archive.close()


if __name__ == "__main__":
    main()
