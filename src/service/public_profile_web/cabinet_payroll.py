"""Cabinet cost card and accessible monthly role history, without client scripts."""

from service.public_profile_web.asset_declarations import format_declared_amount
from service.public_profile_web.security import official_url, text


def render_cabinet_cost(profile):
    payroll = profile.get("cabinet_payroll") or {}
    latest = payroll.get("latest")
    if not latest:
        return (
            '<div class="metric"><span>Gastos com gabinete</span>'
            "<strong>Não disponível</strong><small>Folha da equipe ainda não coletada; "
            "não representa gasto zero.</small></div>"
        )
    reference = text(latest["period"])
    amount = format_declared_amount(latest["total_amount"])
    return (
        f'<div class="metric"><span>Gastos com gabinete</span><strong>{amount}</strong>'
        '<button class="attendance-history-button" commandfor="cabinet-payroll-history" '
        'command="show-modal">Ver histórico</button>'
        f"<small>Folha da equipe · {reference} · Última competência coletada</small></div>"
        + render_cabinet_history(payroll)
    )


def render_role_totals(roles, caption):
    rows = "".join(
        f'<tr><th scope="row">{text(row["role"])}</th>'
        f"<td>{format_declared_amount(row['gross_amount'])}</td>"
        f"<td>{format_declared_amount(row['allowances_amount'])}</td>"
        f"<td>{format_declared_amount(row['total_amount'])}</td></tr>"
        for row in roles
    )
    return (
        f'<div class="cabinet-table-scroll"><table class="cabinet-payroll-table">'
        f'<caption>{text(caption)}</caption><thead><tr><th scope="col">Cargo</th>'
        '<th scope="col">Remuneração bruta</th><th scope="col">Auxílios e outras verbas</th>'
        '<th scope="col">Total publicado</th></tr></thead><tbody>' + rows + "</tbody></table></div>"
    )


def render_cabinet_month(month):
    source = official_url(month["sourceUrl"])
    link = f'<a href="{text(source)}">Folha oficial</a>' if source else ""
    return (
        f"<section><h3>{text(month['period'])}</h3>"
        + render_role_totals(month["roles"], "Soma por cargo na competência")
        + f"<p><strong>Total: {format_declared_amount(month['total_amount'])}</strong> · "
        f"{text(month['payment_entries'])} lançamentos · {link}</p></section>"
    )


def render_cabinet_history(payroll):
    months = payroll.get("months") or []
    if not months:
        return ""
    total_history = render_role_totals(
        payroll["totals_by_role"], "Soma por cargo nos meses coletados abaixo"
    )
    truncated = (
        "<p>Exibindo as 120 competências mais recentes coletadas.</p>"
        if payroll.get("truncated")
        else ""
    )
    return (
        '<dialog id="cabinet-payroll-history" class="attendance-dialog cabinet-payroll-dialog" '
        'aria-labelledby="cabinet-payroll-title"><header>'
        '<h2 id="cabinet-payroll-title">Histórico de gastos com gabinete</h2>'
        '<form method="dialog"><button autofocus aria-label="Fechar histórico do gabinete">'
        'Fechar</button></form></header><div class="attendance-dialog-content">'
        "<p>Remuneração bruta da equipe do gabinete e dos escritórios de apoio, "
        "acrescida de diárias, auxílios e verbas "
        "indenizatórias publicados. Exclui o pagamento do parlamentar, encargos patronais "
        "não informados e despesas fora da folha, como aluguel e passagens. "
        "O bruto considera os descontos por faltas. IR e previdência integram o custo, "
        "sem soma em duplicidade. Lançamentos não equivalem a pessoas únicas. "
        "Meses ausentes não significam gasto zero.</p>"
        + truncated
        + total_history
        + "".join(render_cabinet_month(m) for m in months)
        + "</div></dialog>"
    )
