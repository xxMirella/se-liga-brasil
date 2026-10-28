"""Archive the official SAPL current-legislature roster without collecting election candidates."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawlers.interlegis.roster import collect_current_roster  # noqa: E402
from database.operations import connect_database  # noqa: E402
from database.state_assembly_rosters import StateAssemblyRosterRepository  # noqa: E402
from service.ingestion.contracts import SourceDescriptor  # noqa: E402
from service.state_assembly_rosters.acquisition import (  # noqa: E402
    RosterAcquisition,
    RosterConfiguration,
)
from service.voting_pipeline.runtime import official_source_acquisition  # noqa: E402
from storage.files import save_json  # noqa: E402

BASES = {
    "AC": ("aleac", "https://sapl.al.ac.leg.br"),
    "AM": ("aleam", "https://sapl.al.am.leg.br"),
    "PB": ("alpb", "https://sapl3.al.pb.leg.br"),
    "PI": ("alepi", "https://sapl.al.pi.leg.br"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--storage", type=Path, default=Path("data/state-assembly-rosters"))
    parser.add_argument("--uf", choices=BASES, required=True)
    arguments = parser.parse_args()
    code, base = BASES[arguments.uf]
    source = SourceDescriptor(code, code.upper(), base)
    configuration = RosterConfiguration(arguments.storage.resolve())
    with connect_database(arguments.env_file) as connection:
        StateAssemblyRosterRepository(connection).ensure_official_source(source)
        with official_source_acquisition(
            connection,
            configuration,
            source,
            frozenset({urlsplit(base).hostname}),
            RosterAcquisition,
        ) as acquisition:
            roster, legislature = collect_current_roster(acquisition, base, date.today())
    receipt = {
        "uf": arguments.uf,
        "institution_code": code,
        "source_url": roster.resource.url,
        "path": str(roster.path),
        "sha256": roster.sha256,
        "fetched_at": roster.fetched_at,
        "supporting_evidence": [
            {
                "url": legislature.resource.url,
                "sha256": legislature.sha256,
                "fetched_at": legislature.fetched_at,
            }
        ],
    }
    save_json(arguments.storage / "roster-receipts" / f"{arguments.uf}.json", receipt)
    print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()
