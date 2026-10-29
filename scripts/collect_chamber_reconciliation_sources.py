"""Capture an explicit, deduplicated plan of official legacy deputy/legislature pairs."""

import argparse
import json
from pathlib import Path

import httpx

from crawlers.camara.legacy_exercises import LEGACY_ENDPOINT
from crawlers.camara.official_snapshot_capture import capture_chamber_page
from storage.files import save_json


def verified_capture_plan(path):
    pairs = set()
    for row in json.loads(path.read_text()):
        identifier = str(row["id"])
        legislature = int(row["legislature"])
        if not identifier.isdecimal() or not 51 <= legislature <= 57:
            raise ValueError("CHAMBER_LEGACY_CAPTURE_INVALID_IDENTITY")
        pairs.add((identifier, legislature))
    return sorted(pairs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--storage", type=Path, required=True)
    options = parser.parse_args()
    plan = verified_capture_plan(options.plan)
    if (options.storage / "sources.json").exists():
        raise ValueError("CHAMBER_CAPTURE_ALREADY_EXISTS_USE_NEW_DIRECTORY")
    options.storage.mkdir(parents=True, exist_ok=True)
    evidence = []
    with httpx.Client(timeout=60, follow_redirects=False) as client:
        for identifier, legislature in plan:
            url = f"{LEGACY_ENDPOINT}?ideCadastro={identifier}&numLegislatura={legislature}"
            source, next_url = capture_chamber_page(client, options.storage, url)
            if next_url:
                raise ValueError("CHAMBER_LEGACY_UNEXPECTED_PAGINATION")
            evidence.append(source)
    save_json(options.storage / "sources.json", evidence)
    print(json.dumps({"resources": len(evidence), "storage": str(options.storage)}))


if __name__ == "__main__":
    main()
