"""P1-D: the panorama document stored in the serving schema equals the live assembly."""

import json
from dataclasses import replace
from datetime import date

import pytest
from majority_panorama_fixtures import fictional_panorama
from serving_fakes import FakeServingConnection
from test_majority_panorama_reader import TODAY, fake_dashboard

from application.majority_panorama_reader import CachedMajorityPanorama, MajorityPanoramaReader
from service.majority_panorama.contracts import HouseComposition, PartyCount
from service.majority_panorama.document_codec import (
    decode_document,
    decode_exact,
    encode_document,
)
from service.serving import majority_panorama_document as dataset
from service.serving.builder import build_dataset
from service.serving.registry import SERVING_DATASETS


class StoredRow:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeReadConnection:
    """Answers the three statements the released-document read issues."""

    def __init__(self, document=None, as_of=TODAY, installed=True):
        self.document, self.as_of, self.installed = document, as_of, installed

    def execute(self, sql, parameters=None):
        if "to_regclass" in sql:
            return StoredRow({"installed": self.installed})
        if "dataset_release" in sql:
            return StoredRow(
                None
                if self.document is None
                else {
                    "name": dataset.DATASET_NAME,
                    "version": "v1",
                    "built_at": None,
                    "as_of": self.as_of,
                    "row_count": 1,
                }
            )
        return StoredRow(None if self.document is None else {"document": self.document})


class FakePool:
    def __init__(self, connection):
        self.connection = connection

    def read(self, operation):
        return operation(self.connection)


def live_reader(pool=None):
    return MajorityPanoramaReader(fake_dashboard, lambda: TODAY, pool)


def rich_panorama():
    base = fictional_panorama()
    camara = HouseComposition(
        "camara",
        100,
        {"left": 60},
        {"left": (PartyCount("PT", 60),)},
        2023,
        observed_on=date(2026, 10, 22),
        source_url="https://exemplo.invalid",
        notes=("nota",),
    )
    legislature = replace(base.legislatures[-1], camara=camara)
    return replace(
        base,
        legislatures=(*base.legislatures[:-1], legislature),
        sources_note="fonte",
        coverage_notes=("a", "b"),
    )


@pytest.mark.parametrize("panorama", [fictional_panorama(), rich_panorama(), live_reader().fetch()])
def test_codec_round_trip_is_identical(panorama):
    assert decode_document(encode_document(panorama)) == panorama
    assert decode_document(json.loads(encode_document(panorama))) == panorama


def test_encoding_is_stable_and_compact():
    text = encode_document(rich_panorama())
    assert text == encode_document(rich_panorama())
    assert ", " not in text and '": ' not in text
    assert list(json.loads(text)) == sorted(json.loads(text))


def test_reader_serves_the_stored_document_identical_to_live_assembly():
    live = live_reader().fetch()
    stored = json.loads(encode_document(live))
    pool = FakePool(FakeReadConnection(stored))
    assert live_reader(pool).fetch() == live


def test_reader_serves_stored_document_without_touching_the_dashboard():
    stored = json.loads(encode_document(rich_panorama()))

    def forbidden(parameters):
        raise AssertionError("dashboard must not be read")

    reader = MajorityPanoramaReader(forbidden, lambda: TODAY, FakePool(FakeReadConnection(stored)))
    assert reader.fetch() == rich_panorama()


@pytest.mark.parametrize(
    "connection",
    [
        FakeReadConnection(None),  # no release
        FakeReadConnection({}, as_of=date(2026, 10, 1)),  # stale release
        FakeReadConnection({}, installed=False),  # migration not applied
    ],
)
def test_reader_falls_back_to_live_assembly(connection):
    assert live_reader(FakePool(connection)).fetch() == live_reader().fetch()


def test_reader_falls_back_when_the_read_fails():
    class Broken:
        def read(self, operation):
            raise RuntimeError("down")

    assert live_reader(Broken()).fetch() == live_reader().fetch()


def test_process_cache_still_wraps_the_released_reader():
    stored = json.loads(encode_document(rich_panorama()))
    calls = []

    class CountingPool(FakePool):
        def read(self, operation):
            calls.append(1)
            return super().read(operation)

    cached = CachedMajorityPanorama(live_reader(CountingPool(FakeReadConnection(stored))))
    assert cached.fetch() is cached.fetch()
    assert len(calls) == 1


