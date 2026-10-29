"""Apoio de cada partido a candidaturas presidenciais (1.º turno), a partir do TSE consulta_cand.

O partido é considerado apoiador quando consta de DS_COMPOSICAO_COLIGACAO/FEDERACAO da candidatura
ou é o partido do candidato. 1994 não traz coligação na fonte (#NE): só o partido do candidato.
Saída: derived/presidential_coalition_support.json. Coligação formal não prova afinidade programática.
"""
# ruff: noqa: E501, SIM117  # hardcode-ok: textos longos de fonte e prosa metodológica

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from pathlib import Path

POLICIES = Path(__file__).resolve().parents[1] / "data/political-orientation/party-model/policies"
YEARS = (1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022)
NO_VALUE = {"#NE", "#NULO", "#NULO#", "None", ""}


def coalition_parties(row: dict) -> list[str]:
    text = " / ".join(row.get(field) or "" for field in ("DS_COMPOSICAO_COLIGACAO",))
    inside_parentheses = re.findall(r"\(([^)]*)\)", text)
    flat = re.sub(r"Federação[^(]*\([^)]*\)", lambda m: m.group(0).split("(")[1].rstrip(")"), text)
    flat = " / ".join([flat] + inside_parentheses)
    names = {
        name.strip() for name in flat.split("/") if name.strip() and name.strip() not in NO_VALUE
    }
    names.add(row["SG_PARTIDO"])
    return sorted(names)


def first_round_candidates(year: int) -> list[dict]:
    with zipfile.ZipFile(POLICIES / f"raw/tse/consulta_cand_{year}.zip") as archive:
        with archive.open(f"consulta_cand_{year}_BR.csv") as raw:
            rows = csv.DictReader(
                io.TextIOWrapper(raw, encoding="latin-1", newline=""), delimiter=";"
            )
            return [
                {
                    "candidato": r["NM_CANDIDATO"],
                    "partido_do_candidato": r["SG_PARTIDO"],
                    "resultado": r["DS_SIT_TOT_TURNO"],
                    "partidos_da_coligacao": coalition_parties(r),
                }
                for r in rows
                if r["DS_CARGO"] == "PRESIDENTE" and r["NR_TURNO"] == "1"
            ]


def main() -> None:
    output = {str(y): first_round_candidates(y) for y in YEARS}
    (POLICIES / "derived/presidential_coalition_support.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=1)
    )


if __name__ == "__main__":
    main()
