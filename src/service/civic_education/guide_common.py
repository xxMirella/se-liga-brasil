"""Shared pieces of the civic guide: spheres and source links."""


from service.public_profile_web.security import text

SPHERES = {"municipal": "Cidade", "estadual": "Estado", "federal": "País", "distrital": "DF"}


def source_link(source, reference=""):
    title, url = source
    suffix = " · " + reference if reference else ""
    return (
        f'<a href="{text(url)}" target="_blank" rel="noopener noreferrer">'
        f"{text(title + suffix)}</a>"
    )


def render_choice_check(check_id, question, options):
    """A question answered without script: radios reveal feedback through `:checked` siblings.

    `options` is a sequence of (label, is_correct, feedback_title, feedback_text).
    """
    name = f"check-{check_id}"
    inputs = "".join(
        f'<input class="ds-civic-quiz__input" type="radio" name="{name}" id="{name}-{index}"'
        f' data-option="{index}">'
        for index, _ in enumerate(options)
    )
    labels = "".join(
        f'<label class="ds-civic-quiz__option" for="{name}-{index}" data-option="{index}"'
        f' data-correct="{str(correct).lower()}">{text(label)}</label>'
        for index, (label, correct, _, _) in enumerate(options)
    )
    feedback = "".join(
        f'<div class="ds-civic-quiz__feedback" role="status" data-option="{index}"'
        f' data-correct="{str(correct).lower()}"><strong>{text(title)}</strong> {text(body)}</div>'
        for index, (_, correct, title, body) in enumerate(options)
    )
    return f"""<div class="ds-civic-quiz" role="group" aria-labelledby="{name}-question">
<span class="ds-civic-quiz__eyebrow">Checagem · pense antes de escolher</span>
<p class="ds-civic-quiz__question" id="{name}-question">{text(question)}</p>
{inputs}<div class="ds-civic-quiz__options">{labels}</div>{feedback}</div>"""
