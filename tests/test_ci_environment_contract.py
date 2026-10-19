"""Contract regressions must fail without revealing any supplied secret value."""

import ast
import runpy
from pathlib import Path

import pytest

from code_quality.environment_contract import (
    ENVIRONMENT_NAMES,
    literal_environment_names,
    read_template_names,
    validate_environment_template,
)


@pytest.mark.parametrize(
    "entry",
    [
        "DATABASE_URL=private-value",
        "UNKNOWN=",
        "broken",
        "DATABASE_URL=\nDATABASE_URL=",
    ],
)
def test_invalid_template_rejects_values_unknown_names_and_duplicates(tmp_path, entry):
    path = tmp_path / ".env.example"
    path.write_text(entry)
    with pytest.raises(ValueError) as error:
        read_template_names(path)
    assert "private-value" not in str(error.value)


def test_template_allows_only_empty_documented_names(tmp_path):
    path = tmp_path / ".env.example"
    path.write_text("# private values stay elsewhere\n\nDATABASE_URL=\nSUPABASE_URL=\n")
    assert read_template_names(path) == {"DATABASE_URL", "SUPABASE_URL"}


def test_missing_documented_name_blocks_validation(tmp_path):
    (tmp_path / ".env.example").write_text("DATABASE_URL=\n")
    with pytest.raises(ValueError, match="SUPABASE_STORAGE_KEY"):
        validate_environment_template(tmp_path)


def test_repository_template_covers_configuration_contract():
    validate_environment_template(Path(__file__).resolve().parents[1])


def test_extracts_environment_reads_without_executing_code():
    tree = ast.parse("""
os.getenv("DATABASE_URL")
os.environ.get("SUPABASE_URL", "")
values.get("SUPABASE_STORAGE_KEY")
values.get("lowercase_domain_field")
other.getenv("DATABASE_URL")
get_value("DATABASE_URL")
os.getenv(variable_name)
os.getenv()
""")
    assert literal_environment_names(tree) == {
        "DATABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_STORAGE_KEY",
    }


def test_quality_runner_returns_nonzero_for_findings(monkeypatch, capsys):
    import code_quality.environment_contract as environment
    import code_quality.system_design as design

    monkeypatch.setattr(environment, "validate_environment_template", lambda _: None)
    monkeypatch.setattr(
        design,
        "review_project",
        lambda _: [
            {
                "path": "module.py",
                "line": 1,
                "rule": "nesting_depth",
                "message": "too deep",
            }
        ],
    )
    script = Path(__file__).resolve().parents[1] / "scripts/check_quality.py"
    runner = runpy.run_path(str(script))
    assert runner["main"]() == 1
    assert "module.py:1: nesting_depth" in capsys.readouterr().out


def test_quality_runner_returns_zero_without_findings(monkeypatch):
    import code_quality.environment_contract as environment
    import code_quality.system_design as design

    monkeypatch.setattr(environment, "validate_environment_template", lambda _: None)
    monkeypatch.setattr(design, "review_project", lambda _: [])
    script = Path(__file__).resolve().parents[1] / "scripts/check_quality.py"
    assert runpy.run_path(str(script))["main"]() == 0


def test_environment_template_names_match_documented_schema():
    assert "SE_LIGA_BRASIL_IDENTITY_KEY" in ENVIRONMENT_NAMES


def test_new_environment_read_requires_documentation(tmp_path):
    (tmp_path / ".env.example").write_text(
        "".join(name + "=\n" for name in sorted(ENVIRONMENT_NAMES))
    )
    source = tmp_path / "src"
    source.mkdir()
    (source / "configuration.py").write_text('os.getenv("NEW_SERVER_TOKEN")')
    with pytest.raises(ValueError, match="NEW_SERVER_TOKEN"):
        validate_environment_template(tmp_path)


def test_subscript_and_lowercase_environment_names_cannot_bypass_contract():
    tree = ast.parse('os.environ["NEW_TOKEN"]\nos.getenv("lowercase_config")')
    assert literal_environment_names(tree) == {"NEW_TOKEN", "lowercase_config"}


def test_import_aliases_and_keyword_names_require_documentation():
    tree = ast.parse("""
import os as system
from os import getenv as read_environment, environ as environment
system.environ.get("ALIAS_TOKEN")
read_environment("IMPORTED_TOKEN")
environment["SUBSCRIPT_TOKEN"]
system.getenv(key="KEYWORD_TOKEN")
""")
    assert literal_environment_names(tree) == {
        "ALIAS_TOKEN",
        "IMPORTED_TOKEN",
        "SUBSCRIPT_TOKEN",
        "KEYWORD_TOKEN",
    }
