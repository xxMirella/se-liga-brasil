"""File adapter, rubric proposal adapter, catalog adapter, comparison report and the CLI command."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from party_orientation_fixtures import (
    PERIOD_2019_2022,
    balanced_party_evidence,
    evidence_document,
    evidence_entry,
    make_rubric,
    rubric_document,
)

from application import cli
from service.party_orientation_model.catalog_adapter import (
    to_catalog_observation,
    to_catalog_observations,
)
from service.party_orientation_model.classifier import classify_party_period
from service.party_orientation_model.comparison import render_comparison_report
from service.party_orientation_model.contracts import PartyModelContractError
from service.party_orientation_model.rubric import parse_rubric
from service.party_orientation_model.rubric_adapter import adapt_proposal_to_rubric_document
from service.party_orientation_model.serialization import classification_document

RUBRIC = make_rubric()
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def document_for(party, stance):
    items = balanced_party_evidence(RUBRIC, party, stance)
    return classification_document(
        classify_party_period(party, PERIOD_2019_2022, items, (), RUBRIC)
    )


def write_model_directory(root: Path, parties=("ALFA",)) -> Path:
    (root / "rubric.json").write_text(json.dumps(rubric_document()))
    entries = []
    for party in parties:
        for item in balanced_party_evidence(RUBRIC, party, 0.6, prefix=f"{party}"):
            entries.append(
                evidence_entry(
                    item.evidence_id,
                    party,
                    item.layer,
                    item.indicator_id,
                    item.stance,
                    years=(2020, 2020),
                )
            )
    votes = root / "votes"
    votes.mkdir()
    (votes / "party_vote_positions.json").write_text(json.dumps(evidence_document(entries)))
    return root


def run_cli(*values):
    arguments = cli.create_argument_parser().parse_args(["classify-political-parties", *values])
    return cli.execute_command(arguments)


def test_cli_classifies_a_party_and_writes_reproducible_files(tmp_path):
    model = write_model_directory(tmp_path)
    result = run_cli("--party", "ALFA", "--period", "2019-2022", "--model-directory", str(model))
    assert result["classifications"] == 1 and result["categories"] == {"right": 1}
    assert "policies/parties/*/party_policy_evidence.json" in result["layers_without_files"]
    target = model / "output" / "alfa" / "2019-2022.json"
    first = target.read_bytes()
    run_cli("--party", "ALFA", "--period", "2019-2022", "--model-directory", str(model))
    assert target.read_bytes() == first
    document = json.loads(first)
    assert document["model_version"] == "party_orientation_model.v1"
    assert {e["source_url"] for e in document["evidence_used"]}
    assert (model / "output" / "index.json").exists()


def test_cli_all_uses_rubric_periods_and_every_party_in_the_evidence(tmp_path):
    model = write_model_directory(tmp_path, parties=("ALFA", "BETA"))
    result = run_cli("--all", "--model-directory", str(model))
    assert result["classifications"] >= 4  # at least two parties x the two rubric periods
    assert result["categories"]["right"] == 2


def test_cli_requires_party_or_all(tmp_path):
    model = write_model_directory(tmp_path)
    with pytest.raises(PartyModelContractError):
        run_cli("--model-directory", str(model))


def test_cli_lists_files_with_unsupported_schema_instead_of_guessing(tmp_path):
    model = write_model_directory(tmp_path)
    folder = model / "discourse" / "parties" / "ALFA"
    folder.mkdir(parents=True)
    (folder / "party-discourse.json").write_text(json.dumps({"schema": "party-discourse/1"}))
    result = run_cli("--party", "ALFA", "--period", "2020", "--model-directory", str(model))
    assert result["evidence_files_skipped_unsupported_schema"] == [
        "discourse/parties/ALFA/party-discourse.json"
    ]


def test_cli_writes_comparison_report_without_touching_the_catalog(tmp_path):
    model = write_model_directory(tmp_path)
    catalog = PROJECT_ROOT / "src/service/political_dashboard/political_orientation_catalog.json"
    before = catalog.read_bytes()
    report = tmp_path / "report.md"
    run_cli(
        "--party",
        "ALFA",
        "--period",
        "2019-2022",
        "--model-directory",
        str(model),
        "--comparison-report",
        str(report),
    )
    text = report.read_text()
    assert "### PDT" in text and "### PCdoB" in text
    assert "nenhuma conclusão é emitida" in text
    assert catalog.read_bytes() == before


def test_domain_library_does_not_load_network_or_database_modules():
    code = (
        "import sys; import service.party_orientation_model.classifier as c, "
        "service.party_orientation_model.batch, service.party_orientation_model.comparison; "
        "print(sorted({'httpx','psycopg','requests','duckdb'} & set(sys.modules)))"
    )
    output = subprocess.run(
        [sys.executable, "-I", "-c", code],
        capture_output=True,
        text=True,
        check=True,
        env={"PYTHONPATH": str(PROJECT_ROOT / "src")},
    ).stdout
    assert output.strip() == "[]"


def test_catalog_adapter_converts_classified_results_only():
    right = to_catalog_observation(document_for("ALFA", 0.7))
    assert right["catalog_group"] == "right" and right["status"] == "model_classification"
    assert right["score"] == pytest.approx(5 + 5 * document_for("ALFA", 0.7)["overall_score"])
    empty = classification_document(classify_party_period("ZETA", PERIOD_2019_2022, (), (), RUBRIC))
    assert to_catalog_observation(empty) is None
    assert len(to_catalog_observations([document_for("ALFA", 0.7), empty])) == 1


def lookup_stub(table):
    return lambda party, year: table.get((party, year), "undetermined")


def test_comparison_report_marks_agreement_disagreement_and_hypotheses():
    documents = [document_for("PDT", 0.7), document_for("PCdoB", 0.7)]
    table = {("PDT", year): "left" for year in range(2019, 2023)}
    table |= {("PCdoB", year): "right" for year in range(2019, 2023)}
    text = render_comparison_report(
        documents,
        lookup_stub(table),
        ["PDT", "PCdoB", "XYZ"],
        "m.v1",
        hypotheses={"PDT": "right", "PCdoB": "left"},
    )
    assert "discorda" in text and "concorda" in text
    assert "contrariando a hipótese" in text  # PCdoB hypothesis: left, model: right
    assert "compatível com a hipótese" in text  # PDT hypothesis: right, model: right
    assert "XYZ" in text.split("sem classificação comparável")[1]


def test_report_states_missing_data_instead_of_concluding():
    text = render_comparison_report([], lookup_stub({}), ["PDT"], "m.v1")
    assert text.count("nenhuma conclusão é emitida") == 2  # PDT and PCdoB, no hypothesis assumed


def test_real_rubric_proposal_adapts_to_a_valid_contract():
    path = PROJECT_ROOT / "data/political-orientation/party-model/rubric.json"
    if not path.exists():
        pytest.skip("rubric.json ainda não entregue")
    rubric = parse_rubric(adapt_proposal_to_rubric_document(json.loads(path.read_text())))
    assert rubric.band_limits == (-0.8, -0.4, -0.15, 0.15, 0.4, 0.8)
    behavior = sum(v for k, v in rubric.layer_weights.items() if k != "discourse")
    assert behavior == pytest.approx(0.7) and rubric.layer_weights["discourse"] == pytest.approx(
        0.2
    )
    assert rubric.sufficiency.minimum_indicators == {"economic": 4, "sociocultural": 3}
