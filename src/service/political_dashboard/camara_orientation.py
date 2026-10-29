"""Explicit Chamber-only editorial policy; original dated survey observations stay intact."""

from collections import Counter

from service.political_dashboard.chamber_party_identity import (
    HISTORICAL_IDENTITY_POLICY,
    IDENTITY_ALIGNMENTS,
    chamber_survey_identity,
)
from service.political_dashboard.political_orientation_catalog import (
    CATEGORY_LABELS,
    ORIENTATION_METHODOLOGY_URL,
    classify_political_orientation,
)
from service.public_profile_web.security import text

POLICY_VERSION = "camara_2020_2026.v1"
IDEOLOGICAL_CATEGORIES = ("left", "center", "right")
UNAFFILIATED = {"s.part.", "s/partido", "sem partido", "sem filiação partidária"}


def chamber_policy_applies(composition, year):
    historical = (2010 <= year <= 2019
                  and composition.get("orientation_policy_version") in {
                      "camara_2010_2019.v1", HISTORICAL_IDENTITY_POLICY,
                  })
    current = (2020 <= year <= 2026
               and composition.get("orientation_policy_version") == POLICY_VERSION)
    return (composition.get("institution_code") == "camara" and (historical or current)
            and composition.get("territory_code") == "BR"
            and composition.get("expected_seats") == 513)


def chamber_orientation(group, year, *, reference_year=None, identity_alignment=False):
    label = str(group.get("abbreviation") or "").strip()
    reference = reference_year or (year if year < 2018 else 2018 if year < 2022 else 2022)
    if group.get("political_party_code") in {"unreported", "unknown", "unreconciled"}:
        return {"category": "undetermined", "status": "unverified_affiliation"}
    if label.casefold() in UNAFFILIATED:
        return {"category": "unaffiliated", "status": "not_a_party"}
    # PODE and PODEMOS name the same party, not a merger or successor organisation.
    canonical = "PODEMOS" if label.casefold() == "pode" and reference == 2022 else label
    canonical, alignment = chamber_survey_identity(
        canonical, year, reference, identity_alignment,
    )
    result = classify_political_orientation(canonical, reference)
    return dict(result, classification_year=year, reference_year=None if year < 2018 else reference,
                reference_political_party=canonical,
                identity_alignment=alignment,
                policy_version=HISTORICAL_IDENTITY_POLICY if identity_alignment else
                "camara_2010_2019.v1" if year < 2020 else POLICY_VERSION,
                evidence_kind="no_dated_observation" if year < 2018 else
                "dated_survey" if year == reference
                else "editorial_application_of_dated_expert_estimate")


def chamber_counts(composition, year, reference_year=None):
    counts = Counter()
    for group in composition.get("political_parties", []):
        result = chamber_orientation(
            group, year, reference_year=reference_year,
            identity_alignment=composition.get("orientation_policy_version")
            == HISTORICAL_IDENTITY_POLICY,
        )
        counts[result["category"]] += group["count"]
    missing = composition.get("total", 0) - sum(counts.values())
    if missing < 0:
        raise ValueError("CHAMBER_PARTY_COUNTS_EXCEED_OBSERVED_PEOPLE")
    counts["undetermined"] += missing
    return counts


def chamber_orientation_summary(composition, year):
    if not chamber_policy_applies(composition, year):
        return None
    counts = chamber_counts(composition, year)
    total = composition.get("total", 0)
    vacant = len(composition.get("documented_vacancies") or [])
    if not 0 <= total <= 513 - vacant:
        raise ValueError("CHAMBER_OBSERVED_PEOPLE_EXCEED_CAPACITY")
    classified = sum(counts[key] for key in IDEOLOGICAL_CATEGORIES)
    maximum = max((counts[key] for key in IDEOLOGICAL_CATEGORIES), default=0)
    leaders = [key for key in IDEOLOGICAL_CATEGORIES if counts[key] == maximum and maximum]
    majority = next((key for key in IDEOLOGICAL_CATEGORIES if counts[key] >= 257), None)
    unresolved = 513 - vacant - classified - counts["unaffiliated"]
    absence_proven = all(counts[key] + unresolved < 257 for key in IDEOLOGICAL_CATEGORIES)
    return {"policy_version": composition["orientation_policy_version"],
            "reference_year": None if year < 2018 else 2018 if year < 2022 else 2022,
            "counts": dict(counts), "total_seats": 513, "observed_people": total,
            "unobserved_seats": 513 - total - vacant, "documented_vacant_seats": vacant,
            "classified_people": classified,
            "coverage": composition.get("coverage"), "majority_threshold": 257,
            "largest_groups": leaders, "largest_count": maximum,
            "absolute_majority": majority, "absence_proven": absence_proven,
            "snapshot_on": composition.get("snapshot_on"),
            "sensitivity": {str(reference): dict(chamber_counts(composition, year, reference))
                            for reference in (2018, 2022)} if year >= 2018 else {}}


