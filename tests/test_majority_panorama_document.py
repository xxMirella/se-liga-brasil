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
from service.majority_panorama.document_codec import decode_document, encode_document
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
