"""Reproduce dated expert-survey means from original CC0 data, never interpolate years."""

import csv
import hashlib
import json
from pathlib import Path
from statistics import fmean, stdev

SOURCE_SHA256 = "74fe0ac6948c4da4bc0c8e824d547159d9c6adcec10c8cafcefec574c90d6754"
SOURCE_URL = "https://doi.org/10.7910/DVN/MFIXKW"
EXPLICIT_SOURCE_LABELS = {
    "mdb": "MDB", "uniao": "UNIÃO", "ptb": "PTB", "pdt": "PDT", "pt": "PT",
    "dem": "DEM", "p_cdo_b": "PCdoB", "psb": "PSB", "psdb": "PSDB", "ptc": "PTC",
    "agir": "AGIR", "psc": "PSC", "pmn": "PMN", "prp": "PRP", "pps": "PPS",
    "cdd": "CIDADANIA", "pv": "PV", "avante": "AVANTE", "progressistas": "PP",
    "progre": "PP", "pstu": "PSTU", "pcb": "PCB", "prtb": "PRTB", "phs": "PHS",
    "dc": "DC", "pco": "PCO", "pode": "PODE", "podemos": "PODEMOS", "psl": "PSL",
    "prb": "PRB", "rep": "REPUBLICANOS", "psol": "PSOL", "pr": "PR", "pl": "PL",
    "psd": "PSD", "ppl": "PPL", "patri": "PATRIOTA", "pros": "PROS",
    "sdd": "SOLIDARIEDADE", "novo": "NOVO", "rede": "REDE", "pmb": "PMB", "up": "UP",
}


def survey_observations(rows):
    observations = []
    for column in rows[0]:
        if not column.startswith(("ideol_18_", "ideol_22_")):
            continue
        year = 2000 + int(column.split("_")[1])
        label = EXPLICIT_SOURCE_LABELS[column[9:]]
        values = [float(row[column]) for row in rows if row[column].strip()]
        if not values or any(not 0 <= value <= 10 for value in values):
            raise ValueError("EXPERT_SURVEY_SCORE_OUTSIDE_DOCUMENTED_SCALE")
        observations.append({
            "political_party": label, "year_start": year, "year_end": year,
            "reference_year": year, "methodology_id": "bolognesi_expert_mean_0_10_v1",
            "score": round(fmean(values), 8), "respondents": len(values),
            "respondent_standard_deviation": round(stdev(values), 8),
            "source_column": column, "source_url": SOURCE_URL,
            "source_sha256": SOURCE_SHA256, "status": "observed_expert_estimate",
        })
    return observations


def main():
    source = Path("data/political-orientation/sources/df_experts.csv")
    if hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("ORIGINAL_EXPERT_SURVEY_CHECKSUM_MISMATCH")
    with source.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter=";"))
    catalog = {"schema_version": "dated_political_orientation_catalog.v1",
               "version": "2026-10-27.1", "license": "CC0-1.0 source data",
               "observations": survey_observations(rows)}
    target = Path("src/service/political_dashboard/political_orientation_catalog.json")
    target.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"observations": len(catalog["observations"]), "expert_rows": len(rows)}))


if __name__ == "__main__":
    main()
