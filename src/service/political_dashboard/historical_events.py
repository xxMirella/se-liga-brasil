"""Source-qualified historical context, independent of institutional observations."""

from dataclasses import dataclass

from service.public_profile_web.security import text


@dataclass(frozen=True)
class HistoricalEvent:
    code: str
    label: str
    geography: str
    start_year: int
    end_year: int
    date_description: str
    source_title: str
    source_url: str
    color: str


HISTORICAL_EVENTS = (
    HistoricalEvent(
        "abolition", "Abolição legal da escravidão", "Brasil", 1888, 1888,
        "13 de maio de 1888 · Lei nº 3.353 (Lei Áurea)", "Presidência da República · Lei nº 3.353",
        "https://www.planalto.gov.br/ccivil_03/leis/lim/lim3353.htm", "#56866c",
    ),
    HistoricalEvent(
        "presidential_system", "Início do presidencialismo republicano", "Brasil", 1889, 1889,
        "15 de novembro de 1889 · Proclamação da República; "
        "experiência parlamentarista posterior em 1961–1963",
        "Presidência da República · Decreto nº 1, de 15 de novembro de 1889",
        "https://www.planalto.gov.br/ccivil_03/decreto/1851-1899/d0001.htm", "#236049",
    ),
    HistoricalEvent(
        "nazi_regime", "Regime nazista", "Alemanha", 1933, 1945,
        "30 de janeiro de 1933 a 8 de maio de 1945", "United States Holocaust Memorial Museum",
        "https://encyclopedia.ushmm.org/content/en/article/third-reich", "#9b8b9f",
    ),
    HistoricalEvent(
        "military_dictatorship", "Ditadura militar", "Brasil", 1964, 1985,
        "1964–1985 · delimitação anual do Arquivo Nacional", "Arquivo Nacional",
        "https://www.gov.br/arquivonacional/pt-br/servicos/acervos/"
        "copy_of_acervos-mais-consultados/acervos-sobre-o-regime-militar-1964-1985", "#c79d58",
    ),
)


def event_coordinates(event, first_year, last_year, x_start, year_width):
    """Clip annual positions to the visible axis; exact dates remain in the legend."""
    if event.end_year < first_year or event.start_year > last_year:
        return None
    start = max(event.start_year, first_year)
    end = min(event.end_year, last_year)
    return (x_start + (start - first_year + .5) * year_width,
            x_start + (end - first_year + .5) * year_width)


def render_historical_event(event, coordinates, y):
    start, end = coordinates
    description = f"{event.label} · {event.geography} · {event.date_description}"
    legend = f"{event.label} · {event.geography} · {event.start_year}"
    if event.end_year != event.start_year:
        legend += f"–{event.end_year}"
    # Left-aligned captions remain readable even for a one-year point at the axis boundary.
    caption_x = min(start, 870)
    line = (f'<path d="M{start:.2f} {y + 12}H{end:.2f}'
            f'M{start:.2f} {y + 5}V{y + 19}M{end:.2f} {y + 5}V{y + 19}" '
            f'stroke="{event.color}" stroke-width="2" fill="none"/>')
    if start == end:
        line = (f'<path d="M{start:.2f} {y + 5}V{y + 19}" '
                f'stroke="{event.color}" stroke-width="2"/>')
    return (f'<g aria-label="{text(description)}"><title>{text(description)}</title>'
            f'<text x="{caption_x:.2f}" y="{y - 3}" fill="#203d32">'
            f'{text(legend)}</text>{line}</g>')


def render_historical_events(first_year, last_year, x_start, year_width):
    elements = ['<text x="0" y="54">Contexto histórico</text>']
    for index, event in enumerate(HISTORICAL_EVENTS):
        coordinates = event_coordinates(event, first_year, last_year, x_start, year_width)
        if coordinates:
            elements.append(render_historical_event(event, coordinates, 54 + index * 45))
    return "".join(elements)


def render_historical_event_sources():
    sources = "".join(
        f'<li><strong>{text(event.label)} · {text(event.geography)}</strong>: '
        f'{text(event.date_description)}. <a href="{text(event.source_url)}" '
        f'target="_blank" rel="noopener noreferrer">{text(event.source_title)} ↗</a></li>'
        for event in HISTORICAL_EVENTS
    )
    return ('<details class="panorama-historical-event-sources">'
            '<summary>Marcos históricos e fontes</summary>'
            '<p>As linhas com terminações verticais delimitam períodos; '
            '1888 e 1889 são marcos pontuais. '
            'Este contexto reúne acontecimentos de países diferentes. '
            'As posições anuais não representam datas exatas nem filiação partidária.</p>'
            f'<ul>{sources}</ul>'
            '<p>O marco de 1889 indica a origem republicana do sistema presidencial, '
            'sem afirmar continuidade: houve experiência parlamentarista em 1961–1963. '
            '<a href="https://www.tse.jus.br/eleicoes/plebiscitos-e-referendos/'
            'referendo-1963/referendo-de-1963" target="_blank" rel="noopener noreferrer">'
            'TSE · Referendo de 1963 ↗</a></p></details>')


def historical_context_height():
    return 54 + len(HISTORICAL_EVENTS) * 45
