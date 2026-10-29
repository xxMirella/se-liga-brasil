"""Public page comparing survey-based and behavior-based party classifications."""

from pathlib import Path
from urllib.parse import quote

from service.party_orientation_comparison.detail import PROPOSAL_NOTE, render_comparison_table
from service.party_orientation_comparison.rows import (
    OUTCOME_LABELS,
    build_rows,
    outcome_counts,
    party_entry,
)
from service.party_orientation_comparison.snapshot import load_snapshot
from service.political_dashboard.political_orientation_catalog import (
    ORIENTATION_METHODOLOGY_LABEL,
    ORIENTATION_METHODOLOGY_URL,
)
from service.public_profile.contracts import PublicProfileError
from service.public_profile_web.layout import render_layout
from service.public_profile_web.security import text
from service.public_profile_web.static_text import read_static_text

ROUTE = "/comparacao-de-classificacoes"
STYLESHEET_ROUTE = "/assets/party-comparison.css"
EXPLANATION = (
    '<div class="comparison-grid">'
    "<section><h2>Pesquisa de especialistas</h2>"
    "<p>Mede a <strong>percepção de especialistas</strong> sobre a posição do partido em uma "
    "escala de 0 (esquerda) a 10 (direita). Não é a opinião da população nem a autodeclaração "
    "do partido. Só há estimativas para 2018 e 2022 "
    f'(<a href="{ORIENTATION_METHODOLOGY_URL}" rel="noopener noreferrer">'
    f"{text(ORIENTATION_METHODOLOGY_LABEL)}</a>). O site agrupa a média em esquerda "
    "(abaixo de 4,5), centro (4,5 a 5,5) e direita (acima de 5,5).</p></section>"
    "<section><h2>Modelo de atuação</h2>"
    "<p>Mede <strong>o que o partido faz</strong>: votos nominais, políticas e iniciativas, "
    "com peso menor para declarações. Usa uma escala de −1 (esquerda) a +1 (direita), em duas "
    "dimensões: econômica e sociocultural. Quando faltam evidências, o modelo diz "
    "&quot;evidência insuficiente&quot; e não preenche a lacuna.</p></section></div>"
)
LIMITS = (
    "<h2>Limites desta comparação</h2><ul>"
    "<li>A pesquisa cobre só 2018 e 2022; nos demais períodos a comparação não é possível.</li>"
    "<li>Os votos de 2003 a 2014 misturam posição ideológica com ser governo ou oposição; "
    "não valem sozinhos como esquerda ou direita.</li>"
    "<li>Há poucas votações temáticas por legislatura; com menos de três, "
    "a nota é só indicativa.</li>"
    "<li>Para comparar, o modelo é agrupado em esquerda, centro e direita; centro-esquerda "
    "conta como esquerda e centro-direita como direita.</li>"
    "<li>Rótulos &quot;extrema&quot; e &quot;radical&quot; do modelo são "
    f"{PROPOSAL_NOTE}.</li>"
    "<li>Uma coluna de autodeclaração do partido ainda não aparece: os textos dos partidos foram "
    "arquivados, mas a leitura ainda não foi revisada. Veja "
    '<a href="/fontes-dos-dados">as fontes dos dados</a>.</li></ul>'
)


def comparison_stylesheet():
    return read_static_text(Path(__file__).parent / "assets" / "party-comparison.css")


def render_filter(snapshot, selected):
    options = "".join(
        f'<option value="{text(entry["political_party"])}"'
        f"{' selected' if selected and entry['political_party'] == selected else ''}>"
        f"{text(entry['political_party'])}</option>"
        for entry in snapshot["political_parties"]
    )
    return (
        f'<form class="comparison-filter" action="{ROUTE}" method="get">'
        '<div><label for="comparison-party">Partido</label><br>'
        f'<select id="comparison-party" name="partido">{options}</select></div>'
        '<button type="submit">Ver partido</button>'
        f'<a href="{ROUTE}">Ver todos</a></form>'
    )


def render_overview_row(snapshot, entry):
    rows = build_rows(snapshot, entry["political_party"])
    counts = outcome_counts(rows)
    name = entry["political_party"]
    cells = "".join(f'<td class="number">{counts[key]}</td>' for key in OUTCOME_LABELS)
    return (
        f'<tr><th scope="row"><a href="{ROUTE}?partido={quote(name)}">{text(name)}</a></th>'
        f'<td class="number">{len(rows)}</td>{cells}</tr>'
    )


def render_overview(snapshot):
    headers = "".join(f'<th scope="col">{label}</th>' for label in OUTCOME_LABELS.values())
    body = "".join(render_overview_row(snapshot, e) for e in snapshot["political_parties"])
    return (
        '<div class="comparison-scroll"><table class="comparison-table">'
        "<caption>Períodos com algum registro, por partido e resultado</caption>"
        '<thead><tr><th scope="col">Partido</th><th scope="col">Períodos</th>'
        f"{headers}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def selected_party(snapshot, requested):
    if not requested:
        return None
    entry = party_entry(snapshot, requested)
    if entry is None:
        raise PublicProfileError("UNKNOWN_POLITICAL_PARTY", 400)
    return entry["political_party"]


def render_party_comparison(snapshot, political_party):
    entry = party_entry(snapshot, political_party)
    rows = build_rows(snapshot, political_party)
    if not rows:
        return f"<p>{text(political_party)} não tem registro de nenhum dos métodos.</p>"
    return render_comparison_table(political_party, rows, entry["empty_periods"])


def render_party_comparison_page(requested_party=None):
    snapshot = load_snapshot()
    political_party = selected_party(snapshot, requested_party)
    body = (
        render_party_comparison(snapshot, political_party)
        if political_party
        else render_overview(snapshot)
    )
    content = (
        "<h1>Comparação entre classificações de partidos</h1>"
        "<p>Duas formas de classificar cada partido, lado a lado: o que especialistas "
        "percebem e o que o partido faz. Nenhuma das duas é tratada como a resposta certa.</p>"
        + EXPLANATION
        + render_filter(snapshot, political_party)
        + body
        + LIMITS
    )
    return render_layout(
        "Comparação de classificações",
        content,
        extra_stylesheet=STYLESHEET_ROUTE,
        active_section="comparison",
    )
