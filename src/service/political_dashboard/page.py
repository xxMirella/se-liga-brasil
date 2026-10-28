"""Accessible server-rendered panorama using the portal's established palette."""

from datetime import date, timedelta
from pathlib import Path
from uuid import UUID

from service.political_dashboard.composition_charts import render_party_bars
from service.political_dashboard.composition_presentation import composition_presentation
from service.political_dashboard.contracts import STATE_NAMES
from service.political_dashboard.executive_context import render_government_context_observations
from service.political_dashboard.orientation_composition import (
    orientation_composition,
    render_orientation_composition_note,
)
from service.political_dashboard.orientation_glossary import render_orientation_glossary
from service.political_dashboard.orientation_timeline import render_orientation_annual_summary
from service.political_dashboard.presidential_explanations import render_presidential_explanations
from service.political_dashboard.semicircle import render_people_semicircle
from service.political_dashboard.senate_election_observations import (
    render_senate_election_observations,
)
from service.political_dashboard.timeline import render_timeline_bands
from service.political_dashboard.view_filter import (
    render_orientation_legend,
    render_timeline_view_filter,
)
from service.public_profile_web.layout import render_layout
from service.public_profile_web.security import official_url, person_path, text

POLITICAL_PARTY_QUALIFIERS = {
    "verified_party_official_dated_government_statement": (
        "Partido declarado pela organização partidária nesta data", "Declaração datada do partido; "
        "não é certidão governamental de filiação.", "Fonte da declaração partidária",
    ),
    "verified_official_government_party_classification": (
        "Partido atribuído ao governo pela fonte oficial", "Classificação do governo; "
        "não comprova filiação contínua.", "Fonte da classificação oficial do governo",
    ),
    "verified_government_classification": (
        "Classificação histórica do governo", "Identificação em pesquisa histórica; "
        "não é certidão de filiação.", "Fonte da classificação do governo",
    ),
    "verified_official_presidential_term_party": (
        "Partido informado para o mandato", "Atribuição da fonte ao mandato; "
        "não comprova filiação contínua.", "Fonte do partido informado para o mandato",
    ),
    "verified_official_inauguration_observation": (
        "Partido informado na posse", "Observação na data da posse; "
        "não comprova filiação durante todo o mandato.", "Fonte da posse",
    ),
    "verified_official_dated_government_observation": (
        "Partido informado na data documentada", "Observação durante o exercício; "
        "não comprova filiação durante todo o mandato.", "Fonte da observação",
    ),
}


def dashboard_stylesheet():
    return (Path(__file__).parent / "panorama.css").read_text(encoding="utf-8")


def render_state_options(selected, *, national=False):
    options = ['<option value="">Brasil inteiro</option>'] if national else []
    for code, name in STATE_NAMES.items():
        checked = " selected" if code == selected else ""
        options.append(f'<option value="{code}"{checked}>{text(name)} · {code}</option>')
    return "".join(options)


def render_municipality_options(data):
    options = ['<option value="">Todo o estado</option>']
    for municipality in data.get("municipalities", []):
        selected = " selected" if municipality["ibge_code"] == data["municipality_ibge"] else ""
        options.append(
            f'<option value="{text(municipality["ibge_code"])}"{selected}>'
            f"{text(municipality['name'])}</option>"
        )
    return "".join(options)


def render_filters(data, today):
    selected = data["uf"] if data["level"] != "federal" else "BR"
    checked = " selected" if selected == "BR" else ""
    options = f'<option value="BR"{checked}>Brasil inteiro</option>'
    options += render_state_options(selected)
    state_form = f'''<form class="panorama-filters" aria-label="Escolher estado"
action="/panorama" method="get">
<label>Estado<select name="territory">{options}</select></label>
<input type="hidden" name="view" value="{text(data.get('view', 'political_party'))}">
<button type="submit">Ver estado</button></form>'''
    municipality_form = ""
    if data["level"] != "federal" and data["uf"] != "DF":
        municipality_form = f'''<form class="panorama-filters" aria-label="Escolher município"
action="/panorama" method="get">
<input type="hidden" name="territory" value="{text(data['uf'])}">
<input type="hidden" name="view" value="{text(data.get('view', 'political_party'))}">
<label>Municípios de {text(data['state_name'])}<select name="municipality_ibge">
{render_municipality_options(data)}</select></label>
<button type="submit">Ver município</button></form>'''
    return f'<div class="panorama-geography-navigation">{state_form}{municipality_form}</div>'


