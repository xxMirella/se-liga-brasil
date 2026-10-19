from datetime import date
from types import SimpleNamespace

import pytest
from test_attendance_profile import attendance_html

from crawlers.camara import attendance, voting_propositions
from crawlers.camara.configuration import API_BASE
from service.ingestion.contracts import IngestionError


def test_attendance_filters_before_exercise_start_and_preserves_unknown_status(
    monkeypatch, tmp_path
):
    source = tmp_path / "presence.html"
    source.write_bytes(attendance_html(status="Não publicado"))
    artifact = SimpleNamespace(path=source)
    acquisition = SimpleNamespace(acquire=lambda *_: artifact)
    monkeypatch.setattr("crawlers.camara.pipeline.ingest_collected", lambda *_: {})
    result = attendance.collect_person_attendance(
        acquisition,
        None,
        {"id": 1},
        "person",
        2026,
        date(2026, 10, 19),
        date(2026, 3, 1),
    )
    assert result["days"] == 0 and result["months"] == 0
    assert attendance.attendance_status("Ausência não justificada") == "unexcused_absence"
    assert attendance.attendance_status("Unknown") == "unknown"


def test_attendance_history_starts_at_2000_and_preserves_unavailable_years(monkeypatch):
    calls = []

    def collect(*args):
        calls.append(args[4])
        if args[4] == 2001:
            raise IngestionError("HTTP_ERROR", {"status": 404})
        return {"months": 0, "days": 0}

    monkeypatch.setattr(attendance, "collect_person_attendance", collect)
    result = attendance.collect_attendance_history(
        None, None, {"attendance_start_year": 1998}, "person"
    )
    assert min(calls) == 2000 and 1999 not in calls
    assert result["failures"] == [{"year": 2001, "code": "HTTP_ERROR"}]


@pytest.mark.parametrize(
    "error",
    [
        IngestionError("SOURCE_COOLDOWN_ACTIVE"),
        IngestionError("HTTP_ERROR", {"status": 403}),
        IngestionError("HTTP_ERROR", {"status": 429}),
    ],
)
def test_attendance_backfill_respects_source_blocks_immediately(monkeypatch, error):
    calls = []

    def collect(*args):
        calls.append(args)
        raise error

    monkeypatch.setattr(attendance, "collect_person_attendance", collect)
    with pytest.raises(IngestionError):
        attendance.collect_attendance_history(None, None, {}, "person")
    assert len(calls) == 1


@pytest.mark.parametrize(
    "payload,code",
    [
        (attendance_html().replace(b"02/02/2026", b"02/02/2027"), "OUTSIDE_PERIOD"),
        (
            attendance_html().replace(
                b"</table>", b"<tr><td>02/02/2026</td><td>Ausente</td></tr></table>"
            ),
            "CONFLICTING_DAY",
        ),
    ],
)
def test_conflicting_or_future_frequency_is_not_ingested(payload, code):
    with pytest.raises(IngestionError, match=code):
        attendance.parse_attendance_days(payload, 2026, date(2026, 10, 19))


def event(key="1-1", day="2026-05-27"):
    return {"id": key, "uri": API_BASE + "votacoes/" + key, "data": day}


def test_scoped_vote_discovery_never_spends_budget_on_unrelated_period_votes(monkeypatch):
    def forbidden(*_):
        raise AssertionError("Explicit proposal scope must not request all Congress votes")

    monkeypatch.setattr(voting_propositions, "discover_votings", forbidden)
    acquisition = SimpleNamespace(
        pages=lambda *_: iter([([event(), event(), event("1-2")], "artifact")])
    )
    rows, evidence, complete = voting_propositions.discover_voting_sources(
        acquisition,
        date(2026, 5, 1),
        date(2026, 5, 31),
        100,
        ("1", "1"),
    )
    assert len(rows) == 2 and evidence == ["artifact"] and complete


def test_targeted_discovery_filters_dates_and_reports_budget_exhaustion():
    acquisition = SimpleNamespace(
        pages=lambda *_: iter(
            [
                (
                    [
                        event("1-0", "2026-04-01"),
                        event(),
                        event("1-2"),
                    ],
                    "artifact",
                )
            ]
        )
    )
    selected = []
    artifacts, complete = voting_propositions.discover_proposition_votings(
        acquisition,
        ("1",),
        date(2026, 5, 1),
        date(2026, 5, 31),
        selected,
        1,
    )
    assert len(selected) == 1 and artifacts == ["artifact"] and not complete


@pytest.mark.parametrize("keys", [("0",), ("abc",), tuple(str(x) for x in range(1, 102))])
def test_invalid_or_unbounded_document_scope_is_rejected(keys):
    with pytest.raises(IngestionError, match="INVALID_PROPOSITION_SCOPE"):
        voting_propositions.discover_proposition_votings(None, keys, None, None, [], 100)


def test_default_voting_discovery_uses_the_period_index(monkeypatch):
    monkeypatch.setattr(voting_propositions, "discover_votings", lambda *_: ([event()], [], True))
    assert voting_propositions.discover_voting_sources(None, None, None, 1)[2]
