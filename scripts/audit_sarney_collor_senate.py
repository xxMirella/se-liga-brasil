"""Audit available Senate evidence during Sarney and Collor without inventing a full roster."""

import json
from collections import Counter
from pathlib import Path

from crawlers.senado.dated_exercise_observations import parse_dated_exercise_observations

DIRECTORY = Path("data/political-orientation")


def observed_exercises():
    sources = [
        (DIRECTORY / "sarney-collor-sources/votes-catalog-1991.xml", 1991),
        (DIRECTORY / "itamar-senate-sources/votes-catalog-1992.html", 1992),
    ]
    rows = []
    for path, year in sources:
        url = ("https://www12.senado.leg.br/dados-abertos/legislativo/plenario/"  # hardcode-ok: URL oficial da fonte arquivada, usada como proveniência  # noqa: E501
               f"votacoes-nominais/lista-de-votacoes-nominais-de-{year}")
        rows.extend(parse_dated_exercise_observations(
            path.read_bytes(), url, "1990-03-15", "1992-10-02",
        ))
    return rows


def existing_annual_evidence():
    directory = Path("data/political-dashboard")
    manifest = json.loads((directory / "senate-history-manifest.json").read_text())
    indexed = {r["year"]: r for r in manifest
               if r["territory_code"] == "BR" and 1985 <= r["year"] <= 1992}
    result = []
    for year in range(1985, 1993):
        row = indexed.get(year)
        payload = json.loads((directory / row["file"]).read_text()) if row else {}
        result.append({"year": year, "source_partition": row["file"] if row else None,
                       "verified_snapshot_count": payload.get("total"),
                       "snapshot_on": payload.get("snapshot_on"),
                       "legislature_roster_records": len(payload.get("historical_roster", [])),
                       "is_complete_composition": False,
                       "limitation": "Lista de legislatura e snapshot parcial não comprovam "
                                     "composição completa ou filiações contínuas."})
    return result


def main():
    rows = observed_exercises()
    years = existing_annual_evidence()
    for year in years:
        observed = [r for r in rows if r["observed_on"].startswith(str(year["year"]))]
        people = {r["source_person_id"] for r in observed}
        year["dated_exercise_observations"] = len(observed)
        year["people_with_dated_votes"] = len(people)
        year["distinct_voting_dates"] = sorted({r["observed_on"] for r in observed})
    report = {"schema_version": "sarney_collor_senate_inventory.v1", "as_of": "2026-10-28",
              "period_start": "1985-03-15", "period_end_exclusive": "1992-10-02",
              "annual_evidence": years, "dated_exercise_observations": rows,
              "party_field_status_counts": dict(Counter(r["political_party_status"] for r in rows)),
              "complete_senate_composition_established": False,
              "limitation": "Votos são evidência pontual, não composição completa nem "
                            "81 cadeiras simultâneas. Preservar mudanças no tamanho da Casa."}
    output = DIRECTORY / "sarney-collor-senate-inventory-1985-1992.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(years, ensure_ascii=False))


if __name__ == "__main__":
    main()