def render_members(composition, *, annual=False):
    if not composition.get("members"):
        return '<p class="panorama-caption">Relação nominal ainda não disponível.</p>'
    members = "".join(
        f"<li>{render_person_name(member)}"
        f"<span>{text(member.get('political_party'))} · {text(member.get('uf'))}</span>"
        f"<span>{text(member.get('period_description') or member.get('observed_on'), '')}"
        "</span></li>"
        for member in composition["members"]
    )
    label = "Ver integrantes documentados" if annual else "Ver composição nominal"
    return (
        f'<details class="panorama-members"><summary>{label}</summary><ul>{members}</ul></details>'
    )


def render_person_name(member):
    try:
        UUID(str(member.get("person_id")))
    except ValueError:
        return text(member["name"])
    return f'<a href="{person_path(member["person_id"])}">{text(member["name"])}</a>'


def render_annual_participation(composition):
    political_parties = composition.get("distinct_people_observed_during_year", [])
    if not political_parties:
        return ""
    entries = "".join(
        f"<li><span>{text(political_party['abbreviation'])}</span>"
        f"<strong>{political_party['distinct_people']}</strong></li>"
        for political_party in political_parties
    )
    return f"""<details class="panorama-annual-participation">
<summary>Pessoas observadas ao longo do ano por partido</summary>
<p class="panorama-caption">Pessoas distintas registradas no ano, não cadeiras simultâneas.
Uma pessoa pode aparecer em mais de um partido se mudou de filiação.</p>
<ul>{entries}</ul></details>"""



def render_institutional_status(composition, title, eyebrow):
    evidence = composition.get("institutional_status_evidence") or {}
    source = official_url(evidence.get("url"))
    source_link = (
        f'<a href="{text(source)}" target="_blank" rel="noopener noreferrer">'
        'Ler história institucional ↗</a>' if source else ""
    )
    return (
        f'<section class="panorama-panel"><p class="eyebrow">{text(eyebrow)}</p>'
        f'<h2>{text(title)}</h2><p><strong>'
        f'{text(composition.get("institutional_status_label"))}</strong></p>'
        '<p class="panorama-caption">A ausência de composição decorre da suspensão '
        'do funcionamento da instituição neste ano.</p>' + source_link
        + render_senate_election_observations(composition) + '</section>'
    )


def composition_chart_presentation(composition, title, view, year, reference_on):
    presentation = composition_presentation(composition)
    if view != "political_orientation" or not (
        title.startswith("Senado") or title == "Câmara dos Deputados"
    ):
        return presentation, ""
    selected_year = int(year or str(reference_on or composition.get("snapshot_on") or "0")[:4])
    from service.political_dashboard.senate_orientation_2026 import (
        render_senate_orientation_summary,
    )

    presentation = orientation_composition(presentation, selected_year)
    note = render_orientation_composition_note(composition, selected_year, reference_on)
    return presentation, note + render_senate_orientation_summary(presentation)


