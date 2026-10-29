"""Build the bundled snapshot for /comparacao-de-classificacoes from the model outputs.

Default is a dry run: it reads the survey catalog and `party-model/output/`, reports what would
change and writes nothing. `--apply` replaces
`src/service/party_orientation_comparison/snapshot.json` atomically. Production has no `data/`
directory, so run this locally after every model run and review the diff before deploying.
"""

import argparse
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from service.party_orientation_comparison.snapshot import SNAPSHOT_PATH  # noqa: E402
from service.party_orientation_comparison.snapshot_builder import build_snapshot  # noqa: E402
from service.political_dashboard import political_orientation_catalog as catalog  # noqa: E402

DEFAULT_OUTPUT_DIR = Path("data/political-orientation/party-model/output")


def read_catalog_observations():
    source = Path(catalog.__file__).with_suffix(".json")
    return json.loads(source.read_text())["observations"]


def read_model_documents(output_dir):
    index = json.loads((output_dir / "index.json").read_text())
    return [
        json.loads((output_dir / entry["file"]).read_text()) for entry in index["classifications"]
    ]


def serialize(snapshot):
    return json.dumps(snapshot, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def write_atomically(path, content):
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, prefix=path.name, suffix=".tmp", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(content)
    Path(handle.name).replace(path)


def summarize(snapshot, content, previous):
    rows = sum(len(entry["rows"]) for entry in snapshot["political_parties"])
    return {
        "political_parties": len(snapshot["political_parties"]),
        "rows_with_any_record": rows,
        "model_version": snapshot["model_version"],
        "rubric_version": snapshot["rubric_version"],
        "bytes": len(content.encode()),
        "changed": previous != content,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--apply", action="store_true", help="write snapshot.json")
    arguments = parser.parse_args()
    snapshot = build_snapshot(
        read_catalog_observations(),
        read_model_documents(arguments.output_dir),
        catalog_version=catalog.ORIENTATION_CATALOG_VERSION,
        generated_on=date.today().isoformat(),
    )
    content = serialize(snapshot)
    previous = SNAPSHOT_PATH.read_text() if SNAPSHOT_PATH.exists() else None
    summary = summarize(snapshot, content, previous)
    if arguments.apply and summary["changed"]:
        write_atomically(SNAPSHOT_PATH, content)
    print(json.dumps({**summary, "applied": arguments.apply and summary["changed"]}))


if __name__ == "__main__":
    main()
