import pytest

from service.archive_export.contracts import ArchiveError
from service.archive_export.manifest import select_entries
from service.archive_export.row_format import checked_row, decode_line, encode_line, hash_row_text

ROW_TEXT = '{"id": 1, "note": "a,\\"row\\":b ação 😀", "tags": ["x"]}'


def test_line_round_trip_keeps_exact_row_text_even_with_marker_lookalikes():
    digest, encoded = encode_line('[1, "k,\\"row\\":"]', ROW_TEXT)
    row = checked_row(encoded.decode("utf-8"))
    assert row.row_text == ROW_TEXT
    assert row.row_sha256 == digest == hash_row_text(ROW_TEXT)
    assert row.key_text == '[1, "k,\\"row\\":"]'


def test_tampered_or_malformed_lines_are_rejected():
    _, encoded = encode_line("[1]", ROW_TEXT)
    with pytest.raises(ArchiveError, match="ARCHIVE_ROW_HASH_MISMATCH"):
        checked_row(encoded.decode("utf-8").replace("ação", "acao"))
    with pytest.raises(ArchiveError, match="MALFORMED_ARCHIVE_LINE"):
        decode_line("not json\n")


def test_entries_are_selected_by_table_slice_or_file_name():
    whole = {"file": "s.t.ndjson.gz", "table": "t", "schema": "s", "slice": None}
    part = {"file": "s.t@p.ndjson.gz", "table": "t", "schema": "s", "slice": "p"}
    manifest = {"files": [whole, part]}
    assert select_entries(manifest, None) == [whole, part]
    assert select_entries(manifest, ["t"]) == [whole]
    assert select_entries(manifest, ["t@p"]) == [part]
    assert select_entries(manifest, ["s.t@p"]) == [part]
    assert select_entries(manifest, ["s.t.ndjson.gz"]) == [whole]
