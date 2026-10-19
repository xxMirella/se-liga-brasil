from service.public_profile_web.asset_declarations import render_asset_declarations
from service.public_profile_web.vote_groups import proposition_group_key
from service.public_profile_web.votes import render_votes_timeline


def voting(day="2026-05-27", choice="yes", number="1", institution="camara"):
    return {"voting_id": day + choice, "occurred_on": day, "date_precision": "day",
            "proposition": {"kind": "PEC", "number": number, "year": 2025,
                            "title": f"PEC {number}/2025"},
            "individual": {"participation_status": "voted", "choice": choice},
            "institution": {"code": institution, "name": institution},
            "subject": "Emenda em votação"}


def test_same_proposal_in_same_month_has_one_card_and_keeps_opposing_votes():
    html = render_votes_timeline({"items": [voting(), voting("2026-05-28", "no")]})
    assert html.count('class="timeline-event monthly-proposition"') == 1
    assert html.count('class="voting-history-entry"') == 2
    assert "2026-05-27" in html and "2026-05-28" in html
    assert "Sim · a favor" in html and "Não · contra" in html
    assert "Emenda em votação" in html
    assert 'command="show-modal"' in html


def test_months_and_different_proposals_never_collapse_together():
    html = render_votes_timeline({"items": [voting(), voting("2026-04-10"), voting(number="2")]})
    assert html.count('class="timeline-event monthly-proposition"') == 3
    assert html.count('<dialog id="voting-history-') == 3


def test_institutions_disambiguate_equal_numbers_and_years():
    assert proposition_group_key(voting()) != proposition_group_key(voting(institution="senado"))


def test_unidentified_matters_do_not_collapse_into_a_fake_proposal():
    first = {"voting_id": "a"}
    second = {"voting_id": "b"}
    assert proposition_group_key(first) != proposition_group_key(second)


def test_declarations_never_use_file_generation_as_month_of_submission():
    html = render_asset_declarations({"assets": {"declarations": [{
        "election_year": 2022, "source_generated_at": "2026-10-19T00:00:00",
        "recorded_total": "10", "items": [],
    }]}})
    assert 'class="timeline-event"' in html
    assert "Mês não informado" in html
    assert "Outubro" not in html
