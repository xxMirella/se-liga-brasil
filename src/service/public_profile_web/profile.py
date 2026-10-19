"""Public header: temporal evidence remains separate from electoral declarations."""

from itertools import islice

from service.public_profile_web.security import official_url, text

OFFICE_LABELS = {
    "federal_deputy": "Deputado(a) federal",
    "state_deputy": "Deputado(a) estadual",
    "district_deputy": "Deputado(a) distrital",
    "senator": "Senador(a)",
    "councillor": "Vereador(a)",
    "mayor": "Prefeito(a)",
    "vice_mayor": "Vice-prefeito(a)",
    "governor": "Governador(a)",
    "vice_governor": "Vice-governador(a)",
    "senator_substitute": "Suplente de senador(a)",
    "other": "Outro cargo público",
}
def render_portrait(profile):
    photo = profile.get("photo") or {}
    url = official_url(photo.get("url"))
    if url:
        portrait = (
            f'<img src="{text(url)}" alt="Foto institucional de '
            f'{text(profile.get("display_name"))}" referrerpolicy="no-referrer">'
        )
    else:
        portrait = (
            '<div class="portrait-placeholder" role="img" aria-label="Foto não '
            'disponível"><span aria-hidden="true">◯</span></div>'
        )
    attribution = text(
        photo.get("attribution"), "Foto institucional" if url else "Foto não disponível"
    )
    return f'<div class="portrait">{portrait}<small>{attribution}</small></div>'


def render_political_party(profile):
    political_party = profile.get("political_party") or {}
    abbreviation = political_party.get("abbreviation")
    name = political_party.get("name") or abbreviation
    return f"""<div class="affiliation"><span class="party-icon">{text(abbreviation, "—")}</span>
<div><strong>{text(name, "Partido não disponível")}</strong></div></div>"""


def render_observed_office(status):
    if status.get("office_kind"):
        label = OFFICE_LABELS.get(status["office_kind"], "Cargo público")
        institution = (status.get("institution") or {}).get("name")
        reference = text(status.get("observed_on"))
        return (
            f'<p class="role">{label} · {text(institution)}<br>'
            f"Cargo observado em {reference}; exercício atual não confirmado.</p>"
        )
    label = "Sem cargo público atual confirmado"
    if status.get("has_current_public_office") is False and status.get("status") == "observed":
        label = "Não ocupa cargo público atual, segundo a evidência disponível"
    return f'<p class="role">{label}</p>'


def render_offices(profile):
    offices = list(islice(profile.get("current_offices", []), 20))
    if not offices:
        return render_observed_office(profile.get("public_office") or {})
    labels = []
    for office in offices:
        label = OFFICE_LABELS.get(office.get("office_kind"), "Cargo público")
        institution = (office.get("institution") or {}).get("name")
        labels.append(f"{label} · {text(institution)}")
    return '<p class="role">' + "<br>".join(labels) + "</p>"


def render_metric(label, value, reference, action=""):
    return (
        f"<div "
        f'class="metric"><span>{label}</span><strong>{value}</strong>{action}'
        f'<small>{reference}</small></div>'
    )


def render_tenures(profile):
    offices = list(islice(profile.get("current_offices", []), 20))
    metrics = []
    for office in offices:
        tenure = office.get("tenure") or {}
        value = "Início não confirmado"
        if tenure.get("years") is not None and tenure.get("months") is not None:
            value = f"{text(tenure['years'])} anos e {text(tenure['months'])} meses"
        institution = (office.get("institution") or {}).get("name")
        metrics.append(render_metric("Tempo no exercício atual", value, text(institution)))
    return "".join(metrics) or render_metric(
        "Tempo no exercício", "Não disponível", "Início individual não confirmado"
    )


def render_payments(profile):
    payments = list(islice(profile.get("payments", []), 20))
    if not payments:
        return render_metric("Remuneração", "Não disponível", "Não representa remuneração zero")
    metrics = []
    for payment in payments:
        gross = payment.get("gross_amount")
        value = f"R$ {text(gross)}" if gross is not None else "Não disponível"
        reference = (
            f"Bruto · Competência {text(payment.get('competence'))} · "
            f"{text(payment.get('organization_code'))}"
        )
        freshness = payment.get("freshness")
        if freshness != "current_competence":
            reference += " · Última publicação disponível; não confirma o mês atual"
        metrics.append(render_metric("Remuneração publicada", value, reference))
    return "".join(metrics)


def render_profile_header(profile):
    age = (profile.get("age") or {}).get("value")
    age_value = f"{text(age)} anos" if age is not None else "Não disponível"
    metrics = render_metric("Idade", age_value, f"Referência {text(profile.get('as_of'))}")
    metrics += render_metric(
        "Escolaridade", text(profile.get("education_level")), "Declarada na fonte"
    )
    metrics += render_tenures(profile) + render_attendance(profile) + render_payments(profile)
    return f"""<section class="profile" aria-label="Identificação pública">
{render_portrait(profile)}<div class="profile-info"><p class="eyebrow">PERFIL PÚBLICO</p>
<h1>{text(profile.get("display_name"))}</h1>{render_offices(profile)}
{render_political_party(profile)}</div></section><div class="metrics">{metrics}</div>"""


def render_attendance(profile):
    attendance = profile.get("attendance") or {}
    months = profile.get("attendance_history", [])
    action = (
        '<button class="attendance-history-button" commandfor="attendance-history" '
        'command="show-modal">Ver histórico</button>' if months else ""
    )
    percentage = attendance.get("percentage")
    if percentage is None:
        return (
            render_metric("Presença", "Não disponível", "Sem frequência atual consolidada", action)
            + render_attendance_history(months)
        )
    value = text(str(percentage).replace(".", ",")) + "%"
    reference = (
        f"{text(attendance.get('period'))} · {text(attendance.get('present'))} de "
        f"{text(attendance.get('required'))} dias com sessões deliberativas"
    )
    return (
        render_metric("Presença em plenário", value, reference, action)
        + render_attendance_history(months)
    )


def render_attendance_history(months):
    if not months:
        return ""
    items = []
    for month in reversed(months):
        percentage = month.get("percentage")
        value = str(percentage).replace(".", ",") + "%" if percentage else "Não disponível"
        partial = " · parcial" if month.get("partial") else ""
        source = official_url(month.get("sourceUrl"))
        link = f' · <a href="{text(source)}">Fonte oficial</a>' if source else ""
        items.append(
            f"<li>{text(month.get('period'))}: {text(value)} · "
            f"{text(month.get('present'))} de {text(month.get('required'))} dias{partial}"
            f"{link}</li>"
        )
    return (
        '<dialog id="attendance-history" class="attendance-dialog" '
        'aria-labelledby="attendance-history-title">'
        '<header><h2 id="attendance-history-title">Histórico mensal de presença</h2>'
        '<form method="dialog"><button autofocus aria-label="Fechar histórico">'
        'Fechar</button></form></header><div class="attendance-dialog-content">'
        '<p>Presença em dias com sessões deliberativas da Câmara dos Deputados. '
        'Meses sem dados não '
        'significam falta nem frequência completa.</p><ul>'
        + "".join(items) + "</ul></div></dialog>"
    )
