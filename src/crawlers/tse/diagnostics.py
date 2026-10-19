"""Public electoral references for diagnostics; never include documents or fingerprints."""

FIELD_COLUMNS = {
    "candidate_name": "NM_CANDIDATO",
    "ballot_name": "NM_URNA_CANDIDATO",
    "election_year": "ANO_ELEICAO",
    "candidate_sequence": "SQ_CANDIDATO",
    "election_id": "CD_ELEICAO",
    "represented_uf": "SG_UF",
    "political_party": "SG_PARTIDO",
    "office_code": "CD_CARGO",
    "anchor_year": "ANO_ELEICAO_ATUAL",
    "anchor_candidate_sequence": "SQ_CANDIDATO_ATUAL",
}


def build_record_context(row: dict, kind: str, entry: str, line: int, index) -> dict:
    context = {name: row[column] for name, column in FIELD_COLUMNS.items() if row.get(column)}
    context["record_kind"] = kind
    candidate = index.candidate_context(row.get("ANO_ELEICAO"), row.get("SQ_CANDIDATO"))
    if kind == "candidate":
        context["candidate_source"] = {"entry_name": entry, "row_number": line}
    elif candidate:
        context.setdefault("candidate_name", candidate.get("candidate_name"))
        context["candidate_source"] = candidate.get("candidate_source")
    return context