def render_composition(composition, title, eyebrow, official_link, *,
                       view="political_party", year=None, reference_on=None):
    if composition.get("institutional_status") == "suspended_whole_year":
        return render_institutional_status(composition, title, eyebrow)
    presentation, orientation_note = composition_chart_presentation(
        composition, title, view, year, reference_on
    )
    total = presentation["total"]
    historical = composition.get("aggregation_basis") == (
        "verified_exercises_and_affiliations_at_year_end"
    )
    for evidence in composition.get("evidence", []):
        if source := official_url(evidence.get("url")):
            official_link = source
            break
    roster_only = presentation["presentation_basis"] == "historical_roster"
    if roster_only:
        official_link = official_url(composition["historical_roster"][0]["official_url"])
    source_description = (
        "Listagem histórica da legislatura" if roster_only else "Filiação registrada na observação"
    )
    caption = render_composition_reference(composition, historical)
    if presentation["presentation_basis"] != "snapshot":
        caption = ('<p class="panorama-caption">Integrantes documentados no período; '
                   'não representa cadeiras simultâneas. As filiações atuais não são '
                   'aplicadas ao passado.</p>')
    count_label = presentation["count_label"] if total else "Composição ainda não documentada"
    chamber = title == "Câmara dos Deputados"
    diagram = (
        render_people_semicircle(presentation) if title.startswith("Senado") or chamber else ""
    )
    contents = f"""{orientation_note}{diagram}
<div class="panorama-total"><strong>{total or "—"}</strong>
<span>{text(count_label)}</span></div>
{render_party_bars(presentation, compact=title.startswith("Senado"), vertical=chamber)}
<details class="panorama-source-notes"><summary>Como consultar a composição</summary>
{caption}</details>
{render_members(presentation, annual=presentation["presentation_basis"] != "snapshot")}"""
    panel_class = "panorama-panel" if diagram else "panorama-panel panorama-panel-bars"
    if chamber:
        panel_class += " panorama-panel-chamber"
    if orientation_note:
        panel_class += " panorama-orientation-composition"
    return f'''<section class="{panel_class}"><p class="eyebrow">{eyebrow}</p>
<h2>{text(title)}</h2><span class="panorama-coverage-tag">Cobertura documentada</span>
{contents}{render_annual_participation(composition)}
{render_senate_election_observations(composition)}
<div class="panorama-panel-foot"><span>{source_description}</span>
<a href="{official_link}" target="_blank" rel="noopener noreferrer">Verificar fonte ↗</a>
</div></section>'''


def render_composition_reference(composition, historical):
    if composition.get("aggregation_basis") == "verified_dated_official_senate_composition":
        return (
            f'<p class="panorama-caption">Observação oficial: '
            f'{text(composition.get("observed_on"))}. '
            'Distribuição agregada de cadeiras por partido nessa data. '
            'Não equivale à ocupação durante todo o ano; a fonte não fornece '
            'a relação nominal nesta composição.</p>'
        )
    if composition.get("aggregation_basis") == (
        "verified_year_end_status_of_historical_legislature_rosters"
    ):
        return (
            '<p class="panorama-caption">Exercício e filiação documentados em 31/12 '
            'a partir das relações históricas das legislaturas. Cobertura histórica '
            'parcial; não representa todas as pessoas que passaram pelo cargo no ano.</p>'
        )
    if historical:
        return (
            '<p class="panorama-caption">Referência anual: '
            f'{text(composition.get("reference_on"))}. '
            'Calculada a partir dos intervalos oficiais de exercício e filiação. '
            'Não representa todas as pessoas que passaram pelo cargo durante o ano.</p>'
        )
    if composition.get("aggregation_basis") == (
        "official_active_legislature_registry_not_individual_exercise_confirmation"
    ):
        return (
            '<p class="panorama-caption">Cadastro ativo oficial na legislatura observada. '
            'Não constitui confirmação individual de exercício ou de ocupação contínua.</p>'
        )
    if composition.get("aggregation_basis") == (
        "official_roster_reconciled_with_dated_exercise_evidence"
    ):
        return (
            '<p class="panorama-caption">Registros conciliados com evidências de datas distintas. '
            'A contagem não representa uma fotografia simultânea de todas as cadeiras.</p>'
        )
    if composition.get("aggregation_basis") == "verified_year_end_status_of_current_roster_cohort":
        return (
            '<p class="panorama-caption">Exercício em 31/12 entre parlamentares da composição '
            'atual. Cobertura histórica parcial: faltam antigos parlamentares.</p>'
        )
    return (
        f'<p class="panorama-caption">Observação: {text(composition.get("observed_on"))}. '
        'Última composição observada no ano; não equivale à ocupação durante todo o ano. '
        'Cobertura dos perfis cadastrados; não representa apuração de vagas.</p>'
    )


