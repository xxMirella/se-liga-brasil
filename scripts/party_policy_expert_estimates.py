"""Estimativas externas de especialistas (Bolognesi; Power & Zucco) lidas de CSV já arquivado."""

import csv

from party_policy_evidence_catalog import EXPERTS_CSV, POWER_ZUCCO_CSV


def expert_estimates(columns: dict, power_row: str | None) -> dict:
    result = {}
    if columns:
        with EXPERTS_CSV.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter=";"))
        for year, column in columns.items():
            values = [
                float(r[f"ideol_{str(year)[2:]}_{column}"].replace(",", "."))
                for r in rows
                if r.get(f"ideol_{str(year)[2:]}_{column}", "").strip() not in {"", "NA"}
            ]
            if values:
                mean = sum(values) / len(values)
                result[f"bolognesi_{year}"] = {
                    "media_0_a_10": round(mean, 2),
                    "respondentes": len(values),
                    "fonte": "df_experts.csv (Bolognesi et al., doi 10.7910/DVN/MFIXKW)",
                    "tipo_de_afirmacao": "estimativa_de_especialistas",
                }
    if power_row:
        with POWER_ZUCCO_CSV.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row[""] == power_row:
                    waves = {w: row[f"party.estimates.{w}"] for w in (1990, 1993, 1997, 2001, 2005)}
                    result["power_zucco_2009_legisladores_1a10"] = {
                        str(w): (round(float(v), 2) if v not in {"NA", ""} else None)
                        for w, v in waves.items()
                    }
    return result
