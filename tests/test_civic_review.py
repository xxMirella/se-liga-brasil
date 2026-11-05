from service.civic_education.guide_review import REVIEW_QUESTIONS, render_practice


def test_review_questions_have_one_correct_alternative_and_an_explanation():
    for question, alternatives, correct_index, answer in REVIEW_QUESTIONS:
        assert question.endswith("?") and answer.startswith(alternatives[correct_index] + ".")
        assert 0 <= correct_index < len(alternatives)
        assert len(set(alternatives)) == len(alternatives)


def test_review_answers_stay_legally_correct():
    answers = {q: (alts[i], e) for q, alts, i, e in REVIEW_QUESTIONS}
    assert answers["Um vereador pode mandar consertar uma rua sozinho?"][0] == "Não"
    assert answers["Um senador vota leis só para o estado dele?"][0] == "Não"
    assert answers["O prefeito vota na Câmara Municipal?"][0] == "Não"
    assert "sancionar ou vetar" in answers["O prefeito vota na Câmara Municipal?"][1]


def test_review_works_without_javascript_and_matches_the_reference_text():
    html = render_practice()

    assert html.count('<details class="ds-disclosure ds-civic-question"') == len(REVIEW_QUESTIONS)
    assert html.count('data-correct-index="1"') == len(REVIEW_QUESTIONS)
    assert html.count('<p class="ds-civic-answer">Não. ') == len(REVIEW_QUESTIONS)
    assert "<script" not in html and "style=" not in html
    assert 'id="pratique"' in html and "Passo 4 de 4" in html
    assert "hidden>" in html  # the reset button only appears once the script runs


def test_review_has_no_glossary_block():
    html = render_practice()
    assert "Palavras que aparecem no caminho" not in html and 'id="palavras"' not in html
    assert "Ver todas as palavras do guia" not in html
