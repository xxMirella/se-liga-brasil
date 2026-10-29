"""Published history preserves timeline semantics and rejects invalid compressed payloads."""

import base64
import json
import zlib

import pytest

from service.political_dashboard.timeline import timeline_cell
from service.political_dashboard_dataset import history


def test_compressed_published_history_round_trip_preserves_timeline_and_omits_names():
    composition = {
        "institution_code": "senado", "territory_code": "BR", "office_kinds": ["senator"],
        "total": 81, "coverage": "observed_complete", "snapshot_on": "2025-12-22",
        "political_parties": [{"abbreviation": "PT", "count": 81}],
        "members": [{"name": "Only annual detail needs this", "person_id": "source:1"}],
        "evidence": [{"url": "https://example.invalid/source"}],
    }
    row = {
        "year": 2025, "institution_code": "senado", "territory_code": "BR",
        "office_kinds": ["senator"], "total": 81, "composition": composition,
    }
    entry = history.history_entry("BR", [row])
    payload = history.decode_history_base64(base64.b64encode(entry["payload_zlib"]))
    decoded = history.expand_history_row(payload["rows"][0])
    assert "members" not in decoded["composition"]
    assert "evidence" not in decoded["composition"]
    for view in ("political_party", "political_orientation"):
        before = timeline_cell({"year": 2025, "institutions": [composition]},
                               "senado", "legislative", view)
        after = timeline_cell({"year": 2025, "institutions": [decoded["composition"]]},
                              "senado", "legislative", view)
        assert before == after


def valid_compressed_history():
    return zlib.compress(json.dumps({"schema_version": history.HISTORY_SCHEMA_VERSION,
                                    "rows": []}).encode())


def test_history_rejects_trailing_data_and_truncated_stream():
    compressed = valid_compressed_history()
    for invalid in (compressed + b"unexpected bytes", compressed[:-1]):
        with pytest.raises(ValueError, match="HISTORY_PAYLOAD_INVALID"):
            history.decode_history(invalid)


def test_history_rejects_oversized_decompression(monkeypatch):
    monkeypatch.setattr(history, "MAX_DECOMPRESSED_HISTORY_BYTES", 32)
    with pytest.raises(ValueError, match="HISTORY_PAYLOAD_INVALID"):
        history.decode_history(zlib.compress(b"a" * 33))


@pytest.mark.parametrize("payload", [[], {"schema_version": "political_dashboard_history.v2"}])
def test_history_rejects_incompatible_schema(payload):
    with pytest.raises(ValueError, match="HISTORY_SCHEMA_UNSUPPORTED"):
        history.decode_history(zlib.compress(json.dumps(payload).encode()))


@pytest.mark.parametrize("rows", [None, {}, ["not an annual row"]])
def test_history_rejects_invalid_row_container(rows):
    payload = {"schema_version": history.HISTORY_SCHEMA_VERSION, "rows": rows}
    with pytest.raises(ValueError, match="HISTORY_ROWS_INVALID"):
        history.decode_history(zlib.compress(json.dumps(payload).encode()))


def test_history_rejects_invalid_base64_instead_of_ignoring_characters():
    encoded = base64.b64encode(valid_compressed_history()) + b"!"
    with pytest.raises(ValueError):
        history.decode_history_base64(encoded)
