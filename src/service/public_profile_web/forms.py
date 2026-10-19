"""GET controls preserve only explicit public filters."""

from itertools import islice

from service.public_profile.contracts import OFFICE_KINDS
from service.public_profile_web.profile import OFFICE_LABELS
from service.public_profile_web.security import text


def render_select(name, label, options, selected):
    choices = ['<option value="">Todos</option>']
    for value, caption in options:
        marker = " selected" if str(value) == str(selected) else ""
        choices.append(f'<option value="{text(value)}"{marker}>{text(caption)}</option>')
    return f'<label>{label}<select name="{name}">' + "".join(choices) + "</select></label>"


def render_vote_filters(path, votes, filters):
    exercises = islice(votes.get("exercises", []), 100)
    options = []
    for exercise in exercises:
        office = OFFICE_LABELS.get(exercise.get("office_kind"), "Cargo público")
        institution = (exercise.get("institution") or {}).get("name") or "Órgão não disponível"
        caption = (
            f"{office} · {institution} · {exercise.get('starts_on') or 'Início não confirmado'}"
        )
        options.append((exercise["exercise_id"], caption))
    offices = render_select(
        "office_kind",
        "Cargo",
        ((key, label) for key, label in OFFICE_LABELS.items() if key in OFFICE_KINDS),
        filters.get("office_kind"),
    )
    exercise_control = render_select(
        "exercise_id", "Exercício", options, filters.get("exercise_id")
    )
    return f'''<details class="activity-filters"><summary>Filtrar votações</summary>
<form class="activity-controls" action="{path}" method="get">
<input type="hidden" name="tab" value="activity">
<input type="hidden" name="scope" value="period">
<label>De<input name="start_date" type="date" required value="{
        text(filters.get("start_date"), "")
    }"></label>
<label>Até<input name="end_date" type="date" required value="{
        text(filters.get("end_date"), "")
    }"></label>
{offices}{exercise_control}<button type="submit">Aplicar filtros</button></form></details>'''
