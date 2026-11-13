"""person_profile_snapshot: codec roundtrip, reader fallbacks, loader parity and SQL parity."""

import json
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from serving_fakes import FakeServingConnection

from application import person_profile_loader
from application.person_profile_loader import compose_profile, load_person_profile
from application.person_profile_reads import (
    PROPOSITIONS,
    RecordingProfileSource,
    StoredProfileSource,
)
from service.serving import person_profile_snapshot as snapshot
from service.serving.person_profile_codec import decode_reads, encode_reads
from service.serving.person_profile_snapshot import (
    DATASET_NAME,
    person_profile_snapshot_spec,
    read_stored_reads,
    snapshot_rows,
)
from service.serving.registry import SERVING_DATASETS

AS_OF = date(2026, 11, 5)
PERSON = "1e294b66-fd40-47c6-ab93-b240c6f07e6a"


def canned_office_reads():
    """Reads about the person, current mandate exercises and party affiliations."""
    return {
        "fetch_public_person": {
            "person_id": PERSON,
            "display_name": "Pessoa Demo",
            "slug": "pessoa-demo",
            "birth_date": date(1980, 11, 6),
            "photo_url": "https://www.camara.leg.br/x.jpg",
            "education_level": "Superior",
            "has_current_public_office": True,
            "public_office_status_as_of": date(2026, 11, 1),
            "current_public_office_kind": "federal_deputy",
            "snapshot_institution_code": "camara",
            "snapshot_institution_name": "Câmara",
        },
        "fetch_current_exercises": [
            {
                "exercise_id": 7,
                "term_id": 3,
                "office_kind": "federal_deputy",
                "represented_uf": "PA",
                "institution_code": "camara",
                "institution_name": "Câmara",
                "starts_on": date(2023, 2, 1),
                "ends_before": None,
                "capacity": "holder",
                "term_end": date(2027, 2, 1),
            }
        ],
        "fetch_public_affiliations": [
            {
                "abbreviation": "PT",
                "name": "Partido",
                "observed_on": date(2026, 3, 1),
                "evidence_kind": "administrative",
                "valid_from": None,
                "valid_until": None,
                "information_scope": None,
            }
        ],
    }


def canned_payment_and_asset_reads():
    """Reads about latest payments, the person row and declared assets."""
    return {
        "fetch_latest_public_payments": [
            {
                "organization_code": "camara",
                "office_kind": "federal_deputy",
                "payroll_kind": "regular",
                "competence": date(2026, 10, 1),
                "currency": "BRL",
                "gross_amount": Decimal("40000.10"),
                "tax_amount": Decimal("9000.00"),
                "net_amount": Decimal("31000.10"),
            }
        ],
        "fetch_person": {"person_id": PERSON, "display_name": "Pessoa Demo"},
        "fetch_asset_years": [
            {
                "election_year": 2022,
                "item_count": 1,
                "recorded_total": Decimal("1000.50"),
                "review_count": 0,
                "source_generated_at": datetime(2022, 9, 1, 12, tzinfo=UTC),
            }
        ],
        "fetch_asset_items": [
            {
                "election_year": 2022,
                "asset_type": "Casa",
                "declared_value": Decimal("1000.50"),
                "value_quality_status": "reported",
                "source_url": "https://divulgacandcontas.tse.jus.br/a",
            }
        ],
    }


def canned_activity_reads():
    """Reads about activity, attendance, propositions, legal scopes and payroll history."""
    return {
        "historical_activity": {"items": [], "truncated": False, "coverage": "partial"},
        "attendance": {"percentage": "80.0", "period": "2026-09", "present": 8, "required": 10},
        PROPOSITIONS: {"items": [{"id": 1, "title": "PL 1"}], "truncated": False, "page": 1},
        "attendance_history": [{"period": "2026-08", "present": 9, "required": 9}],
        "legal_scopes": [{"office_kind": "federal_deputy", "reviewed_on": "2026-01-01"}],
        "payroll_history": {"months": [], "truncated": False},
    }


def canned_reads(**changes):
    """Raw reads shaped like the database returns them (dates, Decimals, jsonb values)."""
    reads = canned_office_reads() | canned_payment_and_asset_reads() | canned_activity_reads()
    return reads | changes


class ScriptedSource:
    """Live stand-in: returns canned reads and counts how often each one is read."""

    def __init__(self, reads):
        self.reads, self.calls = reads, []

    def read_snapshot(self):
        return self._nothing()

    @contextmanager
    def _nothing(self):
        yield

    def __getattr__(self, name):
        def read(*arguments):
            self.calls.append(name)
            return self.reads[PROPOSITIONS if name == "propositions" else name]

        return read


