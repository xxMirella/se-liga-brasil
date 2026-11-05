"""Adapter over the dashboard payload, with a fictional payload (no database)."""

from datetime import date

from application.majority_panorama_reader import MajorityPanoramaReader

TODAY = date(2026, 11, 3)


def fake_dashboard(parameters):
    year = int(parameters["year"])
    segment = {
        "exercise_id": "arquivo-nacional-president:204:2023-01-01",
        "person_id": "arquivo-nacional-president:204", "starts_on": "2023-01-01",
        "ends_before": None, "political_party": "PT", "name": "Lula Fictício",
        "official_url": "https://exemplo.invalid/lula",
    }
    history = [{"year": 2026, "institutions": [
        {"institution_code": "senado", "territory_code": "BR", "total": 81,
         "snapshot_on": "2026-10-22", "political_parties": [{"abbreviation": "PT", "count": 81}]},
        {"institution_code": "presidency", "territory_code": "BR", "segments": [segment]},
    ]}]
    return {"year": year, "history": history, "presidency": {"segments": [segment]}}


def test_reader_builds_panorama_from_dashboard_history():
    panorama = MajorityPanoramaReader(fake_dashboard, lambda: TODAY).fetch()
    current = panorama.legislatures[-1]
    assert current.senado.seats("left") == 81
    assert current.camara is None
    assert panorama.presidents[0].full_name == "Lula Fictício"
    assert panorama.presidents[0].source_url == "https://exemplo.invalid/lula"
