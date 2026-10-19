"""Political-office filtering isolates candidacies and their dependent data."""

from dataclasses import replace

from crawlers.tse.discovery import build_resource
from crawlers.tse.validator import validate_resource
from storage.files import read_json_lines
from storage.validation_index import ValidationIndex


def test_office_scope_filters_candidates_and_asset_dependencies(
    configuration, candidate_row, archive_factory
):
    configuration = replace(configuration, office_codes=("5", "6", "7"))
    index = ValidationIndex(configuration.storage_directory.parent / "scope.sqlite")
    try:
        rows = [
            candidate_row,
            candidate_row | {"SQ_CANDIDATO": "2", "CD_CARGO": "3", "DS_CARGO": "GOVERNADOR"},
        ]
        validated = validate_resource(archive_factory("candidate", rows), configuration, index)
        assert validated.summary["valid"] == 1
        assert validated.summary["skipped"] == 1
        assert configuration.scope_key == "PA;offices=5,6,7"
        asset = candidate_row | {
            "NR_ORDEM_BEM_CANDIDATO": "1",
            "CD_TIPO_BEM_CANDIDATO": "1",
            "VR_BEM_CANDIDATO": "10,00",
        }
        assets = [asset, asset | {"SQ_CANDIDATO": "2"}]
        validated_assets = validate_resource(archive_factory("asset", assets), configuration, index)
        assert validated_assets.summary["valid"] == 1
        record = next(read_json_lines(validated_assets.records_path))
        assert record["normalizedData"]["candidateSequence"] == candidate_row["SQ_CANDIDATO"]
    finally:
        index.close()


def test_official_catalog_url_label_is_removed_before_security_validation():
    resource = build_resource(
        {
            "id": "official",
            "name": "Complementares 2018",
            "url": "URL: https://cdn.tse.jus.br/consulta_cand_complementar/2018.zip",
        },
        "candidatos-2018",
        2018,
    )
    assert resource.url == "https://cdn.tse.jus.br/consulta_cand_complementar/2018.zip"
