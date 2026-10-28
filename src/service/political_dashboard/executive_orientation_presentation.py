"""Present government and regime evidence without rewriting personal party affiliation."""

from service.political_dashboard.executive_orientation_evidence import (
    classify_executive_orientation,
    classify_regime_orientation,
)
from service.public_profile_web.security import text


def documented_executive_cell(institution, year):
    if institution.get("institution_code") != "presidency":
        return None
    regime = classify_regime_orientation("senado-vcb:16005", year)
    if regime["category"] != "undetermined":
        return regime_cell(regime)
    records = list(institution.get("segments") or [])
    if institution.get("current"):
        records.append(institution["current"])
    observations = executive_record_observations(records, year)
    documented = [row for row in observations if row["category"] != "undetermined"]
    return government_cell(observations, documented) if documented else None


def executive_record_identity(record):
    if record.get("exercise_id"):
        return record["exercise_id"]
    person_id, starts_on = record.get("person_id"), record.get("starts_on")
    return f"{person_id}:{starts_on}" if person_id and starts_on else None


def executive_record_observations(records, year):
    observations = {}
    year_start, year_end = f"{year}-01-01", f"{year + 1}-01-01"
    for record in records:
        starts_on = record.get("starts_on") or year_start
        ends_before = record.get("ends_before") or year_end
        if starts_on >= year_end or ends_before <= year_start:
            continue
        identity = executive_record_identity(record)
        evidence = classify_executive_orientation(identity, year)
        if evidence["category"] != "undetermined":
            evidence["coverage_start"] = max(
                year_start, starts_on, evidence.get("coverage_start", year_start),
            )
            evidence["coverage_end_exclusive"] = min(
                year_end, ends_before, evidence.get("coverage_end_exclusive", year_end),
            )
            if evidence["coverage_start"] >= evidence["coverage_end_exclusive"]:
                continue
        observations.setdefault((identity, starts_on, ends_before), evidence)
    return list(observations.values())


def regime_cell(evidence):
    from service.political_dashboard.orientation_timeline import category_cell

    cell = category_cell([evidence["category"]], "partial")
    partial = evidence["year_coverage"] == "partial"
    cell["label"] += " · ditadura" + (" · parte do ano" if partial else "")
    cell["qualifier"] = "classificação do regime, distinta da filiação pessoal"
    cell["detail"] = (
        f"Ditadura militar: {evidence['coverage_start']} até "
        f"{evidence['coverage_end_exclusive']} (fim exclusivo). "
        "Direita é uma síntese historiográfica das bases do regime. "
        + ("O restante deste ano não recebe essa classificação. " if partial else "")
        + "Não classifica automaticamente o Congresso ou todos os indivíduos."
    )
    cell["source_evidence"] = [evidence]
    return cell


def government_cell(observations, documented):
    from service.political_dashboard.orientation_timeline import category_cell

    categories = sorted({row["category"] for row in observations})
    cell = category_cell(categories, "mixed" if len(categories) > 1 else "partial")
    cell["qualifier"] = "classificação do governo, distinta da filiação partidária"
    cell["detail"] = " ".join(government_description(row) for row in documented)
    if any(row["category"] == "undetermined" for row in observations):
        cell["detail"] += " Há exercício neste ano sem classificação de governo documentada."
    cell["source_evidence"] = documented
    return cell


def government_description(evidence):
    if evidence["evidence_kind"] == "editorial_government_classification":
        basis = "Síntese editorial do mandato; não é medição acadêmica anual."
    elif evidence["status"] == "literature_based_editorial_summary":
        basis = "Síntese editorial fundamentada na literatura indicada."
    else:
        basis = "Classificação acadêmica do discurso governamental no período estudado."
    period = (
        f"{evidence['coverage_start']} até {evidence['coverage_end_exclusive']} "
        "(fim exclusivo)."
    )
    return " ".join(filter(None, [
        evidence["executive_name"] + ": " + period + " " + basis,
        evidence.get("coalition_note"), evidence.get("ui_qualifier"),
        "A classificação não altera a filiação partidária nem rotula o Congresso.",
    ]))


def render_orientation_evidence_sources(cell):
    sources = {}
    for evidence in cell.get("source_evidence", []):
        for source in [evidence, *evidence.get("supporting_sources", [])]:
            if source.get("source_title"):
                sources.setdefault(source["source_url"], source)
    return "".join(
        f'<p><a href="{text(url)}" target="_blank" rel="noopener noreferrer">'
        f'{text(row["source_title"])} ↗</a>'
        + (f' · publicação: {text(row["source_publication_year"])}'
           if row.get("source_publication_year") else " · publicação sem data informada")
        + '</p>'
        for url, row in sources.items()
    )


def render_executive_orientation(executive, view, year):
    if view != "political_orientation" or year is None:
        return ""
    from service.political_dashboard.orientation_timeline import executive_orientation_cell

    cell = executive_orientation_cell(executive, year)
    return (f'<p><strong>Abordagem do governo: {text(cell["label"])}</strong></p>'
            '<details><summary>Critério e fontes da classificação</summary>'
            f'<p>{text(cell["detail"])}</p>{render_orientation_evidence_sources(cell)}</details>')