def chamber_summary_text(summary):
    counts = summary["counts"]
    majority = summary["absolute_majority"]
    conclusion = ("Maioria absoluta: " + CATEGORY_LABELS[majority] if majority else
                  "Sem maioria absoluta" if summary["absence_proven"] else
                  "Maioria absoluta não comprovada; há lacunas")
    leaders = " / ".join(CATEGORY_LABELS[key] for key in summary["largest_groups"])
    distribution = "; ".join(f"{CATEGORY_LABELS[key]}: {counts.get(key, 0)}"
                             for key in CATEGORY_LABELS)
    method = (f"Survey de {summary['reference_year']} aplicado à fotografia anual; "
              "síntese editorial fora do ano da pesquisa, sem interpolação de escores. "
              if summary["reference_year"] else
              "Sem classificação datada integrada para este ano; ondas futuras não retroagem. ")
    return (f"{conclusion}. Referência: {summary['snapshot_on']}. "
            f"{summary['observed_people']}/513 integrantes documentados; "
            f"{summary['classified_people']}/513 com classificação; "
            f"{summary['documented_vacant_seats']} vagas documentadas; "
            f"{summary['unobserved_seats']} cadeiras sem exercício comprovado. "
            f"Maior grupo classificado: {leaders or 'nenhum'} ({summary['largest_count']}). "
            f"Limiar: 257/513. {distribution}. "
            f"Política: {summary['policy_version']}. {method}"
            "Não mede apoio ao governo, presença ou orientação individual.")


def chamber_orientation_cell(summary):
    from service.political_dashboard.orientation_timeline import category_cell

    majority = summary["absolute_majority"]
    categories = [majority] if majority else summary["largest_groups"] or ["undetermined"]
    cell = category_cell(categories, "partial")
    suffix = " · maioria absoluta" if majority else " · maior grupo, sem maioria comprovada"
    cell["label"] += suffix if summary["largest_groups"] else " · maioria não comprovada"
    cell["detail"] = chamber_summary_text(summary)
    source = ORIENTATION_METHODOLOGY_URL if summary["reference_year"] else (
        "https://dadosabertos.camara.leg.br/swagger/api.html"
    )
    title = ("Survey 2018/2022; aplicação editorial à Câmara" if summary["reference_year"]
             else "Históricos oficiais; sem classificação datada integrada")
    cell["source_evidence"] = [{"source_url": source,
                                "source_title": title}]
    return cell


