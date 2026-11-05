"""GET controls preserve only explicit public filters."""

from itertools import islice

from service.public_profile.contracts import OFFICE_KINDS
from service.public_profile_web.profile import OFFICE_LABELS
from service.public_profile_web.security import text
from web_components import render_disclosure


def render_select(name, label, options, selected):
    choices = ['<option value="">Todos</option>']
    for value, caption in options:
        marker = " selected" if str(value) == str(selected) else ""
        choices.append(f'<option value="{text(value)}"{marker}>{text(caption)}</option>')
    return f'<label>{label}<select name="{name}">' + "".join(choices) + "</select></label>"


def render_select_element(name, options, selected, *, empty_caption, css_class, label_text=""):
    """Bare <select> for the people search; the caller supplies the accessible name."""
    choices = [f'<option value="">{text(empty_caption)}</option>']
    for value, caption in options:
        marker = " selected" if str(value) == str(selected) else ""
        choices.append(f'<option value="{text(value)}"{marker}>{text(caption)}</option>')
    aria = f' aria-label="{text(label_text)}"' if label_text else ""
    return (
        f'<select class="{css_class}" name="{name}"{aria}>'
        + "".join(choices) + "</select>"
    )


def render_radio_pills(name, legend, options, selected):
    """Single-choice pills backed by native radio inputs (no script needed)."""
    chosen = str(selected or "")
    pills = []
    for value, caption in (("", "Todos"), *options):
        checked = " checked" if str(value) == chosen else ""
        pills.append(
            f'<label class="ds-people-pill"><input type="radio" name="{name}" '
            f'value="{text(value, "")}"{checked}><span>{text(caption)}</span></label>'
        )
    return (
        f'<fieldset class="ds-people-field"><legend>{text(legend)}</legend>'
        f'<div class="ds-people-pills">{"".join(pills)}</div></fieldset>'
    )


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
    form = f'''<form class="activity-controls" action="{path}" method="get">
<input type="hidden" name="tab" value="activity">
<input type="hidden" name="scope" value="period">
<label>De<input name="start_date" type="date" required value="{
        text(filters.get("start_date"), "")
    }"></label>
<label>Até<input name="end_date" type="date" required value="{
        text(filters.get("end_date"), "")
    }"></label>
{offices}{exercise_control}<button type="submit">Aplicar filtros</button></form>'''
    return render_disclosure("Filtrar votações", form)
