"""Four-card summary of the profile, each card linking to the section that explains it."""

from itertools import islice

from service.public_profile_web.profile_dates import format_month_year, format_reais
from service.public_profile_web.security import text

LAW_PROPOSAL_KINDS = frozenset({"PL", "PLP", "PEC", "PDL"})
UNAVAILABLE = "Não disponível"


def render_summary_card(anchor, label, value, detail):
    return (
        f'<a class="ds-profile-summary__card" href="#{anchor}"><span>{label}</span>'
        f"<strong>{value}</strong><span>{detail}</span></a>"
    )


def attendance_card(profile):
    months = list(islice(profile.get("attendance_history") or [], 600))
    required = sum(int(month.get("required") or 0) for month in months)
    if not required:
        return render_summary_card(
            "presenca", "Presença no mandato", UNAVAILABLE,
            "sem frequência consolidada na fonte",
        )
    present = sum(int(month.get("present") or 0) for month in months)
    first = format_month_year(months[0].get("period"))
    last = format_month_year(months[-1].get("period"))
    return render_summary_card(
        "presenca", "Presença no mandato", f"{present} de {required} dias",
        f"com sessões deliberativas, {text(first)} a {text(last)}",
    )


def proposal_period(items):
    months = sorted(
        format_key
        for item in items
        if (format_key := (item.get("occurred_on") or "")[:7]) and format_month_year(format_key)
    )
    if not months:
        return "na amostra"
    first, last = format_month_year(months[0]), format_month_year(months[-1])
    if first[3:] == last[3:]:
        first = first[:3]
    return f"entre {first} e {last}, na amostra"


def proposals_card(profile):
    items = list(islice((profile.get("propositions") or {}).get("items") or [], 1000))
    if not items:
        return render_summary_card(
            "atuacao", "Propostas de lei", UNAVAILABLE,
            "sem registros na fonte consultada. Apresentar não é aprovar.",
        )
    laws = [item for item in items if item.get("kind") in LAW_PROPOSAL_KINDS]
    return render_summary_card(
        "atuacao", "Propostas de lei", f"{len(laws)} apresentadas",
        f"{proposal_period(items)}. Apresentar não é aprovar.",
    )


def payment_card(profile):
    payment = next(iter(profile.get("payments") or []), None) or {}
    amount = format_reais(payment.get("gross_amount"))
    if amount is None:
        return render_summary_card(
            "bens", "Remuneração publicada", UNAVAILABLE, "não representa remuneração zero"
        )
    month = format_month_year(payment.get("competence"))
    return render_summary_card(
        "bens", "Remuneração publicada", amount,
        f"bruto, referente a {text(month, 'competência não informada')}",
    )


def assets_card(profile):
    declarations = (profile.get("assets") or {}).get("declarations") or []
    latest = max(
        islice(declarations, 100), key=lambda item: str(item.get("election_year")), default=None
    )
    amount = format_reais((latest or {}).get("recorded_total"))
    if amount is None:
        return render_summary_card(
            "bens", "Bens declarados", UNAVAILABLE,
            "declarações à Justiça Eleitoral ainda não disponíveis",
        )
    return render_summary_card(
        "bens", f"Bens declarados em {text(latest.get('election_year'))}", amount,
        "à Justiça Eleitoral; não é o patrimônio atual",
    )


def render_cabinet_gap_note(profile):
    cabinet = profile.get("cabinet_payroll") or {}
    if cabinet.get("latest") or cabinet.get("months"):
        return ""
    return (
        '<p class="ds-profile-summary-note"><strong>Ainda não coletado:</strong> gastos com '
        "gabinete. Isso não significa gasto zero.</p>"
    )


def render_profile_summary(profile):
    cards = attendance_card(profile) + proposals_card(profile)
    cards += payment_card(profile) + assets_card(profile)
    return (
        f'<section class="ds-profile-summary" aria-label="Resumo">{cards}</section>'
        + render_cabinet_gap_note(profile)
    )
