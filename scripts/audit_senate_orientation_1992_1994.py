"""Write the reproducible validation of the 1992-1994 Senate snapshots (no network, no database)."""

import json
from collections import Counter
from pathlib import Path

from service.political_dashboard.senate_orientation_1992_1994 import (
    SNAPSHOT_YEARS,
    senate_1992_1994_evidence,
    snapshot_for,
    snapshot_summary,
)

OUTPUT = Path("data/political-dashboard/senate-itamar-1992-1994-validation-20261028.json")


def integrity_checks(seats):
    occupants = [seat["occupant_source_id"] for seat in seats]
    per_uf = Counter(seat["uf"] for seat in seats)
    return {
        "seat_count_is_81": len(seats) == 81,
        "every_uf_has_three_seats": len(per_uf) == 27 and set(per_uf.values()) == {3},
        "no_person_counted_twice": len(set(occupants)) == len(occupants),
    }


def snapshot_report(year):
    snapshot_on = f"{year}-12-31"
    seats = snapshot_for(snapshot_on)["seats"]
    return {
        "snapshot_on": snapshot_on,
        "summary": snapshot_summary(snapshot_on),
        "integrity_checks": integrity_checks(seats),
        "members": seats,
    }


def main():
    evidence = senate_1992_1994_evidence()
    report = {
        "schema_version": "senate_itamar_1992_1994_validation.v1",
        "reference_on": "2026-10-28",
        "classification_source": evidence["classification_source"],
        "seat_events": evidence["seat_events"],
        "documented_gaps": evidence["documented_gaps"],
        "snapshots": [snapshot_report(year) for year in SNAPSHOT_YEARS],
        "database_consulted": False,
        "records_written_to_database": 0,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
