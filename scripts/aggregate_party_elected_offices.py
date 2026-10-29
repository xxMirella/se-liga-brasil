"""Agrega eleitos por partido (TSE consulta_cand) e registra url/sha256 dos zips brutos.

Entrada: data/political-orientation/party-model/policies/raw/tse/consulta_cand_AAAA.zip
Saída: derived/tse_elected_offices.json (presidente, governadores, prefeitos de capitais,
total de prefeitos, vagas de senador e de deputado federal por partido e ano).
O partido é o registrado pelo TSE na candidatura; coligação é preservada como texto da fonte.
"""
# ruff: noqa: E501, SIM117  # hardcode-ok: textos longos de fonte e prosa metodológica

from __future__ import annotations

import collections
import csv
import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

POLICIES = Path(__file__).resolve().parents[1] / "data/political-orientation/party-model/policies"
RAW_TSE = POLICIES / "raw/tse"
TSE_URL = "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_{year}.zip"  # hardcode-ok: endpoint público oficial do TSE
ELECTED_STATUS = {
    "ELEITO",
    "ELEITO POR QP",
    "ELEITO POR MÉDIA",
    "ELEITO POR MEDIA",
    "MÉDIA",
    "MEDIA",
    "QP",
}
SINGLE_SEAT_OFFICES = {"PRESIDENTE", "GOVERNADOR", "PREFEITO"}
TRACKED_OFFICES = {"PRESIDENTE", "GOVERNADOR", "SENADOR", "DEPUTADO FEDERAL", "PREFEITO"}
STATE_CAPITALS = {  # (município, UF): evita confundir homônimos como Boa Vista/PB ou Belém/PB
    ("RIO BRANCO", "AC"),
    ("MACEIÓ", "AL"),
    ("MACAPÁ", "AP"),
    ("MANAUS", "AM"),
    ("SALVADOR", "BA"),
    ("FORTALEZA", "CE"),
    ("BRASÍLIA", "DF"),
    ("VITÓRIA", "ES"),
    ("GOIÂNIA", "GO"),
    ("SÃO LUÍS", "MA"),
    ("CUIABÁ", "MT"),
    ("CAMPO GRANDE", "MS"),
    ("BELO HORIZONTE", "MG"),
    ("BELÉM", "PA"),
    ("JOÃO PESSOA", "PB"),
    ("CURITIBA", "PR"),
    ("RECIFE", "PE"),
    ("TERESINA", "PI"),
    ("RIO DE JANEIRO", "RJ"),
    ("NATAL", "RN"),
    ("PORTO ALEGRE", "RS"),
    ("PORTO VELHO", "RO"),
    ("BOA VISTA", "RR"),
    ("FLORIANÓPOLIS", "SC"),
    ("SÃO PAULO", "SP"),
    ("ARACAJU", "SE"),
    ("PALMAS", "TO"),
}


def iter_elected(year: int):
    """Gera um dict por eleito, deduplicado (ver chave abaixo)."""
    seen = set()
    with zipfile.ZipFile(RAW_TSE / f"consulta_cand_{year}.zip") as archive:
        for name in archive.namelist():
            if not name.endswith(".csv"):
                continue
            with archive.open(name) as raw:
                reader = csv.DictReader(
                    io.TextIOWrapper(raw, encoding="latin-1", newline=""), delimiter=";"
                )
                for row in reader:
                    # Cargo majoritário tem um vencedor por unidade eleitoral; os demais, um por candidatura.
                    key = (
                        (row["DS_CARGO"], row["SG_UE"])
                        if row["DS_CARGO"] in SINGLE_SEAT_OFFICES
                        else (row.get("SQ_CANDIDATO"), row["DS_CARGO"])
                    )
                    if (
                        row["DS_CARGO"] in TRACKED_OFFICES
                        and row["DS_SIT_TOT_TURNO"] in ELECTED_STATUS
                        and key not in seen
                    ):
                        seen.add(key)
                        yield row


def summarize_year(year: int) -> dict:
    seats = collections.defaultdict(collections.Counter)
    executives = []
    capital_mayors = []
    for row in iter_elected(year):
        office, party = row["DS_CARGO"], row["SG_PARTIDO"]
        seats[office][party] += 1
        if office in {"PRESIDENTE", "GOVERNADOR"}:
            executives.append(
                {
                    "cargo": office,
                    "uf": row["SG_UF"],
                    "nome": row["NM_CANDIDATO"],
                    "partido": party,
                    "coligacao": row.get("DS_COMPOSICAO_COLIGACAO", ""),
                }
            )
        if office == "PREFEITO" and (row["NM_UE"].upper(), row["SG_UF"]) in STATE_CAPITALS:
            capital_mayors.append(
                {
                    "municipio": row["NM_UE"],
                    "uf": row["SG_UF"],
                    "nome": row["NM_CANDIDATO"],
                    "partido": party,
                }
            )
    return {
        "vagas_por_cargo_e_partido": {k: dict(v.most_common()) for k, v in seats.items()},
        "executivos_estaduais_e_federal": executives,
        "prefeitos_de_capitais": capital_mayors,
    }


def build_manifest() -> dict:
    entries = {}
    for path in sorted(RAW_TSE.glob("consulta_cand_*.zip")):
        year = path.stem.rsplit("_", 1)[-1]
        sha = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                sha.update(block)
        entries[path.name] = {
            "url": TSE_URL.format(year=year),
            "sha256": sha.hexdigest(),
            "bytes": path.stat().st_size,
            "registrado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        }
    return entries


def main() -> None:
    summary = {}
    for path in sorted(RAW_TSE.glob("consulta_cand_*.zip")):
        year = int(path.stem.rsplit("_", 1)[-1])
        summary[str(year)] = summarize_year(year)
        print(year, flush=True)
    (POLICIES / "derived").mkdir(parents=True, exist_ok=True)
    (POLICIES / "derived/tse_elected_offices.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1)
    )
    (RAW_TSE / "manifest.json").write_text(
        json.dumps(build_manifest(), ensure_ascii=False, indent=1)
    )


if __name__ == "__main__":
    main()
