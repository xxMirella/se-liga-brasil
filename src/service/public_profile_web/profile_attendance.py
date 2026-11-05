"""Plenary attendance of the profile person and its monthly history dialog."""

from service.public_profile_web.profile_metric import render_metric
from service.public_profile_web.security import official_url, text
from web_components import render_disclosure
from web_components.column_chart import percent_height_classes


def render_attendance(profile):
    attendance = profile.get("attendance") or {}
    months = profile.get("attendance_history", [])
    action = (
        '<button class="attendance-history-button" commandfor="attendance-history" '
        'command="show-modal">Ver histórico</button>'
        if months
        else ""
    )
    percentage = attendance.get("percentage")
    if percentage is None:
        return render_metric(
            "Presença", "Não disponível", "Sem frequência atual consolidada", action
        ) + render_attendance_history(months)
    value = text(str(percentage).replace(".", ",")) + "%"
    reference = (
        f"{text(attendance.get('period'))} · {text(attendance.get('present'))} de "
        f"{text(attendance.get('required'))} dias com sessões deliberativas"
    )
    return render_metric(
        "Presença em plenário", value, reference, action
    ) + render_attendance_history(months)


def render_attendance_history(months):
    if not months:
        return ""
    items = []
    for month in reversed(months):
        percentage = month.get("percentage")
        value = str(percentage).replace(".", ",") + "%" if percentage else "Não disponível"
        partial = " · parcial" if month.get("partial") else ""
        source = official_url(month.get("sourceUrl"))
        link = (
            f' · <a href="{text(source)}" target="_blank" rel="noopener noreferrer">'
            'Fonte oficial</a>'
            if source else ""
        )
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
        "<p>Presença em dias com sessões deliberativas da Câmara dos Deputados. "
        "Meses sem dados não "
        "significam falta nem frequência completa.</p><ul>"
        + "".join(items)
        + "</ul></div></dialog>"
    )


MONTH_ABBREVIATIONS = (
    "jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez",
)
MONTH_NAMES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
    "setembro", "outubro", "novembro", "dezembro",
)


def parse_month(month):
    """Return (year, month_number) of a history row, or None when its period is malformed."""
    period = str(month.get("period") or "")
    if len(period) != 7 or period[4] != "-" or not (period[:4] + period[5:]).isdigit():
        return None
    number = int(period[5:])
    return (int(period[:4]), number) if 1 <= number <= 12 else None


def group_months_by_year(months):
    years = {}
    for month in months:
        parsed = parse_month(month)
        if parsed and month.get("required"):
            years.setdefault(parsed[0], {})[parsed[1]] = month
    return dict(sorted(years.items()))


def describe_month(month_number, month):
    present, required = month.get("present"), month.get("required")
    percentage = month.get("percentage")
    official = (
        f"percentual oficial {text(str(percentage).replace('.', ','))}%"
        if percentage is not None else "sem percentual oficial"
    )
    partial = ", mês parcial" if month.get("partial") else ""
    return (
        f"{MONTH_NAMES[month_number - 1]}: {text(present)} de {text(required)} dias, "
        f"{official}{partial}"
    )


def render_attendance_month(month_number, month):
    if month is None:
        return (
            '<li class="ds-profile-month ds-profile-month--empty">'
            '<span class="ds-profile-month__value" aria-hidden="true">–</span>'
            '<span class="ds-profile-month__track"></span>'
            f'<span class="ds-visually-hidden">{MONTH_NAMES[month_number - 1]}: '
            "sem sessões ou sem dados</span></li>"
        )
    official = month.get("percentage") is not None
    fill = percent_height_classes(100 * month["present"] / month["required"])
    kind = "official" if official else "unofficial"
    return (
        f'<li class="ds-profile-month"><span class="ds-profile-month__value" aria-hidden="true">'
        f'{text(month["present"])}<span class="ds-profile-month__required">/'
        f'{text(month["required"])}</span></span>'
        f'<span class="ds-profile-month__track" aria-hidden="true">'
        f'<span class="ds-profile-month__fill ds-profile-month__fill--{kind} {fill}"></span>'
        f'</span><span class="ds-visually-hidden">{describe_month(month_number, month)}'
        f"</span></li>"
    )