def render_historical_roster(composition):
    rows = composition.get("historical_roster", [])
    if not rows:
        return ""
    grouped = {}
    for row in rows:
        grouped.setdefault(row["legislature"], []).append(row)
    contents = []
    for legislature, records in sorted(grouped.items()):
        people = "".join(
            f'<li>{render_person_name(row)} · {text(row["uf"])}</li>'
            for row in records
        )
        source = official_url(records[0]["official_url"])
        contents.append(
            f'<details class="panorama-members"><summary>{legislature}ª legislatura · '
            f'{len(records)} registros históricos</summary>'
            f'<p>{text(records[0]["period_start"])} a {text(records[0]["period_end"])}</p>'
            f'<ul>{people}</ul><a href="{text(source)}" target="_blank" '
            'rel="noopener noreferrer">Ler listagem oficial ↗</a></details>'
        )
    return (
        '<div class="panorama-historical-roster"><h3>Integrantes documentados da legislatura</h3>'
        '<p class="panorama-caption">A fonte lista integrantes do período legislativo. '
        'Isso não confirma que todos exerceram simultaneamente ou durante todo o ano '
        'selecionado. As filiações atuais não são aplicadas ao passado.</p>'
        + "".join(contents) + '</div>'
    )


def render_executive_source(segment):
    candidates = [segment.get("official_url")]
    candidates.extend(evidence.get("url") for evidence in segment.get("evidence", []))
    url = next((url for value in candidates if (url := official_url(value))), None)
    return (
        f'<a href="{text(url)}" target="_blank" rel="noopener noreferrer">Ler fonte ↗</a>'
        if url
        else ""
    )



def political_party_qualifier(segment):
    if segment.get("political_party_context") in {
        "legal_party_prohibition_not_personal_affiliation",
        "legal_party_extinction_not_personal_affiliation",
    }:
        return ("Situação legal dos partidos", "Regime jurídico do período; "
                "não é informação sobre filiação pessoal.", "Fonte do regime jurídico")
    return POLITICAL_PARTY_QUALIFIERS.get(segment.get("political_party_status"))


def render_executive_political_party_sources(segment):
    links = []
    seen = set()
    qualifier = political_party_qualifier(segment)
    label = qualifier[2] if qualifier else "Fonte da filiação"
    for evidence in segment.get("political_party_evidence", []):
        url = official_url(evidence.get("url"))
        if url and url not in seen:
            seen.add(url)
            links.append(
                f'<a href="{text(url)}" target="_blank" rel="noopener noreferrer" '
                f'aria-label="{label}">Fonte do partido ↗</a>'
            )
    return " ".join(links)


def render_executive_political_party(segment):
    value = text(segment.get("political_party"))
    reference = (
        '<span>Último partido documentado neste exercício no ano</span>'
        if segment.get("political_party_reference") == (
            "last_documented_party_period_during_exercise_in_year"
        ) else ""
    )
    qualifier = political_party_qualifier(segment)
    if qualifier:
        dates = sorted({
            item["observed_on"] for item in segment.get("political_party_evidence", [])
            if item.get("observed_on")
        })
        observation = f' · Data documentada: {text(", ".join(dates))}' if dates else ""
        return (
            f'<strong class="panorama-executive-party">{value}</strong>{reference}'
            f'<span>{qualifier[0]}{observation}</span><span>{qualifier[1]}</span>'
        )
    return f'<span>{value}</span>{reference}'