def test_dataset_is_registered_and_builds_one_deterministic_row(monkeypatch):
    assert SERVING_DATASETS[dataset.DATASET_NAME] is dataset.majority_panorama_spec
    monkeypatch.setattr(dataset, "assemble_panorama", lambda connection, today: rich_panorama())
    connection = FakeServingConnection()
    first = build_dataset(
        connection, dataset.majority_panorama_spec(connection, TODAY, today=TODAY), TODAY
    )
    second = build_dataset(
        connection, dataset.majority_panorama_spec(connection, TODAY, today=TODAY), TODAY
    )
    assert first.row_count == 1
    assert first.version == second.version
    row = connection.tables[dataset.DOCUMENT_TABLE]["rows"][0]
    assert decode_document(row[0]) == rich_panorama()


def stored_variant(change):
    document = json.loads(encode_document(rich_panorama()))
    change(document)
    return document


@pytest.mark.parametrize(
    "change",
    [
        lambda document: document.pop("coverage_notes"),  # older contract: field missing
        lambda document: document.update(unknown_field=1),  # newer contract: extra field
        lambda document: document["legislatures"][0].update(first_year="2015"),  # mistyped
        lambda document: document.update(generated_on="not-a-date"),
        lambda document: document.pop("presidents"),
    ],
)
def test_reader_falls_back_when_the_stored_document_is_corrupted(change):
    connection = FakeReadConnection(stored_variant(change))
    assert live_reader(FakePool(connection)).fetch() == live_reader().fetch()


def test_decode_exact_accepts_what_the_encoder_wrote():
    assert decode_exact(encode_document(rich_panorama())) == rich_panorama()
    with pytest.raises(ValueError):
        decode_exact("[]")


class RowsConnection:
    """The isolated test schema has no cursor(); the builder inserts rows through one."""

    def __init__(self, isolated):
        self.isolated = isolated

    def execute(self, query, parameters=None):
        return self.isolated.execute(query, parameters)

    def transaction(self):
        return self.isolated.transaction()

    def cursor(self):
        schema = self.isolated.schema_name

        class Cursor:
            def __init__(self, raw):
                self.raw = raw

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                self.raw.close()

            def executemany(self, query, rows):
                self.raw.executemany(query.replace("se_liga_brasil", schema), rows)

        return Cursor(self.isolated.connection.cursor())


@pytest.mark.integration
def test_real_postgres_round_trip_equals_live_assembly(integration_database, monkeypatch):
    live = live_reader().fetch()
    monkeypatch.setattr(dataset, "assemble_panorama", lambda connection, today: live)
    connection = RowsConnection(integration_database)
    release = build_dataset(
        connection, dataset.majority_panorama_spec(connection, TODAY, today=TODAY), TODAY
    )
    assert release.row_count == 1
    reader = MajorityPanoramaReader(forbidden_dashboard, lambda: TODAY, FakePool(connection))
    served = reader.fetch()
    assert served == live
    assert encode_document(served) == encode_document(live)


@pytest.mark.integration
def test_real_postgres_stale_or_corrupted_document_falls_back(integration_database, monkeypatch):
    live = live_reader().fetch()
    monkeypatch.setattr(dataset, "assemble_panorama", lambda connection, today: live)
    connection = RowsConnection(integration_database)
    build_dataset(connection, dataset.majority_panorama_spec(connection, TODAY, today=TODAY), TODAY)
    later = date(2026, 11, 20)
    stale = MajorityPanoramaReader(fake_dashboard, lambda: later, FakePool(connection))
    assert stale.fetch_released(later) is None
    connection.execute(f"UPDATE {dataset.DOCUMENT_TABLE} SET document = document - 'presidents'")
    corrupted = live_reader(FakePool(connection))
    assert corrupted.fetch_released(TODAY) is None
    assert corrupted.fetch() == live


def forbidden_dashboard(parameters):
    raise AssertionError("dashboard must not be read")


def test_reader_exposes_release_version_only_for_stored_document():
    stored = json.loads(encode_document(rich_panorama()))
    released = live_reader(FakePool(FakeReadConnection(stored))).fetch_reading()
    assert released.panorama == rich_panorama()
    assert released.release_version == "v1"
    assert live_reader().fetch_reading().release_version is None
    cached = CachedMajorityPanorama(live_reader(FakePool(FakeReadConnection(stored))))
    assert cached.fetch_reading().release_version == released.release_version