def render_month_axis():
    labels = "".join(
        f'<span class="ds-profile-axis__label">{name}</span>' for name in MONTH_ABBREVIATIONS
    )
    return f'<div class="ds-profile-axis" aria-hidden="true">{labels}</div>'


def render_attendance_legend():
    items = (
        ("official", "presença com percentual oficial"),
        ("unofficial", "dias registrados, sem percentual oficial"),
        ("empty", "sem sessões ou sem dados"),
    )
    return '<div class="ds-profile-legend">' + "".join(
        f'<span class="ds-profile-legend__item"><span class="ds-profile-legend__swatch '
        f'ds-profile-legend__swatch--{kind}"></span>{label}</span>'
        for kind, label in items
    ) + "</div>"


def render_year_summary(year, year_months):
    rows = list(year_months.values())
    present = sum(row["present"] for row in rows)
    required = sum(row["required"] for row in rows)
    without_percentage = sum(1 for row in rows if row.get("percentage") is None)
    summary = f"Em {year}, presença registrada em {present} de {required} dias com sessão."
    if without_percentage:
        noun = "mês" if without_percentage == 1 else "meses"
        summary += f" Em {without_percentage} {noun}, a fonte não publicou o percentual oficial."
    else:
        summary += " Todos os meses com percentual oficial."
    partial = [number for number, row in year_months.items() if row.get("partial")]
    if partial:
        summary += f" {MONTH_NAMES[max(partial) - 1].capitalize()} ainda é parcial."
    return summary


def render_year_panel(year, year_months, selected):
    identifier = f"attendance-year-{year}"
    checked = " checked" if selected else ""
    months = "".join(
        render_attendance_month(number, year_months.get(number)) for number in range(1, 13)
    )
    return (
        f'<input class="ds-profile-years__input ds-visually-hidden" type="radio" '
        f'name="attendance-year" id="{identifier}" value="{year}"{checked}>'
        f'<label class="ds-profile-years__label" for="{identifier}">{year}</label>'
        f'<p class="ds-profile-attendance__summary">{text(render_year_summary(year, year_months))}'
        "</p>"
        f'<div class="ds-profile-chart"><ol class="ds-profile-months">{months}</ol>'
        f"{render_month_axis()}{render_attendance_legend()}</div>"
    )


def render_attendance_reading(months):
    link = ""
    for month in reversed(months):
        source = official_url(month.get("sourceUrl"))
        if source:
            link = (
                f' <a href="{text(source)}" target="_blank" rel="noopener noreferrer">'
                "Fonte oficial ↗</a>"
            )
            break
    body = (
        "<p>Contamos só os dias com sessões deliberativas da Câmara. Em alguns meses, a fonte "
        "informa os dias com presença registrada, mas não publica o percentual oficial; "
        "mostramos esses meses listrados. Meses sem dados não significam falta nem "
        f"frequência completa.{link}</p>"
    )
    return render_disclosure("Como ler a presença", body)


def render_attendance_section(profile):
    months = profile.get("attendance_history") or []
    years = group_months_by_year(months)
    heading = '<h2 id="presenca-title" class="ds-profile-heading">Presença em plenário</h2>'
    if not years:
        body = (
            '<p class="ds-profile-attendance__summary">Sem frequência consolidada para esta '
            "pessoa. Ausência de dados não significa falta nem frequência completa.</p>"
        )
        return _wrap_attendance_section(heading + body)
    latest = max(years)
    panels = "".join(
        render_year_panel(year, year_months, year == latest)
        for year, year_months in years.items()
    )
    selector = (
        '<fieldset class="ds-profile-years"><legend class="ds-visually-hidden">Ano</legend>'
        f"{panels}</fieldset>"
    )
    return _wrap_attendance_section(heading + selector + render_attendance_reading(months))


def _wrap_attendance_section(content):
    return (
        '<section id="presenca" class="ds-profile-attendance" '
        f'aria-labelledby="presenca-title">{content}</section>'
    )
