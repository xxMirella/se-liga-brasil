"""Source texts are readable without treating the latest text as the voted version."""

from datetime import date
from html.parser import HTMLParser
from uuid import uuid4

import pytest
from test_public_voting_timeline_dataset import timeline_row

from crawlers.camara.legislative_normalization import normalize_legislative_detail
from crawlers.camara.voting_staging import event_matter_fields
from crawlers.senado.legislative import normalize_process
from service.analytical_datasets.public_voting_timeline import (
    LEGACY_PUBLIC_TIMELINE_COLUMNS,
    PUBLIC_TIMELINE_COLUMNS,
    project_public_voting_timeline,
)
from service.analytical_datasets.storage import connect_analytical_engine
from service.public_profile.contracts import VoteQuery
from service.public_profile.storage_query import query_snapshot
from service.public_profile_web.document_links import render_reading_links
from service.public_profile_web.vote_groups import render_activity_history_entry
from service.voting_pipeline.source_senado import matter_reading_url


class Anchors(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.links = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs))


@pytest.mark.parametrize("institution", ["camara", "senado", "alesp", "alerj"])
def test_all_institutions_separate_reading_from_vote_and_preserve_tab(institution):
    markup = render_activity_history_entry({
        "action_type": "vote", "institution": {"code": institution},
        "proposition": {"kind": "EMC", "title": "Emenda demonstrativa"},
        "official_url": "https://www.senado.leg.br/votacao/1",
        "text_url": "https://www.senado.leg.br/documento/1",
        "document_url": "https://www.senado.leg.br/materia/1",
    })
    anchors = Anchors(markup).links
    assert len(anchors) == 3
    assert len({anchor["href"] for anchor in anchors}) == 3
    assert all(anchor["target"] == "_blank" for anchor in anchors)
    assert all(set(anchor["rel"].split()) == {"noopener", "noreferrer"} for anchor in anchors)
    assert "versão exata do texto votado ainda não foi confirmada" in markup
    assert "Ler texto efetivamente votado" not in markup
    assert "Ler norma promulgada" not in markup


def test_known_voted_version_and_final_norm_have_distinct_labels():
    markup = render_reading_links({
        "voted_text_url": "https://www.camara.leg.br/versao/1",
        "final_norm_url": "https://www.planalto.gov.br/norma/2",
    })
    assert "Ler texto efetivamente votado" in markup
    assert "Ler norma promulgada · texto final" in markup
    assert "ainda não foi confirmada" not in markup


@pytest.mark.parametrize("url", [None, "javascript:alert(1)", "https://example.org/doc"])
def test_missing_or_nonofficial_reading_link_is_explicit(url):
    markup = render_reading_links({"text_url": url})
    assert "Link de leitura do documento ainda não disponível" in markup
    assert not Anchors(markup).links


def test_source_document_links_survive_exact_camara_and_senate_normalization():
    uri = "https://dadosabertos.camara.leg.br/api/v2/proposicoes/123"
    text_url = "https://www.camara.leg.br/proposicoesWeb/prop_mostrarintegra?codteor=456"
    row = {"uri": uri, "siglaTipo": "EMC", "numero": 1, "ano": 2026,
           "urlInteiroTeor": text_url}
    assert normalize_legislative_detail(row)["textUrl"] == text_url
    event = {"discovery": {"uriProposicaoObjeto": uri}, "detail": {}}
    fields = event_matter_fields(event, {"official_url": None}, {uri: row}, uri)
    assert fields["matter_text_url"] == text_url
    assert fields["matter_document_url"] == uri
    senate = normalize_process({"id": 123, "sigla": "PEC", "documento": {"url": text_url}})
    assert senate["document_url"] == text_url
    assert matter_reading_url({"codigoMateria": 123}).endswith("/materia/123")
    assert matter_reading_url({"codigoMateria": "invalid"}) is None


def test_old_inputs_remain_valid_and_unknown_columns_still_fail():
    from service.analytical_datasets import DatasetPartition

    partition = DatasetPartition("senado", 2026)
    row = timeline_row()
    projected = project_public_voting_timeline(row, partition)
    assert projected["matter_text_url"] is None
    linked = project_public_voting_timeline(
        row | {"matter_text_url": "https://www.senado.leg.br/documento/1"}, partition
    )
    assert linked["matter_text_url"].endswith("/documento/1")
    with pytest.raises(ValueError):
        project_public_voting_timeline(row | {"unsupported": "value"}, partition)
    with pytest.raises(ValueError):
        project_public_voting_timeline(row | {"matter_text_url": "https://example.org"}, partition)


