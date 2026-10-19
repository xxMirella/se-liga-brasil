"""Generic public HTML verifies truthful labels and escapes untrusted source content."""

from service.public_profile_web.asset_declarations import (
    format_declared_amount,
    render_asset_declarations,
)


def assets_profile():
    return {
        "assets": {
            "declarations": [
                {
                    "election_year": 2022,
                    "recorded_total": "1234.50",
                    "item_count": 1,
                    "source_generated_at": "2022-09-01T00:00:00+00:00",
                    "value_quality_status": "reported",
                    "items": [
                        {
                            "asset_type": "<script>unsafe</script>",
                            "declared_value": "1234.50",
                            "value_quality_status": "reported",
                            "official_url": "https://dadosabertos.tse.jus.br/dataset/bens?a=1&b=2",
                        }
                    ],
                }
            ]
        }
    }


def test_declaration_is_not_presented_as_current_wealth_and_html_is_escaped():
    html = render_asset_declarations(assets_profile())
    assert "Bens declarados · 2022" in html
    assert "R$ 1.234,50" in html
    assert "Soma dos registros disponíveis" in html
    assert "não representam patrimônio atual" in html
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "?a=1&amp;b=2" in html


def test_missing_declarations_never_implies_zero_assets():
    html = render_asset_declarations({})
    assert "ainda não disponíveis" in html
    assert "R$ 0,00" not in html


def test_untrusted_links_are_omitted_and_items_are_bounded():
    profile = assets_profile()
    declaration = profile["assets"]["declarations"][0]
    declaration["items"] = [
        {
            "asset_type": "Item",
            "declared_value": "-1.20",
            "value_quality_status": "negative_requires_review",
            "official_url": "javascript:alert(1)",
        }
    ] * 101
    declaration["items_truncated"] = True
    html = render_asset_declarations(profile)
    assert "javascript:" not in html
    assert html.count("<li>") == 100
    assert "R$ -1,20" in html
    assert "Valor em revisão" in html
    assert "até 100 itens" in html


def test_nonfinite_or_huge_amounts_are_not_rendered():
    assert format_declared_amount("Infinity") == "Não disponível"
    assert format_declared_amount("1e999999") == "Não disponível"
    assert format_declared_amount(None) == "Não disponível"