def render_executive_annual_summary(segments):
    named = {}
    for segment in segments:
        key = (
            segment.get("name"),
            segment.get("political_party"),
            segment.get("political_party_status"),
        )
        named.setdefault(key, segment)
    rows = "".join(
        f'<li><strong>{render_person_name(segment)}</strong>'
        f'{render_executive_political_party(segment)}{render_executive_source(segment)}'
        f'{render_executive_political_party_sources(segment)}</li>'
        for segment in named.values()
    )
    return (
        '<p class="panorama-executive-year">Exerceram neste ano</p>'
        f'<ul class="panorama-executive-summary">{rows}</ul>'
    )


def render_executive_period(segment):
    if segment.get("date_precision") == "year":
        return (
            f"{text(segment.get('year_start'))}–{text(segment.get('year_end'))}"
            " · Datas precisas ainda não verificadas"
        )
    end = segment.get("ends_before")
    ended_on = date.fromisoformat(end) - timedelta(days=1) if end else None
    if not ended_on and segment.get("observed_through"):
        return (
            f"Início: {text(segment.get('starts_on'))} · "
            f"Exercício documentado até: {text(segment['observed_through'])}"
        )
    return (
        f"Início: {text(segment.get('starts_on'))} · Fim: {text(ended_on, 'Ainda não informado')}"
    )



def executive_presentation_record(executive):
    selected = executive.get("current")
    observations = executive.get("national_observations", [])
    if not observations:
        return selected
    return max(observations, key=lambda item: item.get("source_observed_on") or "")


def render_executive(executive, title, eyebrow, *, view="political_party", year=None):
    from service.political_dashboard.executive_orientation_presentation import (
        render_executive_orientation,
    )

    segments = executive.get("segments", [])
    selected = executive_presentation_record(executive)
    if selected:
        details = (
            f"<h3>{render_person_name(selected)}</h3>"
            f"<p>{render_executive_political_party(selected)}</p>"
            + (f'<p>Observação oficial: {text(selected["source_observed_on"])}</p>'
               if selected.get("source_observed_on") else "")
            + '<div class="panorama-executive-links">'
            + render_executive_source(selected)
            + render_executive_political_party_sources(selected) + '</div>' 
        )
    elif segments:
        details = render_executive_annual_summary(segments)
    elif executive.get("coverage") == "not_applicable":
        details = f'<p>{text(executive.get("context_description"))}</p>'
    else:
        details = '<div class="panorama-government-status">Histórico em construção</div>'
        details += "<p>Não há exercício documentado para o ano selecionado neste recorte.</p>"
    history = "".join(
        f"<li><strong>{render_person_name(segment)}</strong>"
        f"{render_executive_political_party(segment)}"
        f"<span>{render_executive_period(segment)}</span>{render_executive_source(segment)}"
        f"{render_executive_political_party_sources(segment)}</li>"
        for segment in segments
    )
    periods = (
        ("<details><summary>Períodos documentados</summary><ul>" + history + "</ul></details>")
        if history
        else ""
    )
    return f"""<section class="panorama-government"><p class="eyebrow">{eyebrow}</p>
<h2>{text(title)}</h2>{details}{render_executive_orientation(executive, view, year)}
<a href="#panorama-history">Consultar cobertura histórica ↓</a>
{periods}{render_executive_party_periods(executive)}
{render_executive_observations(executive)}
{render_government_context_observations(executive.get("government_context_observations"))}
</section>"""