def test_codec_roundtrips_exact_python_types_and_key_order():
    reads = {
        "z": {"b": 1, "a": [Decimal("1.50"), date(2026, 1, 2)], "é": None},
        "when": datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        "id": UUID(int=5),
        "pair": (1, "x"),
        "flag": True,
        "ratio": 0.1,
        "text": "ação",
    }
    text = encode_reads(reads)
    for document in (
        text,
        json.loads(text),
        json.loads(json.dumps(json.loads(text), sort_keys=True)),
    ):
        decoded = decode_reads(document)
        assert decoded == reads
        assert list(decoded["z"]) == ["b", "a", "é"]
        assert type(decoded["when"]) is datetime and type(decoded["z"]["a"][1]) is date
        assert str(decoded["z"]["a"][0]) == "1.50" and type(decoded["pair"]) is tuple
        assert type(decoded["flag"]) is bool
    assert encode_reads(reads) == text


def test_codec_rejects_unknown_values_instead_of_storing_them():
    for bad in ({"x": object()}, {"x": float("nan")}, {"x": {1: 2}}, {"x": "a\x00b"}):
        with pytest.raises((TypeError, ValueError)):
            encode_reads(bad)
    with pytest.raises(ValueError):
        decode_reads({"format": 99, "reads": []})


def test_canned_reads_survive_the_codec():
    reads = canned_reads()
    assert decode_reads(json.loads(encode_reads(reads))) == reads


def test_stored_profile_is_identical_to_live_profile_in_dict_and_json():
    reads = canned_reads()
    live = compose_profile(ScriptedSource(reads), PERSON, AS_OF)
    stored_source = StoredProfileSource(
        decode_reads(json.loads(encode_reads(reads))), ScriptedSource({})
    )
    stored = compose_profile(stored_source, PERSON, AS_OF)
    assert stored == live
    assert json.dumps(stored, ensure_ascii=False) == json.dumps(live, ensure_ascii=False)
    assert live["age"] == {"value": 45, "status": "known"}


def test_dates_derive_from_the_request_day_not_from_the_build_day():
    stored = decode_reads(json.loads(encode_reads(canned_reads())))
    day_of = compose_profile(StoredProfileSource(stored, None), PERSON, date(2026, 11, 6))
    assert day_of["age"]["value"] == 46  # birthday on the 6th: derived at read time


def test_recording_source_keeps_reads_and_only_the_first_proposition_page():
    live = ScriptedSource(canned_reads())
    recorder = RecordingProfileSource(live)
    compose_profile(recorder, PERSON, AS_OF)
    assert set(recorder.recorded) == set(canned_reads())
    other = RecordingProfileSource(ScriptedSource(canned_reads()))
    compose_profile(other, PERSON, AS_OF, proposal_page=2)
    assert PROPOSITIONS not in other.recorded


def test_other_proposition_pages_are_read_live_everything_else_is_replayed():
    live = ScriptedSource(canned_reads(propositions={"items": [], "page": 2}))
    stored = StoredProfileSource(canned_reads(), live)
    profile = compose_profile(stored, PERSON, AS_OF, proposal_page=2)
    assert live.calls == ["propositions"] and profile["propositions"]["page"] == 2


class Pool:
    def __init__(self, connection):
        self.connection = connection

    def read(self, operation):
        return operation(self.connection)


class QuietConnection:
    info = None

    @contextmanager
    def transaction(self):
        yield

    def execute(self, sql, parameters=None):
        return self


@pytest.fixture
def loader(monkeypatch):
    live = ScriptedSource(canned_reads())
    monkeypatch.setattr("application.person_profile_reads.LiveProfileSource", lambda c: live)
    return live


def test_loader_uses_the_snapshot_without_touching_the_database(monkeypatch, loader):
    stored = canned_reads()
    monkeypatch.setattr(snapshot, "read_stored_reads", lambda *a: stored)
    profile = load_person_profile(Pool(QuietConnection()), PERSON, AS_OF)
    assert loader.calls == [] and profile["display_name"] == "Pessoa Demo"


