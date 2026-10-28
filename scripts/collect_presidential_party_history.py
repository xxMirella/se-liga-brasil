"""Archive and apply reviewed presidential party periods without guessing missing affiliations."""

import argparse
import json
from pathlib import Path

import httpx

from crawlers.presidency.acquisition import PresidencyAcquisition, PresidencyConfiguration
from crawlers.presidency.reviewed_transcriptions import reviewed_party_transcriptions
from service.presidential_history.exercise_capacity import enrich_documented_exercise_capacity
from service.presidential_history.government_context import enrich_documented_government_context
from service.presidential_history.party_collection import collect_presidential_party_periods
from storage.files import save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage", type=Path, default=Path("data/presidency-history"))
    arguments = parser.parse_args()
    target = arguments.storage / "historical-executive-evidence.json"
    evidence = json.loads(target.read_text())
    with httpx.Client(timeout=45) as client:
        acquisition = PresidencyAcquisition(PresidencyConfiguration(arguments.storage), client)
        evidence["exercises"] = enrich_documented_exercise_capacity(
            acquisition, evidence["exercises"],
        )
        evidence["exercises"] = enrich_documented_government_context(
            acquisition, evidence["exercises"], reviewed_party_transcriptions(),
        )
        evidence["exercises"] = collect_presidential_party_periods(
            acquisition,
            evidence["exercises"],
            reviewed_party_transcriptions(),
        )
    save_json(target, evidence)
    print(
        json.dumps(
            {
                "exercises": len(evidence["exercises"]),
                "reviewed_party_periods": sum(
                    len(row.get("political_party_periods", [])) for row in evidence["exercises"]
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
