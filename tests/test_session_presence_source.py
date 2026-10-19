"""Presence evidence is dated, scoped and never inferred from a missing vote."""

from datetime import date
from types import SimpleNamespace

import pytest

from crawlers.camara.session_presence import (
    parse_daily_session_presence,
    parse_official_xml,
    parse_presence_roster,
    presence_state,
)
from service.attendance.session_presence import (
    canonical_presence_records,
    collect_daily_presence,
    publish_daily_presence,
)
from service.ingestion.contracts import IngestionError

DAY = date(2026, 5, 27)
PERSON = "00000000-0000-0000-0000-000000000001"


def roster_xml():
    return b"""<deputados><deputado><matricula>10</matricula><ideCadastro>1</ideCadastro>
    <nomeParlamentar>Pessoa Teste</nomeParlamentar><uf>SP</uf></deputado></deputados>"""


def presence_xml(status="Presença", card="10", start="27/05/2026 13:00:00"):
    return f"""<dia><data>27/05/2026 05:45:01</data><legislatura>57</legislatura>
    <parlamentares><parlamentar><carteiraParlamentar>{card}</carteiraParlamentar>
    <nomeParlamentar>Pessoa Teste</nomeParlamentar><siglaUF>SP</siglaUF>
    <descricaoFrequenciaDia>{status}</descricaoFrequenciaDia>
    <justificativa>PRIVATE MEDICAL DETAIL MUST NOT BE EXPORTED</justificativa>
    <sessoesDia><sessaoDia><inicio>{start}</inicio><descricao>Sessão extraordinária</descricao>
    <frequencia>{status}</frequencia></sessaoDia></sessoesDia>
    </parlamentar></parlamentares></dia>""".encode()


@pytest.mark.parametrize("payload", [b"<!DOCTYPE x><x/>", b"<!ENTITY x 'secret'>", b"<broken>"])
def test_xml_never_accepts_entity_declarations_or_malformed_data(payload):
    with pytest.raises(IngestionError):
        parse_official_xml(payload)


@pytest.mark.parametrize(
    "status,expected",
    [
        ("Presença", "present"),
        ("Ausência", "absent"),
        ("Ausência justificada", "excused"),
        (None, "unknown"),
    ],
)
def test_explicit_frequency_states_remain_separate(status, expected):
    assert presence_state(status) == expected


def test_original_justification_is_not_copied_into_consolidated_records():
    records, legislature = parse_daily_session_presence(presence_xml(), DAY)
    assert legislature == 57
    assert records[0]["sessions"][0]["presence_status"] == "present"
    assert "PRIVATE" not in str(records)


@pytest.mark.parametrize(
    "payload,expected_day",
    [
        (presence_xml(), date(2026, 5, 28)),
        (presence_xml(start="28/05/2026 13:00:00"), DAY),
        (presence_xml(start="invalid"), DAY),
        (presence_xml(card=""), DAY),
        (b"<dia/>", DAY),
        (b"<dia><data>27/05/2026 05:45:01</data><legislatura>57</legislatura></dia>", DAY),
    ],
)
def test_incomplete_or_mismatched_days_never_produce_a_cohort(payload, expected_day):
    with pytest.raises(IngestionError):
        parse_daily_session_presence(payload, expected_day)


def test_duplicate_cards_are_rejected_not_double_counted():
    payload = presence_xml()
    member = payload.split(b"<parlamentar>")[1].split(b"</parlamentar>")[0]
    doubled = payload.replace(
        b"</parlamentares>", b"<parlamentar>" + member + b"</parlamentar></parlamentares>"
    )
    with pytest.raises(IngestionError, match="DUPLICATE"):
        parse_daily_session_presence(doubled, DAY)
    roster = roster_xml().replace(b"</deputados>", roster_xml().split(b"<deputados>")[1])
    with pytest.raises(IngestionError, match="AMBIGUOUS"):
        parse_presence_roster(roster)


