"""Offline regression checks for identity conflicts and quality gate boundaries."""

import ast
from datetime import date
from pathlib import Path

import pytest

from code_quality.system_design import find_project_code, review_function, review_python_file
from normalization.official_media import normalize_official_media_url
from normalization.periods import month_intervals
from normalization.scalars import normalize_date, normalize_money, normalize_year
from parsing.html import HtmlLinksParser, HtmlTableParser, decode_html
from service.identity_resolution.evidence import IdentityEvidenceBuilder, load_identity_key
from service.identity_resolution.matching import (
    PersonIdentityCandidate,
    PersonIdentityIndex,
    match_source_subject,
    names_match_initials,
    resolve_payroll_recipient,
)
from service.identity_resolution.reviewed import validate_target_identity
from service.ingestion.contracts import IngestionError


def test_quality_gate_accepts_exact_function_length_and_rejects_next_line():
    accepted = ast.parse("def bounded():\n" + "    pass\n" * 59).body[0]
    rejected = ast.parse("def bounded():\n" + "    pass\n" * 60).body[0]
    assert not review_function(accepted, Path("module.py"))
    assert [row.rule for row in review_function(rejected, Path("module.py"))] == ["function_length"]


def test_quality_gate_counts_nested_branches_and_boolean_decisions():
    source = (
        "def explicit():\n    if a and b and c:\n        if d:\n"
        "            if e:\n                if f:\n                    pass\n"
    )
    findings = review_function(ast.parse(source).body[0], Path("module.py"))
    assert {finding.rule for finding in findings} == {"nesting_depth"}


@pytest.mark.parametrize("module", ["httpx", "psycopg", "sqlite3", "subprocess"])
def test_quality_gate_blocks_infrastructure_import_variants(tmp_path, module):
    source = tmp_path / "scalars.py"
    source.write_text(f"from {module}.client import connection\n", encoding="utf-8")
    assert [row.rule for row in review_python_file(source)] == ["layer_boundary"]


def test_quality_gate_reports_syntax_and_ambiguous_async_names(tmp_path):
    source = tmp_path / "module.py"
    source.write_text("async def handle():\n    pass\n", encoding="utf-8")
    assert review_python_file(source)[0].rule == "explicit_naming"
    source.write_text("def broken(:\n", encoding="utf-8")
    assert review_python_file(source)[0].rule == "syntax"


def test_quality_gate_ignores_downloads_and_virtual_environments(tmp_path):
    for directory in ("data", ".venv", "src"):
        folder = tmp_path / directory
        folder.mkdir()
        (folder / "module.py").write_text("pass\n", encoding="utf-8")
    assert find_project_code(tmp_path) == [tmp_path / "src/module.py"]


@pytest.mark.parametrize(
    "raw",
    [
        "https://official.example:bad/a",
        "https://user@official.example/a",
        "https://official.example/a#fragment",
        "https://official.example:80/a",
        "https://official.example.evil/a",
        "javascript:alert(1)",
        None,
    ],
)
def test_official_media_rejects_unsafe_or_untrusted_locations(raw):
    assert normalize_official_media_url(raw, {"official.example"}) is None


def test_official_media_http_upgrade_keeps_query_but_requires_explicit_policy():
    raw = "http://official.example/photos/a.jpg?size=100"
    assert normalize_official_media_url(raw, {"official.example"}) is None
    assert normalize_official_media_url(raw, {"official.example"}, upgrade_http=True) == (
        "https://official.example/photos/a.jpg?size=100"
    )


def test_month_intervals_cover_leap_day_and_exclusive_month_boundary():
    assert list(month_intervals(date(2024, 2, 28), date(2024, 3, 1))) == [
        (date(2024, 2, 28), date(2024, 3, 1))
    ]
    assert list(month_intervals(date(2024, 2, 29), date(2024, 3, 2))) == [
        (date(2024, 2, 29), date(2024, 3, 1)),
        (date(2024, 3, 1), date(2024, 3, 2)),
    ]


@pytest.mark.parametrize("end", [date(2024, 1, 1), date(2023, 12, 31)])
def test_month_intervals_reject_empty_or_reversed_ranges(end):
    with pytest.raises(ValueError, match="exclusive end"):
        list(month_intervals(date(2024, 1, 1), end))


@pytest.mark.parametrize("raw", ["1/02/2024", "29/02/2023", "2024-02-29"])
def test_dates_require_exact_source_format(raw):
    with pytest.raises(IngestionError, match="INVALID_DATE"):
        normalize_date(raw)


