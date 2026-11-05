"""Timeline "Por bloco": summary sentence, Senado/Câmara column charts and president chips."""

from service.majority_panorama.bloc_view import bloc_label, rounded_percent
from service.majority_panorama.blocs import BLOC_BY_KEY, IDEOLOGICAL_BLOC_KEYS
from service.majority_panorama.selection import selected_legislature
from web_components import ChartColumn, render_column_chart
from web_components.escaping import escape_text
from web_components.stacked_bar import bloc_class_suffix

CHART_TITLES = (("senado", "no Senado"), ("camara", "na Câmara dos Deputados"))


def _house_of(legislature, house_key):
    return legislature.senado if house_key == "senado" else legislature.camara


def is_classified(house):
    """True when at least one seat is placed on the left-right scale of the catalog."""
    return house is not None and any(house.seats(key) for key in IDEOLOGICAL_BLOC_KEYS)


def _column(state, legislature, house_key, bloc_key, selected_id):
    house = _house_of(legislature, house_key)
    # A bloc share is only meaningful when the house was classified: "0%" would hide the gap.
    neutral_bloc = not BLOC_BY_KEY[bloc_key].ideological
    has_value = house is not None and (is_classified(house) or neutral_bloc)
    percent = house.seats(bloc_key) / house.total * 100 if has_value else 0
    text = f"{rounded_percent(house.seats(bloc_key), house.total)}%" if has_value else "–"
    missing = "sem dados" if house is None else "sem classificação"
    aria = f"{legislature.label}: " + (text if has_value else missing)
    return ChartColumn(
        bloc_key=bloc_key,
        percent=percent,
        value_text=text,
        axis_label=str(legislature.first_year),
        aria_label=aria,
        url=state.link("periodo", legislature_id=legislature.legislature_id, highlight=None),
        selected=legislature.legislature_id == selected_id,
    )


def render_bloc_charts(panorama, state):
    selected = selected_legislature(panorama, state)
    selected_id = selected.legislature_id if selected else None
    bloc_key = state.timeline_bloc
    charts = []
    for house_key, suffix in CHART_TITLES:
        columns = [
            _column(state, legislature, house_key, bloc_key, selected_id)
            for legislature in panorama.legislatures
        ]
        charts.append(render_column_chart(f"{bloc_label(bloc_key)} {suffix}", columns))
    return "".join(charts)


def _strongest_camara_legislature(panorama, bloc_key):
    """Legislature where the bloc held its largest Câmara share; the earliest wins ties."""
    candidates = [
        legislature for legislature in panorama.legislatures if legislature.camara is not None
    ]
    return max(
        candidates,
        key=lambda item: item.camara.seats(bloc_key) / item.camara.total,
        default=None,
    )


def _has_unclassified_period(panorama):
    return any(
        house is not None and not is_classified(house)
        for legislature in panorama.legislatures
        for house in (legislature.camara, legislature.senado)
    )


def _ever_held_majority(panorama, bloc_key):
    return any(
        house is not None and house.seats(bloc_key) >= house.majority_threshold
        for legislature in panorama.legislatures
        for house in (legislature.camara, legislature.senado)
    )


def bloc_summary_text(panorama, bloc_key):
    """Sentence computed from the data: the bloc's best Câmara period and whether it ever won."""
    legislature = _strongest_camara_legislature(panorama, bloc_key)
    if legislature is None:
        return f"{bloc_label(bloc_key)}: ainda não há dados de composição da Câmara."
    camara = legislature.camara
    ever = (
        "Já teve maioria sozinha em pelo menos uma Casa."
        if _ever_held_majority(panorama, bloc_key)
        else "Nunca passou da metade sozinha nas Casas classificadas."
    )
    gap = (
        " Períodos sem classificação ideológica aparecem como “–” e não entram na comparação."
        if _has_unclassified_period(panorama) else ""
    )
    return (
        f"{bloc_label(bloc_key)}: maior presença na Câmara em {legislature.label} "
        f"({rounded_percent(camara.seats(bloc_key), camara.total)}%). {ever}{gap}"
    )


def _render_chip(term, bloc_key):
    highlighted = term.bloc_key == bloc_key
    classes = "ds-president-chip"
    if highlighted:
        classes += f" ds-president-chip--highlight ds-bloc--{bloc_class_suffix(bloc_key)}"
    return (
        f'<span class="{classes}"><span><strong>{escape_text(term.short_name)}</strong> '
        f"{escape_text(term.span_label)}</span></span>"
    )


def render_president_chips(panorama, state):
    bloc_key = state.timeline_bloc
    chips = "".join(_render_chip(term, bloc_key) for term in panorama.presidents)
    return (
        '<div class="ds-timeline__presidents"><span class="ds-timeline__presidents-title">'
        f"Presidentes · em destaque os de {escape_text(bloc_label(bloc_key).lower())}</span>"
        f'<div class="ds-timeline__chips">{chips}</div></div>'
    )


def render_bloc_timeline(panorama, state):
    summary = escape_text(bloc_summary_text(panorama, state.timeline_bloc))
    return (
        '<div class="ds-timeline__bloc-view">'
        f'<p class="ds-timeline__summary">{summary}</p>'
        f"{render_bloc_charts(panorama, state)}{render_president_chips(panorama, state)}</div>"
    )
