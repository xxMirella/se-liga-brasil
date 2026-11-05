from application.political_party_options import load_party_options
from service.public_profile_web.search import render_search_filters

PARTIES = (("MDB", "Movimento Democrático Brasileiro"), ("PT", "Partido dos Trabalhadores"))


def test_party_filter_lists_existing_parties_in_a_wrapped_select():
    html = render_search_filters({}, PARTIES)

    assert '<label class="ds-people-field">Partido<select class="ds-people-select"' in html
    assert '<option value="">Todos os partidos</option>' in html
    assert '<option value="PT">PT · Partido dos Trabalhadores</option>' in html
    assert 'name="political_party" value=' not in html


def test_selected_party_is_marked_case_insensitively():
    html = render_search_filters({"political_party": "pt"}, PARTIES)

    assert '<option value="PT" selected>' in html


def test_unknown_party_from_the_url_is_kept_so_the_filter_stays_visible():
    html = render_search_filters({"political_party": "xyz"}, PARTIES)

    assert '<option value="XYZ" selected>XYZ</option>' in html


def test_without_a_party_list_the_filter_falls_back_to_a_text_field():
    html = render_search_filters({"political_party": "PT"}, ())

    assert 'name="political_party" value="PT"' in html
    assert "<select class=\"ds-people-select\" name=\"political_party\"" not in html


def test_party_options_are_read_through_the_repository(monkeypatch):
    class FakeConnections:
        def read(self, operation):
            class Connection:
                def execute(self, *_):
                    class Result:
                        def fetchall(self):
                            return [{"abbreviation": "PT", "name": "Partido dos Trabalhadores"}]
                    return Result()
            return operation(Connection())

    assert load_party_options(FakeConnections(), None) == (("PT", "Partido dos Trabalhadores"),)


def test_party_caption_does_not_repeat_a_name_equal_to_the_abbreviation():
    html = render_search_filters({}, (("AVANTE", "AVANTE"), ("PT", "Partido dos Trabalhadores")))

    assert '<option value="AVANTE">AVANTE</option>' in html
    assert "AVANTE · AVANTE" not in html