@pytest.mark.parametrize("payload", [b"<deputados/>", b"<deputados><deputado/></deputados>"])
def test_missing_official_identity_bridge_is_not_replaced_with_a_name_match(payload):
    with pytest.raises(IngestionError):
        parse_presence_roster(payload)


def artifacts(tmp_path):
    roster = tmp_path / "roster.xml"
    cohort = tmp_path / "presence.xml"
    roster.write_bytes(roster_xml())
    cohort.write_bytes(presence_xml("Ausência"))
    return SimpleNamespace(
        path=roster, sha256="a" * 64, fetched_at="2026-10-19T00:00:00Z"
    ), SimpleNamespace(path=cohort, sha256="b" * 64, fetched_at="2026-10-19T00:00:00Z")


def test_identity_resolution_is_batched_and_raw_provider_ids_are_not_exported(
    monkeypatch, tmp_path
):
    from service.attendance import session_presence as module

    roster, cohort = artifacts(tmp_path)
    acquisition = SimpleNamespace(
        configuration=None, acquire=lambda url, *_: roster if "ObterDeputados" in url else cohort
    )
    identity = {"1": {"person_id": PERSON, "artifact": SimpleNamespace(sha256="c" * 64)}}
    monkeypatch.setattr(module, "cached_profile_artifact", lambda *_: "profile")
    calls = []
    monkeypatch.setattr(
        module, "resolve_voting_people", lambda _c, profiles: calls.append(profiles) or identity
    )
    rows, coverage = collect_daily_presence(acquisition, None, DAY)
    assert len(calls) == 1
    assert rows[0]["person_id"] == PERSON
    assert rows[0]["presence_status"] == "absent"
    assert rows[0]["scope"] == "plenary_day"
    assert "card" not in rows[0] and "name" not in rows[0]
    assert coverage["source_status_counts"] == {"absent": 1}
    roster.fetched_at = "2020-10-19T00:00:00Z"
    with pytest.raises(IngestionError, match="HISTORICAL_CARD"):
        collect_daily_presence(acquisition, None, DAY)


def test_card_name_uf_and_canonical_uniqueness_are_all_checked(tmp_path):
    roster_artifact, artifact = artifacts(tmp_path)
    cohort, _ = parse_daily_session_presence(artifact.path.read_bytes(), DAY)
    roster = parse_presence_roster(roster_artifact.path.read_bytes())
    identities = {"1": {"person_id": PERSON, "artifact": artifact}}
    assert canonical_presence_records(cohort, {}, identities, artifact, roster_artifact, DAY) == []
    assert (
        canonical_presence_records(
            cohort,
            {"10": roster["10"] | {"name": "Other"}},
            identities,
            artifact,
            roster_artifact,
            DAY,
        )
        == []
    )
    assert (
        canonical_presence_records(
            cohort, {"10": roster["10"] | {"uf": "RJ"}}, identities, artifact, roster_artifact, DAY
        )
        == []
    )
    assert canonical_presence_records(cohort, roster, {}, artifact, roster_artifact, DAY) == []
    with pytest.raises(IngestionError, match="DUPLICATE_CANONICAL"):
        canonical_presence_records(
            cohort + cohort, roster, identities, artifact, roster_artifact, DAY
        )


def test_daily_publication_retains_empty_identity_coverage_without_fake_rows(tmp_path):
    from test_attendance_dataset import RecordingStorage

    storage = RecordingStorage()
    storage.request = lambda *_args, **_kwargs: SimpleNamespace(raise_for_status=lambda: None)
    empty = publish_daily_presence(tmp_path, storage, DAY, [], {"unresolved_people": 513})
    assert empty["row_count"] == 0 and "parquet_file" not in empty
    assert storage.objects == []
    rows = [{"person_id": PERSON, "occurred_on": str(DAY), "presence_status": "absent"}]
    published = publish_daily_presence(tmp_path, storage, DAY, rows, {"unresolved_people": 512})
    assert published["row_count"] == 1 and len(storage.objects) == 1
