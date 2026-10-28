"""Acquire official current state assembly sources with shared source cooldown and cache."""

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from database.operations import connect_database  # noqa: E402
from database.state_assembly_rosters import StateAssemblyRosterRepository  # noqa: E402
from service.ingestion.contracts import IngestionError, SourceDescriptor  # noqa: E402
from service.state_assembly_rosters.acquisition import (  # noqa: E402
    RosterAcquisition,
    RosterConfiguration,
)
from service.state_assembly_rosters.sources import SOURCE_URLS  # noqa: E402
from service.voting_pipeline.runtime import official_source_acquisition  # noqa: E402
from storage.files import load_json, save_json  # noqa: E402

SOURCES = SOURCE_URLS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--storage", type=Path, default=Path("data/state-assembly-rosters"))
    parser.add_argument("--uf", nargs="+", choices=SOURCES, default=list(SOURCES))
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Archive official homepages to locate current roster routes",
    )
    arguments = parser.parse_args()
    configuration = RosterConfiguration(arguments.storage.resolve())
    for uf in arguments.uf:
        collect_selected_source(arguments, configuration, uf)


def collect_selected_source(arguments, configuration, uf):
    previous = load_json(arguments.storage / "failures" / f"{uf}.json", {})
    if previous.get("next_attempt_at") and datetime.fromisoformat(
        previous["next_attempt_at"]
    ) > datetime.now(UTC):
        print(json.dumps({"uf": uf, "status": "deferred", **previous}), flush=True)
        return
    code, url, suffix = SOURCES[uf]
    if arguments.discover:
        location = urlsplit(url)
        url, suffix = f"{location.scheme}://{location.netloc}/", ".html"
    source = SourceDescriptor(code, code.upper(), url)
    try:
        with connect_database(arguments.env_file) as connection:
            StateAssemblyRosterRepository(connection).ensure_official_source(source)
            with official_source_acquisition(
                connection,
                configuration,
                source,
                frozenset({urlsplit(url).hostname}),
                RosterAcquisition,
            ) as acquisition:
                artifact = acquisition.acquire(
                    url,
                    kind="assembly_discovery" if arguments.discover else "assembly_roster",
                    suffix=suffix,
                )
        print(
            json.dumps(
                {
                    "uf": uf,
                    "source_url": url,
                    "path": str(artifact.path),
                    "sha256": artifact.sha256,
                    "fetched_at": artifact.fetched_at,
                }
            ),
            flush=True,
        )
    except IngestionError as error:
        report = {"uf": uf, "source_url": url, "error": error.code, **error.details}
        if error.details.get("retryable") or error.details.get("status") in {
            403,
            429,
            500,
            502,
            503,
            504,
        }:
            delay = max(3600, error.details.get("retry_after_seconds", 0))
            report["next_attempt_at"] = (datetime.now(UTC) + timedelta(seconds=delay)).isoformat()
        save_json(arguments.storage / "failures" / f"{uf}.json", report)
        print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