@pytest.mark.parametrize("stored", [None, {"fetch_public_person": {}}])
def test_loader_falls_back_to_the_live_path(monkeypatch, loader, stored):
    """No snapshot (None) and an unusable one (missing/odd reads) both read live."""
    expected = compose_profile(ScriptedSource(canned_reads()), PERSON, AS_OF)
    monkeypatch.setattr(snapshot, "read_stored_reads", lambda *a: stored)
    assert load_person_profile(Pool(QuietConnection()), PERSON, AS_OF) == expected
    assert "fetch_public_person" in loader.calls and person_profile_loader.logger


class ServingFake(FakeServingConnection):
    def __init__(self, payload=None, row_as_of=AS_OF):
        super().__init__()
        self.payload, self.row_as_of = payload, row_as_of

    def _handlers(self):
        def stored(_match, parameters):
            if self.payload is None:
                return None
            return {"payload": self.payload, "as_of": self.row_as_of}

        return [(r"SELECT payload,as_of", stored), *super()._handlers()]


def release(connection, as_of=AS_OF):
    connection.releases[DATASET_NAME] = {
        "name": DATASET_NAME,
        "version": "v",
        "built_at": datetime.now(UTC),
        "as_of": as_of,
        "row_count": 1,
    }


def test_reader_returns_reads_only_for_a_fresh_release_row_and_day():
    payload = json.loads(encode_reads(canned_reads()))
    connection = ServingFake(payload)
    assert read_stored_reads(connection, PERSON, AS_OF) is None  # no release yet
    release(connection)
    assert read_stored_reads(connection, PERSON, AS_OF) == canned_reads()
    assert read_stored_reads(connection, PERSON.upper(), AS_OF) == canned_reads()
    next_day = AS_OF + timedelta(days=1)  # release still valid, but the row was built for AS_OF
    assert read_stored_reads(connection, PERSON, next_day) is None
    assert read_stored_reads(connection, PERSON, AS_OF + timedelta(days=2)) is None  # old release
    connection.release_table_installed = False
    assert read_stored_reads(connection, PERSON, AS_OF) is None  # migration not applied


def test_reader_ignores_missing_row_other_day_bad_payload_and_bad_id():
    payload = json.loads(encode_reads(canned_reads()))
    for connection in (
        ServingFake(None),  # person outside the scope
        ServingFake(payload, row_as_of=AS_OF - timedelta(days=1)),  # row built for another day
        ServingFake({"format": 1, "reads": [{"__t": "bogus"}]}),  # cannot be decoded
        ServingFake({"format": 2, "reads": {}}),  # foreign format
    ):
        release(connection)
        assert read_stored_reads(connection, PERSON, AS_OF) is None
    connection = ServingFake(payload)
    assert read_stored_reads(connection, "not-a-uuid", AS_OF) is None
    assert connection.statements == []


def test_registered_and_built_through_the_atomic_builder(monkeypatch):
    assert SERVING_DATASETS[DATASET_NAME] is person_profile_snapshot_spec
    connection = ServingFake()
    connection.execute = _with_scope(connection, [PERSON])
    monkeypatch.setattr(snapshot, "collect_person_reads", lambda *a: canned_reads())
    spec = person_profile_snapshot_spec(connection, AS_OF, today=AS_OF)
    assert spec.columns == ("person_id", "payload", "source_version", "as_of")
    rows = list(
        snapshot_rows(_transactional(connection), [PERSON], AS_OF, lambda *a: canned_reads())
    )
    assert rows[0][0] == PERSON and rows[0][3] == AS_OF and len(rows[0][2]) == 32
    assert decode_reads(rows[0][1]) == canned_reads()


def _transactional(connection):
    return connection


def _with_scope(connection, ids):
    original = connection.execute

    class Rows:
        def fetchall(self):
            return [{"person_id": identifier} for identifier in ids]

    def execute(sql, parameters=None):
        return Rows() if "FROM se_liga_brasil.person p" in sql else original(sql, parameters)

    return execute


def test_a_failing_person_is_skipped_not_fatal():
    def collect(_connection, person_id, _as_of):
        if person_id == "bad":
            raise RuntimeError("read failed")
        return canned_reads()

    rows = list(snapshot_rows(ServingFake(), ["bad", PERSON], AS_OF, collect))
    assert [row[0] for row in rows] == [PERSON]


def test_huge_proposition_pages_are_not_stored(monkeypatch):
    huge = canned_reads(propositions={"items": ["x" * 200_000]})
    monkeypatch.setattr(
        "application.person_profile_reads.LiveProfileSource", lambda c: ScriptedSource(huge)
    )
    reads = snapshot.collect_person_reads(None, PERSON, AS_OF)
    assert PROPOSITIONS not in reads and "fetch_public_person" in reads
