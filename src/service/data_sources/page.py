"""Explain the provenance and interpretation of public political information."""

import json
from pathlib import Path

from service.political_dashboard.executive_orientation_presentation import (
    render_orientation_evidence_sources,
)
from service.political_dashboard.senate_orientation_1992_1994 import (
    SNAPSHOT_YEARS,
    senate_1992_1994_cell,
    senate_1992_1994_evidence,
    year_snapshot_summary,
)
from service.political_dashboard.senate_orientation_2026 import (
    senate_orientation_cell,
    senate_orientation_evidence,
    senate_summary_text,
)
from service.public_profile_web.layout import render_layout
from service.public_profile_web.security import text


def render_senate_sources():
    description = (
        "A composição vem de registros oficiais datados do Senado. As classificações "
        "dos partidos são estimativas de especialistas, distintas das autodeclarações. "
        "A aplicação de uma pesquisa de 2022 à composição de 2026 é uma síntese editorial, "
        "não uma pesquisa realizada em 2026. Direita inclui centro-direita. "
        "PSD e MDB têm enquadramentos divergentes conforme a fonte."
    )
    audit = senate_orientation_evidence()["published_audit"]
    summary = audit["orientation_summary"]
    return (
        '<section id="senado-2026"><h2>Senado: composição e abordagem política</h2>'
        f"<p>{description}</p><p>Referência da auditoria: {text(audit['reference_on'])}.</p>"
        f"<p>{text(senate_summary_text(summary))}</p>"
        + render_orientation_evidence_sources(senate_orientation_cell(summary))
        + "</section>"
    )


def render_itamar_senate_snapshot(year):
    summary = year_snapshot_summary(year)
    counts = summary["counts"]
    return (
        f"<li><strong>31/12/{year}: {text(senate_1992_1994_cell(year)['label'])}</strong> "
        f"Direita {counts['right']}/81; centro {counts['center']}; esquerda {counts['left']}; "
        f"sem filiação {counts['unaffiliated']}; partido sem estimativa "
        f"{counts['party_without_estimate']}; partido não identificado "
        f"{counts['party_not_identified']}.</li>"
    )


def render_itamar_senate_sources():
    evidence = senate_1992_1994_evidence()
    snapshots = "".join(render_itamar_senate_snapshot(year) for year in SNAPSHOT_YEARS)
    return (
        '<section id="senado-1992-1994"><h2>Senado no governo Itamar Franco (1992–1994)</h2>'
        "<p>Fotografias de 31 de dezembro reconstruídas a partir de mandatos, chapas, votos "
        "nominais e atos do Senado. A classificação dos partidos usa a onda de 1993 de Zucco "
        "e Power, uma referência diferente da usada em 2018 e 2022, conferida com a classificação "
        "categórica de Coppedge (1997) e com Mainwaring, Meneguello e Power (1999). Autodeclaração "
        "dos partidos (manifestos e programas) e estimativas de pesquisas são registradas à parte; "
        "só as estimativas numéricas definem os grupos. Maioria absoluta exige 41 "
        "das 81 cadeiras. Partidos sem estimativa e cadeiras sem partido identificado ficam "
        "separados e nunca viram centro.</p>"
        f"<ul>{snapshots}</ul><p>{text(evidence['limitation'])}</p>"
        + render_orientation_evidence_sources(senate_1992_1994_cell(SNAPSHOT_YEARS[0]))
        + "</section>"
    )


def render_people_sources():
    return """<section><h2>Pessoas, mandatos e filiações</h2>
<p>Senado e Câmara fornecem identificadores oficiais, mandatos, exercícios e registros
partidários. O TSE fornece dados eleitorais e registros dos partidos. Cada identidade é
relacionada ao person_id da base; mudanças de filiação preservam seus períodos e fontes.
Eleição, mandato e exercício efetivo são informações distintas. Ausência de filiação
informada não comprova desfiliação.</p></section>"""


def render_presidency_introduction():
    return """<section id="presidencia"><h2>Presidência e história dos governos</h2>
<p>Registros oficiais da Presidência, Arquivo Nacional e documentos históricos estabelecem
ocupantes e datas. Pesquisas acadêmicas fundamentam a orientação dos governos.
A classificação do governo é separada da filiação do presidente; transições dentro do ano
são preservadas. Sínteses editoriais não representam medições acadêmicas anuais.</p></section>"""


def render_coverage_sources():
    return """<section><h2>Estados, municípios e cobertura histórica</h2>
<p>Assembleias, diários oficiais e portais governamentais fornecem composições e atos de
posse, licença e substituição. Um cadastro ativo não comprova exercício individual.
Fotografias de datas distintas não são combinadas como uma composição simultânea.
Lacunas históricas permanecem identificadas até existir comprovação documental.</p></section>"""


def render_data_sources():
    content = (
        "<article><h1>Fontes dos dados</h1>"
        "<p>Conheça a origem das informações e os critérios usados para organizar o panorama.</p>"
        + render_people_sources()
        + render_presidency_introduction()
        + render_coverage_sources()
        + render_presidency_sources()
        + render_senate_sources()
        + render_itamar_senate_sources()
        + "</article>"
    )
    return render_layout("Fontes dos dados", content, active_section="sources")


def render_presidency_sources():
    evidence_path = (
        Path(__file__).parents[1] / "political_dashboard" / "executive_orientation_evidence.json"
    )
    records = json.loads(evidence_path.read_text())["records"]
    rows = []
    for record in records:
        label = record.get("executive_name") or record.get("regime_name") or "Governo ou regime"
        cell = {"source_evidence": [record]}
        rows.append(
            f"<section><h3>{text(label)}</h3>"
            f"<p>{text(record.get('classification_basis', ''))}</p>"
            + render_orientation_evidence_sources(cell)
            + "</section>"
        )
    return "<section><h2>Pesquisas sobre os governos</h2>" + "".join(rows) + "</section>"