def test_mixed_legacy_and_new_partitions_remain_readable(tmp_path):
    from service.analytical_datasets import DatasetPartition

    person = str(uuid4())
    records = [timeline_row(person_id=person, voting_id=str(number)) for number in (1, 2)]
    paths, entries = {}, []
    with connect_analytical_engine(tmp_path / "spill") as engine:
        for index, record in enumerate(records):
            projected = project_public_voting_timeline(record, DatasetPartition("senado", 2026))
            columns = LEGACY_PUBLIC_TIMELINE_COLUMNS if index == 0 else PUBLIC_TIMELINE_COLUMNS
            fields = ",".join(f"?::{kind} AS {name}" for name, kind in columns.items())
            path = tmp_path / f"partition-{index}.parquet"
            engine.execute(f"CREATE OR REPLACE TABLE payload AS SELECT {fields}",
                           [projected[name] for name in columns])
            engine.table("payload").write_parquet(str(path))
            manifest = {"institution_code": "senado", "occurred_on": "2026-10-14",
                        "row_count": 1, "schema_version": f"person_voting_timeline.v{index + 1}",
                        "parquet_file": path.name}
            paths[path.name] = path
            entries.append({"source": "senado", "manifest": manifest})

    class Reader:
        directory = tmp_path

        def parquet_path(self, partition, manifest):
            return paths[manifest["parquet_file"]]

    query = VoteQuery(person, date(2026, 10, 14), date(2026, 10, 14), limit=10)
    rows = query_snapshot(Reader(), {"entries": entries}, query, None, [])
    assert len(rows) == 2
    assert all(row["matter_text_url"] is None for row in rows)


def test_legacy_senate_nominal_link_exposes_its_verified_matter_without_guessing():
    from service.public_profile.storage_votes import legacy_matter_document_url

    row = {"institution_code": "senado", "official_url":
           "https://www25.senado.leg.br/web/atividade/materias/-/materia/123/votacoes"}
    assert legacy_matter_document_url(row).endswith("/materia/123")
    assert legacy_matter_document_url(row | {"institution_code": "camara"}) is None
    assert legacy_matter_document_url(row | {"official_url": "https://www.senado.leg.br/"}) is None


def test_proceeding_uses_its_own_document_before_the_current_proposal_text():
    from service.public_profile_web.activity import proposition_activity_items

    items = proposition_activity_items({
        "id": "1", "text_url": "https://www.camara.leg.br/documento/current",
        "events": [{"official_event_key": "2", "occurred_on": "2026-01-01",
                    "text_url": "https://www.camara.leg.br/documento/amendment"}],
    })
    assert items[1]["text_url"].endswith("/amendment")


def test_alesp_document_key_opens_its_official_dossier_not_a_guessed_pdf():
    from database.public_propositions import public_proposition_document_url

    row = {"institution_code": "alesp", "official_key": "1000281893"}
    assert public_proposition_document_url(row) == (
        "https://www.al.sp.gov.br/propositura/?id=1000281893"
    )
    assert public_proposition_document_url(row | {"official_key": "invalid"}) is None


@pytest.mark.integration
def test_sql_history_preserves_document_from_original_event_evidence(integration_database):
    from test_public_profile_integration import create_public_read_fixture

    from database.public_propositions import fetch_person_propositions

    connection = integration_database
    person, _, record, institutions, _ = create_public_read_fixture(connection)
    connection.execute(
        "UPDATE se_liga_brasil.source_record SET payload="
        "'{\"documentUrl\":\"https://www.senado.leg.br/documento/original\"}' WHERE id=%s",
        (record,),
    )
    proposition = connection.execute(
        "INSERT INTO se_liga_brasil.proposition(institution_id,official_key,kind,number,year,"
        "title,introduced_on,current_status,status_as_of,source_record_id) "
        "VALUES(%s,'https://www.senado.leg.br/materia/1','PEC','1',2026,'PEC fictícia',"
        "'2026-01-01','unknown',now(),%s) RETURNING id", (institutions[0], record),
    ).fetchone()["id"]
    connection.execute(
        "INSERT INTO se_liga_brasil.proposition_person(proposition_id,person_id,role,"
        "source_record_id) VALUES(%s,%s,'author',%s)", (proposition, person, record),
    )
    connection.execute(
        "INSERT INTO se_liga_brasil.proposition_event(proposition_id,official_event_key,"
        "occurred_at,event_type,description,source_record_id) "
        "VALUES(%s,'event:1','2026-01-02T12:00:00Z','amendment','Emenda fictícia',%s)",
        (proposition, record),
    )
    item = fetch_person_propositions(connection, person, date(2026, 10, 22))["items"][0]
    assert item["document_url"] == "https://www.senado.leg.br/materia/1"
    assert item["events"][0]["text_url"] == "https://www.senado.leg.br/documento/original"
