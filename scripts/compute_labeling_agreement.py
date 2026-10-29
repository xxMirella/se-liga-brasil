"""Agreement (Cohen's kappa) between labelers, and between a labeler and the model.

Usage: compute_labeling_agreement.py PESSOA_A.csv [PESSOA_B.csv] [--model-labels ia_rotulos.json]
Reads the filled `rotulagem.csv` sheets; prints a JSON summary. Offline: no network, no database.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from service.party_discourse_extraction.label_comparison import (  # noqa: E402
    compare_label_sets,
    model_labels,
    read_labels,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("person_a", type=Path)
    parser.add_argument("person_b", type=Path, nargs="?")
    parser.add_argument("--model-labels", type=Path, help="ia_rotulos.json from the labeling run")
    arguments = parser.parse_args()
    labels_a = read_labels(arguments.person_a)
    summary = {"labeled_by_person_a": sum(v["indicador"] != "nenhum" for v in labels_a.values())}
    if arguments.person_b:
        summary["person_a_vs_person_b"] = compare_label_sets(
            labels_a, read_labels(arguments.person_b)
        )
    if arguments.model_labels:
        predictions = model_labels(json.loads(arguments.model_labels.read_text()))
        summary["person_a_vs_model"] = compare_label_sets(labels_a, predictions)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
