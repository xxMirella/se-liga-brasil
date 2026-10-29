"""Archive official evidence for the Chamber 2020–2026 integration; never changes raw histories."""

import argparse
import json
from pathlib import Path

from crawlers.camara.official_snapshot_capture import capture_chamber_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage", type=Path, required=True,
                        help="dedicated immutable capture directory; do not reuse a dated capture")
    options = parser.parse_args()
    if (options.storage / "sources.json").exists():
        raise ValueError("CHAMBER_CAPTURE_ALREADY_EXISTS_USE_NEW_DIRECTORY")
    evidence = capture_chamber_snapshot(options.storage)
    print(json.dumps({"resources": len(evidence), "storage": str(options.storage)}))


if __name__ == "__main__":
    main()