def render_chamber_orientation_summary(composition, year):
    summary = chamber_orientation_summary(composition, year)
    if not summary:
        return ""
    political_parties = "".join(
        f'<li>{text(group["abbreviation"])}: {group["count"]} · '
        f'{CATEGORY_LABELS[chamber_orientation(
            group, year, identity_alignment=composition.get("orientation_policy_version")
            == HISTORICAL_IDENTITY_POLICY,
        )["category"]]}</li>'
        for group in composition.get("political_parties", [])
    )
    sensitivity = "; ".join(
        f"onda {reference}: " + ", ".join(
            f"{CATEGORY_LABELS[key]} {counts.get(key, 0)}" for key in CATEGORY_LABELS
        ) for reference, counts in summary["sensitivity"].items()
    )
    return ('<p class="panorama-leading-group">' + text(chamber_summary_text(summary)) + '</p>'
            '<details class="panorama-source-notes"><summary>Partidos e sensibilidade '
            'da classificação · Câmara 2010–2026</summary><ul>' + political_parties
            + '</ul><p>' + text(sensitivity) + '</p><p>Comparação aplica cada onda às '
            'mesmas filiações históricas. Organizações ausentes da onda ficam sem '
            'classificação; PRD não herda a nota de PTB ou Patriota. PODE corresponde '
            'ao Podemos. Na política camara_2010_2019.v2, PATRI/Patriota em 2018 e '
            'PL/PR, Republicanos/PRB e Cidadania/PPS em 2019 têm equivalência nominal '
            'documentada pelo TSE. A regra não alcança fusões nem altera as políticas '
            'dos demais anos. Diferenças entre ondas não demonstram mudança individual.</p>'
            '<p><a href="' + ORIENTATION_METHODOLOGY_URL + '">Dados acadêmicos originais</a>'
            ' · <a href="https://dadosabertos.camara.leg.br/swagger/api.html">'
            'Históricos e composição oficiais</a></p></details>'
            + render_chamber_changes(composition) + render_chamber_reconciliation(composition)
            + render_chamber_identity_sources(composition))


def render_chamber_changes(composition):
    changes = composition.get("within_year_changes", [])
    if not changes:
        return ""
    items = "".join(
        f"<li>{text(row['date'])}: entradas {row.get('entry', 0)}; "
        f"saídas {row.get('exit', 0)}; alterações de partido {row.get('affiliation', 0)}</li>"
        for row in changes
    )
    return ('<details class="panorama-source-notes"><summary>Mudanças documentadas dentro '
            'do ano</summary><p>Eventos dos históricos individuais arquivados; entradas '
            'e saídas não são pessoas distintas nem composição simultânea. Registros '
            'administrativos e marcadores sem situação foram excluídos. Em 2026, '
            'este histórico foi coletado até 26/10; a fotografia da listagem é de '
            '29/10. Consulte o histórico oficial de cada integrante.</p><ul>'
            + items + '</ul></details>')


def render_chamber_reconciliation(composition):
    rows = composition.get("uf_reconciliation", [])
    if not rows:
        return ""
    territories = "".join(
        f"<li>{text(row['uf'])}: {row['observed_people']}/{row['expected_seats']} em exercício; "
        f"{row['documented_vacancies']} vagas documentadas; {row['unresolved']} pendências</li>"
        for row in rows
    )
    pending = "".join(
        f"<li>{text(row['name'])} · {text(row['uf'])} · ID Câmara "
        f"{text(row['source_person_id'])}: "
        f'<a href="{text(row["official_url"])}">histórico oficial</a></li>'
        for row in composition.get("reconciliation_pending", [])
    )
    return ('<details class="panorama-source-notes"><summary>Reconciliação por UF e casos '
            'nominais pendentes</summary><ul>' + territories + '</ul><p>Os casos a seguir '
            'são registros nas UFs com diferenças ainda não conciliadas. Não representam '
            'um pareamento de titulares e suplentes nem uma lista de vagas. Licença e '
            'afastamento judicial não são convertidos em vacância.</p><ul>' + pending
            + '</ul></details>')



def render_chamber_identity_sources(composition):
    if composition.get("orientation_policy_version") != HISTORICAL_IDENTITY_POLICY:
        return ""
    links = "".join(
        f'<li><a href="{text(row["source_url"])}">TSE: {text(abbreviation)} / '
        f'{text(row["reference_abbreviation"])}</a> · {text(row["effective_on"])}</li>'
        for (year, abbreviation), row in IDENTITY_ALIGNMENTS.items()
        if year == composition.get("year")
    )
    if not links:
        return ""
    return ('<details class="panorama-source-notes"><summary>Fontes das equivalências '
            'nominais</summary><p>Correspondência explícita da sigla na fotografia de '
            '31/12 com o nome da mesma organização no survey. A sigla histórica permanece '
            'preservada; não constitui nova medição ideológica.</p><ul>' + links
            + '</ul></details>')
