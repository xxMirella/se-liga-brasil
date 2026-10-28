"""Build audited executive inputs without extrapolating party labels or open terms."""

from datetime import date

from crawlers.state_government.parsing import (
    evidence,
    parse_alesp_governor_chronology,
    parse_alesp_provisional_triumvirate,
)
from normalization.executive_intervals import remove_documented_temporary_overlap
from service.state_government_history.annual_observations import (
    additional_annual_observations,
    extend_recent_official_observations,
    extend_verified_observations,
)
from service.state_government_history.political_party_observations import (
    append_contemporaneous_political_party_observations,
)
from service.state_government_history.verified_periods import enrich_alckmin_membership
from storage.files import save_json


def bound_chronology_exercises(records, transition_artifact, lembo_artifact, minimum_year=1889):
    result = []
    for original in records:
        record = dict(original)
        if record["starts_on"] < f"{minimum_year}-01-01":
            continue
        if record["exercise_kind"] == "holder" and not record["ends_before"]:
            record["observed_through"] = record["starts_on"]
            if record["starts_on"] == "2011-01-01":
                record["ends_before"] = "2018-04-06"
                record["evidence"] = record["evidence"] + [
                    evidence(
                        transition_artifact,
                        "Márcio França assume o cargo com a renúncia de Geraldo Alckmin",
                    )
                ]
            if record["starts_on"] == "2001-03-06":
                record["ends_before"] = "2006-03-31"
                record["evidence"] = record["evidence"] + [
                    evidence(
                        lembo_artifact,
                        "Cláudio Lembo, que assumiu nesta sexta-feira, 31/3",
                    )
                ]
        result.append(record)
    return result


def collect_state_government_history(artifacts, output_path, additional_exercises=()):
    records = bound_chronology_exercises(
        parse_alesp_governor_chronology(artifacts["chronology"]),
        artifacts["franca"],
        artifacts["lembo"],
    )
    early = parse_alesp_governor_chronology(artifacts["chronology_early"], require_update=False)
    records.extend(row for row in early if row["starts_on"] >= "1889-11-16")
    records.extend(parse_alesp_provisional_triumvirate(artifacts["chronology_early"]))
    records = remove_documented_temporary_overlap(records)
    records.extend(additional_exercises)

    records.extend(additional_annual_observations(artifacts))
    records = extend_verified_observations(records, artifacts)
    records = extend_recent_official_observations(records, artifacts)

    records = enrich_alckmin_membership(records, artifacts["alckmin_membership"])
    records = append_contemporaneous_political_party_observations(records, artifacts)
    payload = {
        "schema_version": "historical_executive_evidence.v1",
        "exercises": records,
        "coverage": "documented_partial",
        "year_start": 1889,
        "year_end": date.today().year,
        "limitations": [
            "interim_exercises_not_exhaustive",
            "historical_affiliation_partial",
            "unresolved_overlapping_interim_records_preserved",
            "open_exercises_not_extrapolated_beyond_observation",
        ],
        "canonical_person_linking": "source_qualified_identifiers_not_canonical_people",
    }
    save_json(output_path, payload)
    return {"output": str(output_path), "records": len(records), "coverage": "documented_partial"}