def render_executive_party_periods(executive):
    periods = [period for segment in executive.get("segments", [])
               for period in segment.get("political_party_periods", [])]
    if not periods:
        periods = (executive.get("current") or {}).get("political_party_periods", [])
    if not periods:
        return ""
    rows = []
    for period in periods:
        end = period.get("ends_before")
        last_day = date.fromisoformat(end) - timedelta(days=1) if end else None
        interval = f"{text(period.get('starts_on'))} a {text(last_day, 'fim não documentado')}"
        if period.get("date_precision") == "year":
            start_year = str(period.get("starts_on") or period.get("year_start"))[:4]
            end_year = str(last_day.year) if last_day else text(period.get("year_end"))
            interval = f"{text(start_year)}–{text(end_year)} · Classificação anual"
        rows.append(
            f'<li><strong>{text(period["political_party"])}</strong><span>{interval}</span>'
            f'{render_executive_source(period)}</li>'
        )
    return (
        '<details><summary>Partidos e mudanças neste ano</summary>'
        '<p>Intervalos sem registro permanecem sem comprovação; '
        'não são preenchidos por inferência.</p>'
        f'<ul>{"".join(rows)}</ul></details>'
    )


def render_executive_observations(executive):
    observations = executive.get("national_observations", [])
    if not observations:
        return ""
    rows = "".join(
        f'<li><strong>{text(item["name"])}</strong>'
        f'<span>{text(item.get("source_observed_on"))}</span>'
        f'{render_executive_political_party(item)}{render_executive_source(item)}</li>'
        for item in observations
    )
    latest = max(observations, key=lambda item: item.get("source_observed_on") or "")
    earlier_party = any(str(item.get("political_party_status", "")).startswith("verified_")
                        for item in observations)
    latest_verified = str(latest.get("political_party_status", "")).startswith("verified_")
    expanded = " open" if earlier_party and not latest_verified else ""
    return (
        f'<details{expanded}><summary>Observações oficiais no ano</summary>'
        '<p>Informação comprovada na data indicada, sem presumir filiação contínua.</p>'
        f'<ul>{rows}</ul></details>'
    )


def composition_view_context(data):
    return {"view": data.get("view", "political_party"),
            "year": int(data.get("year", data["as_of"][:4])), "reference_on": data["as_of"]}


def render_level_panels(data):
    if data["level"] == "federal":
        senate = render_composition(
            data["senate"],
            "Senado Federal",
            "Representação nacional",
            "https://www25.senado.leg.br/web/senadores/em-exercicio",
            **composition_view_context(data),
        )
        executive = render_executive(
            data["presidency"], "Presidência da República", "Poder Executivo federal",
            view=data.get("view", "political_party"), year=data.get("year"),
        )
        chamber = render_composition(
            data["federal_chamber"],
            "Câmara dos Deputados",
            "Representação nacional",
            "https://www.camara.leg.br/deputados/",
            **composition_view_context(data),
        )
        return senate + executive + chamber
    if data["level"] == "municipal":
        executive = render_executive(
            data.get("mayoralty", {"coverage": "not_available", "segments": []}),
            "Prefeitura",
            "Poder Executivo municipal",
        )
        chamber = render_composition(
            data["municipal_council"],
            "Câmara Municipal",
            "Poder Legislativo municipal",
            "https://www.ibge.gov.br/cidades-e-estados.html",
        )
        return executive + chamber
    assembly_code = data["assembly"]["institution_code"]
    assembly_title = "Assembleia de " + data["state_name"]
    if data["uf"] == "DF":
        assembly_title = "Câmara Legislativa do Distrito Federal"
    source = {
        "alesp": "https://www.al.sp.gov.br/deputados/",
        "alerj": "https://www.alerj.rj.gov.br/Deputados/QuemSao",
    }.get(assembly_code, "https://www12.senado.leg.br/interparlamento")
    executive = render_executive(
        data["government"], "Governo · " + data["state_name"], "Poder Executivo estadual"
    )
    assembly = render_composition(
        data["assembly"], assembly_title, "Poder Legislativo estadual", source
    )
    senate = render_composition(
        data["senate"], "Senado Federal · " + data["uf"], "Representação do estado",
        "https://www25.senado.leg.br/web/senadores/em-exercicio",
        **composition_view_context(data),
    )
    return senate + '<div class="panorama-right">' + executive + assembly + '</div>'


