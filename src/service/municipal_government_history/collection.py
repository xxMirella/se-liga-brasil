"""Create audited municipal executive inputs for annual materialization."""

import json
from datetime import date

from crawlers.municipal_government.documents import document_text
from crawlers.municipal_government.parsing import (
    evidence,
    parse_sp_dossier,
    parse_sp_dossier_interims,
)
from crawlers.municipal_government.rio_parsing import (
    official_rio_period,
    parse_rio_crivella_and_succession,
    parse_rio_municipal_archive,
)
from normalization.executive_intervals import remove_documented_temporary_overlap
from storage.files import save_json


def documented_rio_recent_periods(artifacts):
    records = parse_rio_crivella_and_succession(artifacts["rio_timeline_data"])
    timeline = json.loads(artifacts["rio_timeline_data"].path.read_text(encoding="utf-8-sig"))
    if not any(
        row.get("ano") == "2021" and "01/01/2021-31/12/2024" in row.get("rio", "")
        for row in timeline
    ):
        raise ValueError("MUNICIPAL_GOVERNMENT_RIO_2021_PERIOD_NOT_FOUND")
    term_2021 = official_rio_period(
        artifacts["rio_2026"],
        "Eduardo da Costa Paes",
        "2021-01-01",
        "2025-01-01",
        "2021e 2024",
    )
    term_2021["evidence"].append(evidence(artifacts["rio_timeline_data"], "ano2021.rio"))
    records.extend(
        [
            term_2021,
            official_rio_period(
                artifacts["rio_2025_prefecture"],
                "Eduardo da Costa Paes",
                "2025-01-01",
                "2026-03-20",
                "foram empossados nesta quarta-feira (1º/01)",
            ),
            official_rio_period(
                artifacts["rio_2026"],
                "Eduardo Cavaliere",
                "2026-03-20",
                None,
                "declarou publicamente que Eduardo Cavaliere é o novo prefeito",
            ),
        ]
    )
    for row in records:
        if row["name"] == "Eduardo da Costa Paes":
            row["evidence"].append(evidence(artifacts["rio_2026"], "Paes hands over to Cavaliere"))
    return records


def extend_municipal_observations(records, artifacts):
    sp_text = " ".join(document_text(artifacts["sp_observation"]).split())
    rio_text = document_text(artifacts["rio_observation"])
    if "RICARDO NUNES, Prefeito do Município de São Paulo" not in sp_text:
        raise ValueError("MUNICIPAL_GOVERNMENT_SP_OBSERVATION_NOT_FOUND")
    if "Eduardo Cavaliere" not in rio_text or "11/09/2026" not in rio_text:
        raise ValueError("MUNICIPAL_GOVERNMENT_RIO_OBSERVATION_NOT_FOUND")
    for row in records:
        if row["name"] == "Ricardo Nunes" and row.get("exercise_kind") == "holder":
            row["observed_through"] = "2026-10-01"
            row["evidence"].append(
                evidence(artifacts["sp_observation"], "Decreto65.606/2026; signature")
            )
        if row["name"] == "Eduardo Cavaliere":
            row["observed_through"] = "2026-09-11"
            row["evidence"].append(
                evidence(artifacts["rio_observation"], "Published11/09/2026; mayor")
            )
    return records


def collect_municipal_government_history(artifacts, output_path):
    records = parse_sp_dossier(artifacts["sp_dossier"])
    records.extend(parse_sp_dossier_interims(artifacts["sp_dossier"]))
    records = remove_documented_temporary_overlap(records)
    records.extend(parse_rio_municipal_archive(artifacts["rio_archive"]))
    records.extend(documented_rio_recent_periods(artifacts))
    records = extend_municipal_observations(records, artifacts)
    payload = {
        "schema_version": "historical_executive_evidence.v1",
        "exercises": records,
        "year_start": 1899,
        "year_end": date.today().year,
        "coverage": "documented_partial",
        "limitations": [
            "interims_not_exhaustive",
            "historical_party_affiliation_unknown",
            "sp_dossier_discrepant_interim_tables_not_reconciled",
            "hour_precision_interims_not_materialized",
            "rio_municipal_era_only_from1975_no_guanabara_governors",
        ],
        "canonical_person_linking": "source_qualified_identifiers_not_canonical_people",
    }
    save_json(output_path, payload)
    return dict(output=str(output_path), records=len(records), coverage=payload["coverage"])
