"""The fixed political party palette keeps colors tied to names, not to ranking."""

from service.political_dashboard.political_palette import UNKNOWN_COLOR, political_party_color


def test_party_palette_is_fixed_by_name_not_rank_and_matches_mock():
    assert political_party_color("PSD") == "#236049"
    assert political_party_color("PL") == "#56866c"
    assert political_party_color("MDB") == political_party_color("PMDB") == "#aaa24d"
    assert political_party_color("União") == political_party_color("UNIÃO BRASIL") == "#678798"
    assert political_party_color("Filiação histórica não verificada") == UNKNOWN_COLOR
    assert political_party_color("PRP") == political_party_color("PRP")