def render_history(data):
    grouping_description = (
        "Legislativos: maior grupo documentado por abordagem política na referência anual. "
        "Executivos: classificação dos partidos documentados no período."
        if data.get("view") == "political_orientation"
        else "Legislativos: maior bancada documentada na referência anual. "
        "Executivos: partido registrado nas fontes do período."
    )
    return f"""<section class="panorama-history" id="panorama-history">
<p class="eyebrow">A composição muda. O histórico fica.</p>
<h2>Partidos e acontecimentos ao longo do tempo</h2>
<p>A linha do tempo começa em 1880. Selecione um período para consultar seus integrantes,
mantendo o estado ou município escolhido.</p>
<p class="panorama-timeline-hint">Deslize a linha do tempo para ver todos os períodos.</p>
{render_timeline_bands(data)}{render_orientation_annual_summary(data)}
{render_presidential_explanations(data)}
<p class="panorama-history-selection">{data.get('year', data['as_of'][:4])} selecionado</p>
<p class="panorama-caption">{grouping_description} Em 1888, o Brasil era uma monarquia;
a Presidência começa em 1889. As faixas mostram os partidos documentados;
as cores claras indicam ausência de dados. A cobertura pode ser parcial;
consulte os detalhes de cada ano e as fontes.
Lacunas não significam ausência de representação. O território mudou ao longo do tempo.</p>
</section>"""


def render_dashboard(data, today):
    territory_name = "Brasil" if data["level"] == "federal" else data["state_name"]
    if data["level"] == "municipal":
        selected = next(
            (
                item
                for item in data.get("municipalities", [])
                if item["ibge_code"] == data["municipality_ibge"]
            ),
            None,
        )
        if selected:
            territory_name = selected["name"] + " · " + data["uf"]
    geography_notice = ""
    if data["uf"] == "DF" and int(data["as_of"][:4]) < 1889:
        geography_notice = (
            '<p class="panorama-geography">O Distrito Federal ainda não existia neste período. '
            'O território atual não se aplica retroativamente.</p>'
        )
    elif data["uf"] == "DF" and int(data["as_of"][:4]) < 1960:
        geography_notice = (
            '<p class="panorama-geography">O Distrito Federal desta época tinha sede '
            "no Rio de Janeiro. O território atual não se aplica retroativamente "
            "a este recorte.</p>"
        )
    content = f"""<div class="panorama"><header class="panorama-intro"><div>
<p class="eyebrow">Quem representa você</p>
<h1>O poder, em perspectiva.</h1>
<p>Da Presidência à sua cidade: acompanhe os partidos e quem exerce cada cargo.
Explore diferentes épocas, do Senado no Império à representação atual.</p></div>
<div class="panorama-stamp">PANORAMA POLÍTICO
<strong>{text(territory_name)}</strong>
<span>Ano: {data.get("year", data["as_of"][:4])} · Referência: {data["as_of"]}</span></div></header>
<div class="panorama-filter-row">{render_filters(data, today)}
{render_timeline_view_filter(data)}</div>{geography_notice}
{render_orientation_glossary(data)}
{render_orientation_legend(data)}
<div class="panorama-grid" id="panorama-results">{render_level_panels(data)}</div>
{render_history(data)}
<aside class="panorama-coverage"><details><summary>Fontes e cobertura</summary>
<p>As contagens usam observações oficiais datadas.
Uma observação atual não preenche o passado. 
Suplentes entram apenas quando o exercício está confirmado.
Partidos informados pela fonte são preservados 
mesmo quando a filiação ainda não foi reconciliada no cadastro.</p>
<p>Selecione um estado e depois seus municípios. Cada instituição apresenta apenas
os dados documentados; a cobertura pode variar conforme o ano e o território.</p>
</details></aside></div>"""
    return render_layout(
        "Panorama político",
        content,
        extra_stylesheet="/assets/panorama.css",
        active_section="panorama",
    )
