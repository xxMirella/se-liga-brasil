"""Match the archived TSE 1994 candidacy file to the Senate occupants.

Identity rule: normalized civil name AND birth date must both be equal. Name
alone never matches. Output is evidence for review, not a party resolution:
the TSE party is the party of the 1994 candidacy, not the party on 31/12.
"""

import csv
import hashlib
import io
import json
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path

ARCHIVE_PATH = Path(
    "data/political-dashboard/senate-history-1992-1994-source/tse/consulta_cand_1994.zip"
)
NORMALIZED_PATH = Path("data/political-dashboard/senate-history-1992-1994-normalized.json")
OUTPUT_PATH = Path("data/political-dashboard/senate-history-1992-1994-tse-1994-matches.json")
MEMBER_NAME = "consulta_cand_1994_BRASIL.csv"


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    return " ".join("".join(c for c in decomposed if not unicodedata.combining(c)).upper().split())


def iso_date(brazilian: str) -> str | None:
    try:
        return datetime.strptime(brazilian, "%d/%m/%Y").date().isoformat()
    except ValueError:
        return None


def candidacy_index() -> dict[tuple[str, str], list[dict]]:
    with zipfile.ZipFile(ARCHIVE_PATH) as archive:
        text = archive.read(MEMBER_NAME).decode("latin-1")
    index: dict[tuple[str, str], list[dict]] = {}
    for row in csv.DictReader(io.StringIO(text), delimiter=";"):
        birth = iso_date(row["DT_NASCIMENTO"])
        if birth:
            index.setdefault((fold(row["NM_CANDIDATO"]), birth), []).append(row)
    return index


def candidacy_summary(row: dict) -> dict:
    return {
        key: row[key]
        for key in (
            "SG_UF",
            "DS_CARGO",
            "SG_PARTIDO",
            "NM_PARTIDO",
            "DS_SIT_TOT_TURNO",
            "DT_ELEICAO",
            "SQ_CANDIDATO",
        )
    }


def main() -> None:
    index = candidacy_index()
    senators = json.loads(NORMALIZED_PATH.read_text(encoding="utf-8"))["senators"]
    matches = []
    for senator in senators:
        rows = index.get((fold(senator["civil_name"]), senator["birth_date"]), [])
        if rows:
            matches.append(
                {
                    "senate_id": senator["senate_id"],
                    "name": senator["inventory_name"],
                    "civil_name": senator["civil_name"],
                    "birth_date": senator["birth_date"],
                    "candidacies_1994": [candidacy_summary(r) for r in rows],
                }
            )
    OUTPUT_PATH.write_text(
        json.dumps(
            {
                "source": {
                    "file": str(ARCHIVE_PATH),
                    "sha256": hashlib.sha256(ARCHIVE_PATH.read_bytes()).hexdigest(),
                    "url": "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_1994.zip",  # hardcode-ok: URL oficial do arquivo do TSE registrada como proveniência  # noqa: E501
                },
                "rule": "civil name and birth date both equal; evidence of the 1994 candidacy only",
                "matched_count": len(matches),
                "matches": matches,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"{len(matches)} of {len(senators)} matched")


if __name__ == "__main__":
    main()