def test_year_bounds_and_zero_negative_money_are_explicit():
    assert normalize_year("2000", minimum=2000, maximum=2026) == 2000
    with pytest.raises(IngestionError, match="INVALID_YEAR"):
        normalize_year("1999", minimum=2000)
    assert normalize_money("-0,00", allow_negative=True) == "0.00"
    with pytest.raises(IngestionError, match="NEGATIVE_MONEY_NOT_ALLOWED"):
        normalize_money("-0,01")


def test_html_table_selection_preserves_breaks_entities_and_excludes_other_tables():
    parser = HtmlTableParser("attendance")
    parser.feed(
        '<table><tr><td>unrelated</td></tr></table><table id="attendance">'
        "<tr><th>Data</th></tr><tr><td>Presença<br>Confirmada &amp; válida</td></tr></table>"
    )
    assert parser.rows == [["Data"], ["Presença Confirmada & válida"]]
    assert decode_html("Presença".encode("cp1252")) == "Presença"
    assert decode_html(b"\xef\xbb\xbfData") == "Data"


def test_html_links_ignore_anchors_without_targets_and_decode_entities():
    parser = HtmlLinksParser()
    parser.feed('<a>Sem link</a><a href="/consulta?a=1&amp;b=2">Detalhe</a>')
    assert parser.links == ["/consulta?a=1&b=2"]


def test_identity_fingerprint_reports_invalid_and_missing_documents_without_raw_values():
    builder = IdentityEvidenceBuilder(b"offline-test-key-never-production")
    invalid = builder.build_evidence("Nome Público", "11111111111")
    missing = builder.build_evidence("Nome Público", None)
    assert invalid["documentStatus"] == "invalid"
    assert missing["documentStatus"] == "missing"
    assert invalid["documentFingerprint"] is None
    assert "11111111111" not in repr(invalid)


def test_short_configured_identity_key_fails_before_filesystem_fallback(monkeypatch):
    monkeypatch.setenv("SE_LIGA_BRASIL_IDENTITY_KEY", "too-short")
    with pytest.raises(IngestionError, match="IDENTITY_KEY_TOO_SHORT"):
        load_identity_key()
    monkeypatch.setenv("SE_LIGA_BRASIL_IDENTITY_KEY", "x" * 32)
    assert load_identity_key() == b"x" * 32


def test_public_name_without_birthday_cannot_link_different_civil_names():
    person = PersonIdentityCandidate("one", {"nome civil"}, {"nome publico"}, {"10/05"})
    index = PersonIdentityIndex([person])
    subject = {"legal_name": "Outro Nome", "parliamentary_names": ["Nome Público"]}
    assert match_source_subject(subject, index)["status"] == "unmatched"
    assert match_source_subject(subject | {"birthday": "10/05"}, index)["person_id"] == "one"


def test_official_subject_bridge_cannot_override_different_exact_recipient_identity():
    people = [
        PersonIdentityCandidate("one", {"ana maria"}),
        PersonIdentityCandidate("two", {"ana m"}),
    ]
    result = resolve_payroll_recipient(
        {"recipient_name": "Ana M", "recipient_key": "month:one"},
        PersonIdentityIndex(people),
        [{"legal_name": "Ana Maria"}],
        [{"status": "matched", "person_id": "one"}],
    )
    assert result == {"status": "source_conflict", "recipient_key": "month:one"}


def test_initials_respect_connectors_and_never_accept_missing_name_tokens():
    assert names_match_initials("Ana de M", "Ana Maria")
    assert not names_match_initials("Ana", "Ana Maria")


@pytest.mark.parametrize(
    ("field", "changed", "code"),
    [
        ("civilName", "Outra Pessoa", "REVIEWED_TARGET_NAME_CHANGED"),
        ("displayName", "Outra Pessoa", "REVIEWED_TARGET_NAME_CHANGED"),
        ("politicalPartyCode", "99", "REVIEWED_TARGET_PARTY_CHANGED"),
    ],
)
def test_reviewed_crosswalk_rejects_changed_target_guards(field, changed, code):
    payload = {
        "civilName": "Pessoa Exemplo",
        "displayName": "Pessoa Pública",
        "birthDate": "1980-01-01",
        "politicalPartyCode": "10",
    }
    case = {
        "target_legal_name": "Pessoa Exemplo",
        "target_public_name": "Pessoa Pública",
        "target_birth_date": "1980-01-01",
        "target_political_party_code": "10",
    }
    with pytest.raises(IngestionError, match=code):
        validate_target_identity(payload | {field: changed}, case)
