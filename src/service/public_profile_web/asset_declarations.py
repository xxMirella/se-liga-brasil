"""Bounded public display of election declarations, separate from current wealth."""

from decimal import Decimal, InvalidOperation
from itertools import islice

from service.public_profile_web.security import official_url, text


def format_declared_amount(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or abs(amount) >= Decimal("1e21"):
            return "Não disponível"
        formatted = format(amount, ",.2f").translate(str.maketrans({",": ".", ".": ","}))
    except (InvalidOperation, ValueError):
        return "Não disponível"
    return "R$ " + formatted


def render_declared_item(item):
    label = text(item.get("asset_type"), "Tipo não informado")
    amount = format_declared_amount(item.get("declared_value"))
    review = " · Valor em revisão" if item.get("value_quality_status") != "reported" else ""
    return f"<li><strong>{label}</strong> · {amount}{review}</li>"


def render_declaration_sources(items):
    urls = dict.fromkeys(official_url(item.get("official_url")) for item in items)
    links = [
        f'<a href="{text(url)}" target="_blank" rel="noopener noreferrer">Fonte oficial no TSE</a>'
        for url in islice((url for url in urls if url), 20)
    ]
    return '<p class="explanation">' + " · ".join(links) + "</p>" if links else ""


def render_asset_year(declaration):
    items = list(islice(declaration.get("items") or [], 100))
    year = text(declaration.get("election_year"))
    total = format_declared_amount(declaration.get("recorded_total"))
    count = text(declaration.get("item_count"), "Quantidade não informada")
    review = (
        "<p>Há valores em revisão nesta declaração.</p>"
        if declaration.get("value_quality_status") == "requires_review"
        else ""
    )
    truncated = (
        "<p>Exibindo até 100 itens dos registros disponíveis.</p>"
        if declaration.get("items_truncated") or len(declaration.get("items") or []) > 100
        else ""
    )
    rows = "".join(render_declared_item(item) for item in items)
    source_date = text(declaration.get("source_generated_at"), "Não informada")
    return f"""<article class="timeline-event"><div class="event-date">
<strong>{year}</strong><span>Mês não informado</span></div>
<div class="event-body"><p class="category">DECLARAÇÃO DE BENS</p>
<h3>Bens declarados · {year}</h3>
<p><strong>{total}</strong> · Soma dos registros disponíveis</p>
<p>{count} registros · Declaração eleitoral do TSE</p>{review}
<details><summary>Ver tipos e valores declarados</summary><ul>{rows}</ul>{truncated}
<p class="explanation">Geração da fonte: {source_date}.</p>
{render_declaration_sources(items)}</details></div></article>"""


def render_asset_declarations(profile):
    assets = profile.get("assets") or {}
    declarations = list(islice(assets.get("declarations") or [], 100))
    heading = (
        '<section aria-labelledby="asset-declarations">'
        '<h2 id="asset-declarations">Bens declarados</h2>'
    )
    if not declarations:
        return (
            heading + '<p class="empty-state">Declarações de bens ainda não disponíveis '
            "neste perfil.</p></section>"
        )
    cards = "".join(render_asset_year(declaration) for declaration in declarations)
    limited = (
        "<p>Exibindo até 100 anos disponíveis.</p>"
        if (assets.get("coverage") or {}).get("years_truncated")
        else ""
    )
    return (
        heading + '<p class="explanation">Valores declarados à Justiça Eleitoral por ano; '
        "não representam patrimônio atual. Cobertura parcial dos registros disponíveis.</p>"
        + '<div class="timeline activity-timeline">' + cards + '</div>'
        + limited
        + "</section>"
    )
