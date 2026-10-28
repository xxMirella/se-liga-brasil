from service.political_dashboard.orientation_glossary import (
    GLOSSARY_ENTRIES,
    render_orientation_glossary,
)


def test_glossary_is_visible_only_for_political_orientation_and_has_seven_sourced_terms():
    assert render_orientation_glossary({"view": "political_party"}) == ""
    rendered = render_orientation_glossary({"view": "political_orientation"})
    assert rendered.count('<dt>') == 7
    assert rendered.count('target="_blank"') == 7
    for entry in GLOSSARY_ENTRIES:
        assert entry["term"] in rendered
        assert entry["source_url"] in rendered
    assert "não alteram as três faixas" in rendered
    assert "fascista ou ditatorial" in rendered


def test_glossary_escapes_definitions_and_source_attributes():
    from service.political_dashboard.orientation_glossary import render_glossary_entry

    rendered = render_glossary_entry({
        "term": "<script>", "definition": "<b>texto</b>",
        "source_url": 'https://example.org/" onmouseover="alert(1)',
    })
    assert '<script>' not in rendered
    assert '<b>' not in rendered
    assert '&lt;script&gt;' in rendered
    assert 'href="https://example.org/&quot;' in rendered
