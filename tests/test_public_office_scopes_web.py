"""Public office powers preserve evidence boundaries and safe links."""

from service.public_profile_web.office_scopes import render_office_scopes


def test_legal_scope_preserves_limits_and_rejects_untrusted_links():
    scopes = [
        {
            "office_kind": "governor",
            "jurisdiction": "SP",
            "competencies": [
                {
                    "title": "<script>bad</script>",
                    "description": "Ato administrativo",
                    "scope": "individual",
                }
            ],
            "restrictions": [{"title": "Restrições", "description": "Reserva legal"}],
            "sources": [
                {"url": "javascript:bad", "title": "bad"},
                {"url": "https://www.planalto.gov.br/texto", "title": "Constituição"},
            ],
            "limitations": ["A norma local ainda requer revisão."],
        }
    ]
    markup = render_office_scopes(
        {
            "legal_scopes": scopes,
            "current_offices": [{"office_kind": "governor", "represented_uf": "SP"}],
        }
    )
    assert "Governador(a)" in markup
    assert "Aplicação individual" in markup
    assert "Competência do órgão" in markup
    assert "A norma local ainda requer revisão." in markup
    assert "&lt;script&gt;" in markup
    assert "<script>" not in markup
    assert "javascript:" not in markup
    assert 'href="https://www.planalto.gov.br/texto"' in markup


def test_missing_scope_is_explicit_not_invented():
    markup = render_office_scopes({})
    assert "ainda não está disponível" in markup


def test_default_only_shows_current_office_not_past_candidacies():
    profile = {
        "legal_scopes": [
            {"office_kind": "federal_deputy", "jurisdiction": "BR"},
            {"office_kind": "councillor", "jurisdiction": "BR"},
        ],
        "current_offices": [{"office_kind": "federal_deputy"}],
    }
    markup = render_office_scopes(profile)
    assert "Deputado(a) federal" in markup
    assert "Vereador(a)" not in markup
    votes = {"exercises": [{"exercise_id": 7, "office_kind": "councillor"}]}
    historical = render_office_scopes(profile, votes, {"exercise_id": "7"})
    assert "Vereador(a)" in historical
    assert "Deputado(a) federal" not in historical


def test_other_state_and_unconfirmed_offices_are_never_displayed():
    profile = {
        "legal_scopes": [
            {"office_kind": "state_deputy", "jurisdiction": "SP"},
            {"office_kind": "state_deputy", "jurisdiction": "RJ"},
        ],
        "current_offices": [{"office_kind": "state_deputy", "represented_uf": "RJ"}],
    }
    markup = render_office_scopes(profile)
    assert "estadual · RJ" in markup
    assert "estadual · SP" not in markup
    profile["current_offices"] = []
    assert "ainda não está disponível" in render_office_scopes(profile)
