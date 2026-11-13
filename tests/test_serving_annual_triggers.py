"""Annual build scripts refresh the serving datasets after a confirmed write; no network."""

import ast
import importlib
import sys
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
ANNUAL_BUILD_SCRIPTS = (
    "build_camara_full_history_annual",
    "build_camara_history_annual",
    "build_chamber_orientation_annual",
    "build_chamber_reconciliation_annual",
    "build_national_government_annual",
    "build_political_dashboard_annual",
    "build_political_dashboard_history",
    "build_presidential_annual_dataset",
    "build_senate_election_annual",
    "build_senate_history_annual_dataset",
    "build_senate_report_annual",
    "build_state_assembly_annual",
)
DRY_RUN_FLAGS = {"activate", "apply"}


@pytest.fixture
def load_script(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))

    def load(name):
        sys.modules.pop(name, None)
        return importlib.import_module(name)

    return load


@pytest.fixture
def trigger(load_script, monkeypatch):
    module = load_script("serving_rebuild_trigger")
    connection = object()
    monkeypatch.setattr(module, "connect_database", lambda _: nullcontext(connection))
    module.rebuild = Mock(return_value={"majority_panorama_document": "v1"})
    monkeypatch.setattr(module, "rebuild_serving_datasets", module.rebuild)
    module.connection = connection
    return module


def test_trigger_rebuilds_on_a_fresh_connection_after_a_confirmed_write(trigger):
    outcome = trigger.rebuild_serving_after_write(None, written=True)
    assert outcome == {"majority_panorama_document": "v1"}
    assert trigger.rebuild.call_args.args[0] is trigger.connection


def test_trigger_does_nothing_without_a_confirmed_write(trigger, monkeypatch):
    monkeypatch.setattr(trigger, "connect_database", Mock(side_effect=AssertionError))
    assert trigger.rebuild_serving_after_write(None, written=False) is None
    trigger.rebuild.assert_not_called()


@pytest.mark.parametrize("failing", ["connect_database", "rebuild_serving_datasets"])
def test_trigger_failure_never_propagates(trigger, monkeypatch, failing):
    monkeypatch.setattr(trigger, failing, Mock(side_effect=RuntimeError("boom")))
    assert trigger.rebuild_serving_after_write(None, written=True) is None


def written_argument(script_name):
    """The `written=` expression of every trigger call in the script's main()."""
    tree = ast.parse((SCRIPTS / f"{script_name}.py").read_text(encoding="utf-8"))
    main = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "main")
    return [
        keyword.value
        for call in ast.walk(main)
        if isinstance(call, ast.Call)
        and getattr(call.func, "id", None) == "rebuild_serving_after_write"
        for keyword in call.keywords
        if keyword.arg == "written"
    ]


@pytest.mark.parametrize("script_name", ANNUAL_BUILD_SCRIPTS)
def test_every_annual_build_script_calls_the_trigger_once_from_main(script_name):
    assert len(written_argument(script_name)) == 1


@pytest.mark.parametrize("script_name", ANNUAL_BUILD_SCRIPTS)
def test_scripts_with_a_dry_run_gate_the_trigger_on_the_write_flag(script_name):
    (written,) = written_argument(script_name)
    flags = {n.attr for n in ast.walk(written) if isinstance(n, ast.Attribute)}
    unconditional = isinstance(written, ast.Constant) and written.value is True
    assert unconditional or flags & DRY_RUN_FLAGS


@pytest.mark.parametrize(
    ("apply", "changed", "rebuilds"), [(True, 3, 1), (True, 0, 0), (False, 0, 0)]
)
def test_history_script_rebuilds_only_after_changed_apply(
    load_script, monkeypatch, apply, changed, rebuilds
):
    script = load_script("build_political_dashboard_history")
    rebuild = Mock()
    monkeypatch.setattr(script, "rebuild_serving_after_write", rebuild)
    monkeypatch.setattr(script, "connect_database", lambda _: nullcontext(object()))
    monkeypatch.setattr(script, "run_apply", lambda *_: ([], True, {}, changed))
    monkeypatch.setattr(script, "run_dry", lambda *_: ([], True, {}))
    monkeypatch.setattr(sys, "argv", ["x", *(["--apply"] if apply else [])])
    script.main()
    rebuild.assert_called_once()
    assert rebuild.call_args.kwargs == {"written": bool(rebuilds)}


@pytest.mark.parametrize(("flag", "written"), [("--apply", True), (None, False)])
def test_dashboard_annual_script_passes_the_write_decision(
    load_script, monkeypatch, tmp_path, flag, written
):
    script = load_script("build_political_dashboard_annual")
    rebuild = Mock()
    monkeypatch.setattr(script, "rebuild_serving_after_write", rebuild)
    monkeypatch.setattr(script, "connect_database", lambda _: nullcontext(object()))
    monkeypatch.setattr(script, "build_partitions", lambda *_: ([], []))
    activated = Mock()
    monkeypatch.setattr(script, "activate_database_generation", activated)
    monkeypatch.setattr(
        sys, "argv", ["x", "--year", "2024", "--storage", str(tmp_path), *([flag] if flag else [])]
    )
    script.main()
    assert activated.called is written
    assert rebuild.call_args.kwargs == {"written": written}


def test_dashboard_annual_failure_before_the_write_does_not_rebuild(
    load_script, monkeypatch, tmp_path
):
    script = load_script("build_political_dashboard_annual")
    rebuild = Mock()
    monkeypatch.setattr(script, "rebuild_serving_after_write", rebuild)
    monkeypatch.setattr(script, "connect_database", lambda _: nullcontext(object()))
    monkeypatch.setattr(script, "build_partitions", Mock(side_effect=RuntimeError("boom")))
    monkeypatch.setattr(sys, "argv", ["x", "--year", "2024", "--storage", str(tmp_path), "--apply"])
    with pytest.raises(RuntimeError):
        script.main()
    rebuild.assert_not_called()
