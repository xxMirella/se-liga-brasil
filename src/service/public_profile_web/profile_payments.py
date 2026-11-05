"""Published remuneration of the profile person and the cabinet cost, as one card."""

from itertools import islice

from service.public_profile_web.asset_declarations import format_declared_amount, month_label
from service.public_profile_web.cabinet_payroll import render_cabinet_cost
from service.public_profile_web.security import text

ORGANIZATIONS = {"camara": "pela Câmara dos Deputados", "senado": "pelo Senado Federal"}
NOT_CURRENT = (
    "Última publicação disponível; não confirma o mês atual nem equivale "
    "automaticamente ao salário vigente."
)


def render_payment(payment):
    gross = payment.get("gross_amount")
    value = format_declared_amount(gross) if gross is not None else "Não disponível"
    organization = ORGANIZATIONS.get(payment.get("organization_code"))
    source = f", publicado {organization}" if organization else (
        f", publicado por {text(payment.get('organization_code'))}"
    )
    caution = (
        "Competência mais recente publicada; não equivale automaticamente ao salário vigente."
        if payment.get("freshness") == "current_competence"
        else NOT_CURRENT
    )
    return (
        f'<div class="ds-profile-payment"><strong class="ds-profile-amount">{value}</strong>'
        f"<span>Valor bruto referente a {month_label(payment.get('competence'))}{source}.</span>"
        f'<p class="ds-profile-note">{caution}</p></div>'
    )


def render_payments(profile):
    payments = list(islice(profile.get("payments", []), 20))
    body = (
        "".join(render_payment(payment) for payment in payments)
        if payments
        else '<div class="ds-profile-payment"><strong class="ds-profile-amount">'
        "Não disponível</strong><p class=\"ds-profile-note\">Não representa remuneração "
        "zero.</p></div>"
    )
    return (
        '<div class="ds-profile-card ds-profile-pay" aria-labelledby="remuneration-title">'
        '<h3 id="remuneration-title">Remuneração publicada</h3>'
        + body + render_cabinet_cost(profile) + "</div>"
    )
