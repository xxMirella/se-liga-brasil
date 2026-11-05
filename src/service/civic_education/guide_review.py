"""Step 4 of the civic guide: review questions (reference: Como Funciona v2)."""

from service.public_profile_web.security import text

REVIEW_LEAD = "Pense na resposta antes de abrir. Você não precisa decorar nomes difíceis."
# (question, alternatives, index of the correct alternative, answer text exactly as shown)
REVIEW_QUESTIONS = (
    (
        "Um vereador pode mandar consertar uma rua sozinho?",
        ("Sim", "Não"),
        1,
        "Não. Ele pode cobrar a prefeitura, fiscalizar e propor medidas. A execução da obra "
        "pertence ao Executivo, respeitando as leis e o orçamento.",
    ),
    (
        "Um senador vota leis só para o estado dele?",
        ("Sim", "Não"),
        1,
        "Não. Um senador é eleito por um estado, mas vota leis que podem valer em todo o Brasil.",
    ),
    (
        "O prefeito vota na Câmara Municipal?",
        ("Sim", "Não"),
        1,
        "Não. O prefeito não vota como vereador. Depois da votação dos vereadores, pode "
        "sancionar ou vetar o projeto.",
    ),
)


def render_review_question(question, alternatives, correct_index, answer):
    """One question as a native disclosure; civic-review.js turns it into clickable options."""
    options = "|".join(alternatives)
    return (
        '<details class="ds-disclosure ds-civic-question" data-civic-question '
        f'data-options="{text(options)}" data-correct-index="{correct_index}">'
        f"<summary>{text(question)}</summary>"
        f'<p class="ds-civic-answer">{text(answer)}</p></details>'
    )


def render_review_actions():
    return (
        '<div class="ds-civic-actions">'
        '<a class="ds-button ds-button--primary ds-civic-action" href="/pessoas">'
        "Consultar pessoas por cargo</a>"
        '<button type="button" class="ds-civic-reset" data-civic-reset hidden>'
        "Recomeçar o guia</button></div>"
    )


def render_practice():
    questions = "".join(render_review_question(*question) for question in REVIEW_QUESTIONS)
    return (
        '<section class="ds-section ds-civic-review" id="pratique" data-civic-review>'
        '<span class="ds-civic-step-label">Passo 4 de 4</span>'
        '<h2 class="ds-heading ds-heading--section">Vamos ver se ficou claro?</h2>'
        f'<p class="ds-civic-lead" data-civic-lead aria-live="polite">{REVIEW_LEAD}</p>'
        f'<div class="ds-civic-questions">{questions}</div>'
        f"{render_review_actions()}</section>"
    )


# page.py still imports the original name.
