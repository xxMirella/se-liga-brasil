"""Bounded public display of election declarations, separate from current wealth."""

from decimal import Decimal, InvalidOperation
from itertools import islice

from service.public_profile_web.security import official_url, text

MONTHS = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
    "setembro", "outubro", "novembro", "dezembro",
)
def month_label(period):
    try:
        year, month = str(period).split("-")[:2]
        return f"{MONTHS[int(month) - 1]} de {int(year)}"
    except (ValueError, IndexError):
        return text(period)


def format_declared_amount(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or abs(amount) >= Decimal("1e21"):
            return "Não disponível"
        formatted = format(amount, ",.2f").translate(str.maketrans({",": ".", ".": ","}))
    except (InvalidOperation, ValueError):
        return "Não disponível"
    return "R$ " + formatted


def declared_number(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return amount if amount.is_finite() and abs(amount) < Decimal("1e21") else None


def render_declared_item(item):
    label = text(item.get("asset_type"), "Tipo não informado")
    amount = format_declared_amount(item.get("declared_value"))
    review = " · Valor em revisão" if item.get("value_quality_status") != "reported" else ""
    return f"<li>{label} · <strong>{amount}</strong>{review}</li>"


def render_declaration_sources(items):
    urls = dict.fromkeys(official_url(item.get("official_url")) for item in items)
    # One link only: every year points at the same TSE open-data portal, and repeating the label
    # for each year's file looked like a duplicate. Items arrive newest year first.
    links = [
        f'<a href="{text(url)}" target="_blank" rel="noopener noreferrer">TSE ↗</a>'
        for url in islice((url for url in urls if url), 1)
    ]
    return " · ".join(links)


def count_label(count):
    if count is None or count == "":
        return "Registros disponíveis"
    return f"{text(count)} {'registro' if str(count) == '1' else 'registros'}"


def render_asset_bar(total, largest):
    amount = declared_number(total)
    if amount is None or largest is None or amount <= 0:
        return ""
    return (
        f'<progress class="ds-profile-bar" max="{largest}" value="{amount}" '
        f'aria-label="Proporção em relação à maior declaração">{amount}</progress>'
    )


def render_asset_year(declaration, largest):
    items = list(islice(declaration.get("items") or [], 100))
    year = text(declaration.get("election_year"))
    total = format_declared_amount(declaration.get("recorded_total"))
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
    return f"""<div class="ds-profile-asset-year"><div class="ds-profile-asset-head">
<strong>{year}</strong><span>{total}</span></div>
{render_asset_bar(declaration.get("recorded_total"), largest)}{review}
<details><summary>{count_label(declaration.get("item_count"))}</summary>
<ul>{rows}</ul>{truncated}
<p class="ds-profile-note">Geração da fonte: {source_date}.</p></details></div>"""


def largest_declared_total(declarations):
    totals = [declared_number(d.get("recorded_total")) for d in declarations]
    positive = [t for t in totals if t is not None and t > 0]
    return max(positive) if positive else None


def render_asset_declarations(profile):
    assets = profile.get("assets") or {}
    declarations = list(islice(assets.get("declarations") or [], 100))
    heading = '<h3 id="asset-declarations">Bens declarados à Justiça Eleitoral</h3>'
    if not declarations:
        return (
            '<div class="ds-profile-card" aria-labelledby="asset-declarations">' + heading
            + '<p class="empty-state">Declarações de bens ainda não disponíveis '
            "neste perfil.</p></div>"
        )
    largest = largest_declared_total(declarations)
    cards = "".join(render_asset_year(declaration, largest) for declaration in declarations)
    limited = (
        '<p class="ds-profile-note">Exibindo até 100 anos disponíveis.</p>'
        if (assets.get("coverage") or {}).get("years_truncated")
        else ""
    )
    links = render_declaration_sources(
        [item for d in declarations for item in islice(d.get("items") or [], 100)]
    )
    source = f" Fonte: {links}" if links else ""
    return (
        '<div class="ds-profile-card" aria-labelledby="asset-declarations">' + heading
        + cards + limited + '<p class="ds-profile-note">Soma dos registros disponíveis em cada '
        "declaração; não representa o patrimônio atual." + source + "</p></div>"
    )
