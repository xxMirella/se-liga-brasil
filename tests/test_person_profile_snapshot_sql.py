"""person_profile_snapshot on a disposable PostgreSQL (TEST_DATABASE_URL): parity and fallbacks."""

import json
from contextlib import contextmanager
from datetime import date, timedelta
from uuid import uuid4

import pytest
from test_person_profile_snapshot import Pool

from application import person_profile_loader
from application.person_profile_loader import load_person_profile
from service.serving import build_dataset
from service.serving import person_profile_snapshot as snapshot
from service.serving.person_profile_snapshot import person_profile_snapshot_spec

AS_OF = date(2026, 11, 5)


# --- SQL parity on a disposable PostgreSQL (TEST_DATABASE_URL), never on production ------------


class CountingConnection:
    def __init__(self, connection):
        self.connection, self.statements = connection, []

    def execute(self, sql, parameters=None):
        self.statements.append(sql)
        return self.connection.execute(sql, parameters)

    def __getattr__(self, name):
        return getattr(self.connection, name)


class BuildConnection:
    """The isolated schema connection plus the cursor().executemany() the builder uses."""

    def __init__(self, db):
        self.db = db

    def __getattr__(self, name):
        return getattr(self.db, name)

    def execute(self, sql, parameters=None):
        return self.db.execute(sql, parameters)

    @contextmanager
    def cursor(self):
        raw = self.db.connection

        class Cursor:
            def executemany(_, sql, batch):
                with raw.cursor() as cursor:
                    cursor.executemany(sql.replace("se_liga_brasil", self.db.schema_name), batch)

        yield Cursor()


def insert_rich_person(db):
    from test_public_profile_integration import create_public_read_fixture

    person_id, other_id, record_id, _, _ = create_public_read_fixture(db)
    source_id = db.execute(
        "SELECT source_id FROM se_liga_brasil.source_record WHERE id=%s", (record_id,)
    ).fetchone()["source_id"]
    camara = db.execute(
        "INSERT INTO se_liga_brasil.institution(code,name,level,uf,official_url) "
        "VALUES('camara','Câmara dos Deputados','federal','BR','https://example.invalid') "
        "RETURNING id"
    ).fetchone()["id"]
    term = db.execute(
        "INSERT INTO se_liga_brasil.office_term(person_id,institution_id,office_kind,"
        "represented_uf,legislature_key,official_term_key,term_start,term_end,source_record_id) "
        "VALUES(%s,%s,'federal_deputy','PA','57','57','2023-02-01','2027-02-01',%s) RETURNING id",
        (person_id, camara, record_id),
    ).fetchone()["id"]
    db.execute(
        "INSERT INTO se_liga_brasil.office_exercise(term_id,starts_on,capacity,source_record_id) "
        "VALUES(%s,'2023-02-01','holder',%s)",
        (term, record_id),
    )
    db.execute("UPDATE se_liga_brasil.person SET birth_date='1980-11-06' WHERE id=%s", (person_id,))
    return person_id, other_id, record_id, source_id, camara


def insert_entity(db, source_id, record_id, kind):
    return db.execute(
        "INSERT INTO se_liga_brasil.ingestion_entity(source_id,entity_kind,external_key,"
        "content_sha256,source_record_id,source_generated_at) "
        "VALUES(%s,%s,%s,repeat('b',64),%s,now()) RETURNING id",
        (source_id, kind, str(uuid4()), record_id),
    ).fetchone()["id"]


def insert_party_affiliation(db, person_id, record_id):
    db.execute(
        "INSERT INTO se_liga_brasil.political_party(code,name,abbreviation,source_record_id) "
        "VALUES('9','Partido Demo','PD',%s)",
        (record_id,),
    )
    db.execute(
        "INSERT INTO se_liga_brasil.political_party_affiliation(person_id,political_party_id,"
        "observed_on,source_record_id,evidence_kind) "
        "SELECT %s,id,'2026-03-01',%s,'administrative' FROM se_liga_brasil.political_party",
        (person_id, record_id),
    )


def insert_asset_declarations(db, person_id, record_id, source_id):
    for year, value in ((2022, "1000.50"), (2018, "250.00")):
        db.execute(
            "INSERT INTO se_liga_brasil.candidate_asset_declaration(entity_id,person_id,"
            "election_year,candidate_sequence,asset_order,asset_type,declared_value,"
            "source_record_id,source_generated_at) VALUES(%s,%s,%s,'1','1','Casa',%s,%s,now())",
            (insert_entity(db, source_id, record_id, "asset"), person_id, year, value, record_id),
        )


def insert_payroll_payment(db, person_id, record_id, source_id):
    db.execute(
        "INSERT INTO se_liga_brasil.person_payroll_payment(entity_id,source_id,recipient_key,"
        "recipient_name,normalized_recipient_name,person_id,identity_status,organization_code,"
        "office_kind,represented_uf,competence,currency,payroll_kind,gross_amount,tax_amount,"
        "net_amount,source_record_id,observed_at) VALUES(%s,%s,'k','Demo','demo',%s,'verified',"
        "'camara','federal_deputy','PA','2026-10-01','BRL','regular',40000.10,9000,31000.10,%s,now())",
        (insert_entity(db, source_id, record_id, "pay"), source_id, person_id, record_id),
    )


def insert_person_facts(db, person_id, record_id):
    facts = {
        "camara_attendance:2026-09": {
            "period": "2026-09",
            "present": 8,
            "required": 10,
            "percentage": "80.0",
            "sourceObservedAt": "2026-10-02T00:00:00+00:00",
        },
        "alerj_historical_activity:1": {
            "eventType": "speech",
            "eventKey": "k1",
            "occurredOn": "2020-05-04",
            "description": "Discurso",
            "evidenceUrl": "https://www.alerj.rj.gov.br/x",
        },
        "senado_cabinet_payroll:2026-09": {
            "period": "2026-09",
            "institution": "senado",
            "currency": "BRL",
            "payment_entries": 1,
            "gross_amount": "1000.00",
            "allowances_amount": "0",
            "total_amount": "1000.00",
            "sourceUrl": "https://www.senado.leg.br/p",
            "sourceObservedAt": "2026-10-01",
            "personId": person_id,
            "calculationVersion": 2,
            "roles": [
                {
                    "role": "ASSESSOR",
                    "gross_amount": "1000.00",
                    "allowances_amount": "0",
                    "total_amount": "1000.00",
                    "payment_entries": 1,
                }
            ],
        },
    }
    for name, value in facts.items():
        db.execute(
            "INSERT INTO se_liga_brasil.person_fact(person_id,field_name,original_value,"
            "normalized_value,evidence_kind,review_status,source_record_id) "
            "VALUES(%s,%s,'{}',%s::jsonb,'administrative','verified',%s)",
            (person_id, name, json.dumps(value), record_id),
        )


def insert_proposition_with_event(db, person_id, record_id, camara):
    proposition = db.execute(
        "INSERT INTO se_liga_brasil.proposition(institution_id,official_key,kind,number,year,"
        "title,summary,introduced_on,current_status,status_as_of,source_record_id) "
        "VALUES(%s,'https://dadosabertos.camara.leg.br/api/v2/proposicoes/1','PL','1',2026,"
        "'PL 1/2026','Ementa','2026-03-02','in_progress',now(),%s) RETURNING id",
        (camara, record_id),
    ).fetchone()["id"]
    db.execute(
        "INSERT INTO se_liga_brasil.proposition_person VALUES(%s,%s,'author',%s)",
        (proposition, person_id, record_id),
    )
    db.execute(
        "INSERT INTO se_liga_brasil.proposition_event(proposition_id,official_event_key,"
        "occurred_at,event_type,description,source_record_id) "
        "VALUES(%s,'e1','2026-03-03T12:00:00Z','tramitacao','Apresentada',%s)",
        (proposition, record_id),
    )


def insert_rich_data(db, person_id, record_id, source_id, camara):
    insert_party_affiliation(db, person_id, record_id)
    insert_asset_declarations(db, person_id, record_id, source_id)
    insert_payroll_payment(db, person_id, record_id, source_id)
    insert_person_facts(db, person_id, record_id)
    insert_proposition_with_event(db, person_id, record_id, camara)


def render(profile):
    from service.public_profile_web import render_person_profile

    filters = {"tab": "profile", "start_date": "", "end_date": "", "scope": "history"}
    return render_person_profile(
        profile, {"items": [], "coverage": {"state": "not_requested"}}, filters
    )


@pytest.mark.integration
def test_snapshot_profile_and_html_equal_the_live_path_on_real_sql(
    integration_database, monkeypatch
):
    db = integration_database
    person_id, other_id, record_id, source_id, camara = insert_rich_person(db)
    insert_rich_data(db, person_id, record_id, source_id, camara)
    outcome = build_dataset(
        BuildConnection(db), person_profile_snapshot_spec(db, AS_OF, today=AS_OF), AS_OF
    )
    assert outcome.row_count == 1  # the person with no mandate/proposition/payroll stays out

    counted = CountingConnection(db)
    from_snapshot = load_person_profile(Pool(counted), person_id, AS_OF)
    snapshot_statements = len(counted.statements)

    monkeypatch.setattr(snapshot, "read_stored_reads", lambda *a: None)
    counted = CountingConnection(db)
    live = load_person_profile(Pool(counted), person_id, AS_OF)
    live_statements = len(counted.statements)

    assert from_snapshot == live
    assert json.dumps(from_snapshot, ensure_ascii=False) == json.dumps(live, ensure_ascii=False)
    assert render(from_snapshot) == render(live)
    assert live["cabinet_payroll"]["months"] and live["propositions"]["items"]
    assert live["assets"]["declarations"] and live["attendance"] and live["payments"]
    assert (live_statements, snapshot_statements) == (13, 3)


@pytest.mark.integration
def test_fallbacks_on_real_sql_keep_the_result(integration_database, monkeypatch):
    db = integration_database
    person_id, other_id, record_id, source_id, camara = insert_rich_person(db)
    insert_rich_data(db, person_id, record_id, source_id, camara)
    calls = []
    original = person_profile_loader.compose_profile
    monkeypatch.setattr(
        person_profile_loader,
        "compose_profile",
        lambda s, *a: calls.append(type(s)) or original(s, *a),
    )
    live = load_person_profile(Pool(db), person_id, AS_OF)  # no release at all: live
    build_dataset(BuildConnection(db), person_profile_snapshot_spec(db, AS_OF, today=AS_OF), AS_OF)
    calls.clear()
    assert load_person_profile(Pool(db), person_id, AS_OF) == live
    assert [c.__name__ for c in calls] == ["StoredProfileSource"]
    calls.clear()
    stale = AS_OF + timedelta(days=3)  # release too old for that request day
    load_person_profile(Pool(db), person_id, stale)
    assert [c.__name__ for c in calls] == ["LiveProfileSource"]
    calls.clear()  # person outside the snapshot scope is served live
    assert load_person_profile(Pool(db), other_id, AS_OF)["person_id"] == other_id
    assert [c.__name__ for c in calls] == ["LiveProfileSource"]
    db.execute(
        "UPDATE se_liga_brasil_serving.person_profile_snapshot SET payload='{\"format\":1}'::jsonb"
    )
    calls.clear()  # undecodable row
    assert load_person_profile(Pool(db), person_id, AS_OF) == live
    assert [c.__name__ for c in calls] == ["LiveProfileSource"]


# --- sample of people, legal scopes, proposition pages, per-person cost -----------------------


def install_legal_scopes(db):
    from database.office_legal_scopes import ingest_office_legal_scopes
    from database.operations import read_sql_file, strip_transaction_wrapper
    from service.office_duties.legal_catalog import build_legal_scope_records

    db.execute(
        strip_transaction_wrapper(read_sql_file("migrations/0020_office_legal_scope_versions.sql"))
    )
    ingest_office_legal_scopes(db, build_legal_scope_records())


def insert_authored_propositions(db, person_id, record_id, camara, count):
    base = uuid4().int % 10**9 * 1000
    db.execute(
        "WITH created AS (INSERT INTO se_liga_brasil.proposition(institution_id,official_key,"
        "kind,number,year,title,summary,introduced_on,current_status,status_as_of,"
        "source_record_id) SELECT %s,'https://dadosabertos.camara.leg.br/api/v2/proposicoes/'"
        "||(%s+n),'PL',n::text,2025,'PL '||n,'Ementa','2025-01-01'::date+n,'in_progress',"
        "now(),%s FROM generate_series(1,%s) n RETURNING id) "
        "INSERT INTO se_liga_brasil.proposition_person(proposition_id,person_id,role,"
        "source_record_id) SELECT id,%s,'author',%s FROM created",
        (camara, base, record_id, count, person_id, record_id),
    )


def insert_extra_person(db, record_id, camara, name, *, propositions=0, born="1975-01-01"):
    """A second profile of another shape: a mandate, optional many propositions, no payroll."""
    person_id = str(uuid4())
    db.execute(
        "INSERT INTO se_liga_brasil.person(id,slug,civil_name,display_name,primary_record_id,"
        "birth_date) VALUES(%s,%s,'Identificação privada fictícia',%s,%s,%s)",
        (person_id, person_id, name, record_id, born),
    )
    term = db.execute(
        "INSERT INTO se_liga_brasil.office_term(person_id,institution_id,office_kind,"
        "represented_uf,legislature_key,official_term_key,term_start,term_end,source_record_id) "
        f"VALUES(%s,%s,'federal_deputy','SP','57','57-{person_id}','2023-02-01','2027-02-01',%s) "
        "RETURNING id",
        (person_id, camara, record_id),
    ).fetchone()["id"]
    db.execute(
        "INSERT INTO se_liga_brasil.office_exercise(term_id,starts_on,capacity,source_record_id) "
        "VALUES(%s,'2023-02-01','holder',%s)",
        (term, record_id),
    )
    if propositions:
        insert_authored_propositions(db, person_id, record_id, camara, propositions)
    return person_id


def build_snapshot(db):
    return build_dataset(
        BuildConnection(db), person_profile_snapshot_spec(db, AS_OF, today=AS_OF), AS_OF
    )


def live_profile(db, monkeypatch, person_id, page=1):
    with monkeypatch.context() as patch:
        patch.setattr(snapshot, "read_stored_reads", lambda *a: None)
        return load_person_profile(Pool(db), person_id, AS_OF, page)


@pytest.mark.integration
def test_html_is_identical_for_a_sample_with_legal_scopes_and_every_proposition_page(
    integration_database, monkeypatch
):
    db = integration_database
    person_id, other_id, record_id, source_id, camara = insert_rich_person(db)
    insert_rich_data(db, person_id, record_id, source_id, camara)
    install_legal_scopes(db)
    heavy = insert_extra_person(db, record_id, camara, "Autor Prolífico", propositions=130)
    light = insert_extra_person(db, record_id, camara, "Mandato Simples", born="1990-11-06")
    assert build_snapshot(db).row_count == 3  # other_id (no data) stays out
    sample = [(person_id, 1), (heavy, 1), (heavy, 2), (light, 1)]
    for sampled_id, page in sample:
        from_snapshot = load_person_profile(Pool(db), sampled_id, AS_OF, page)
        live = live_profile(db, monkeypatch, sampled_id, page)
        assert from_snapshot == live
        assert render(from_snapshot) == render(live)
    assert live_profile(db, monkeypatch, person_id)["legal_scopes"]
    first = load_person_profile(Pool(db), heavy, AS_OF)["propositions"]
    second = load_person_profile(Pool(db), heavy, AS_OF, 2)["propositions"]
    assert first["truncated"] is True and len(first["items"]) == 100
    assert second["page"] == 2 and len(second["items"]) == 30 and second["truncated"] is False


@pytest.mark.integration
def test_page_one_is_replayed_and_later_pages_are_the_only_live_read(
    integration_database, monkeypatch
):
    db = integration_database
    _, _, record_id, _, camara = insert_rich_person(db)
    heavy = insert_extra_person(db, record_id, camara, "Autor Prolífico", propositions=130)
    build_snapshot(db)
    for page, expected_live in ((1, 0), (2, 1)):
        counted = CountingConnection(db)
        load_person_profile(Pool(counted), heavy, AS_OF, page)
        live_propositions = [
            s for s in counted.statements if "FROM se_liga_brasil.proposition_person" in s
        ]
        assert len(live_propositions) == expected_live


@pytest.mark.integration
def test_oversized_proposition_page_is_left_out_and_read_live(integration_database, monkeypatch):
    db = integration_database
    _, _, record_id, _, camara = insert_rich_person(db)
    heavy = insert_extra_person(db, record_id, camara, "Autor Prolífico", propositions=30)
    monkeypatch.setattr(snapshot, "MAX_PAYLOAD_CHARS", 1_000)
    build_snapshot(db)
    stored = db.execute(
        "SELECT payload FROM se_liga_brasil_serving.person_profile_snapshot WHERE person_id=%s",
        (heavy,),
    ).fetchone()["payload"]
    from service.serving.person_profile_codec import decode_reads

    assert "propositions" not in decode_reads(stored)
    live = live_profile(db, monkeypatch, heavy)
    assert load_person_profile(Pool(db), heavy, AS_OF) == live
    assert render(load_person_profile(Pool(db), heavy, AS_OF)) == render(live)


@pytest.mark.integration
def test_incomplete_payload_and_other_day_row_fall_back_with_the_same_html(
    integration_database, monkeypatch
):
    db = integration_database
    person_id, _, record_id, source_id, camara = insert_rich_person(db)
    insert_rich_data(db, person_id, record_id, source_id, camara)
    build_snapshot(db)
    live = live_profile(db, monkeypatch, person_id)
    table = "se_liga_brasil_serving.person_profile_snapshot"
    db.execute(  # valid format and tags, but a read is missing: composition fails, live path runs
        f"UPDATE {table} SET payload=jsonb_set(payload,'{{reads}}',"
        '\'{"__t":"dict","items":[]}\'::jsonb)'
    )
    assert load_person_profile(Pool(db), person_id, AS_OF) == live
    db.execute(f"UPDATE {table} SET as_of=as_of-1")  # row built for another day
    assert render(load_person_profile(Pool(db), person_id, AS_OF)) == render(live)


@pytest.mark.integration
def test_build_reads_each_person_with_a_constant_number_of_statements(integration_database):
    db = integration_database
    person_id, _, record_id, source_id, camara = insert_rich_person(db)
    insert_rich_data(db, person_id, record_id, source_id, camara)
    extra = [insert_extra_person(db, record_id, camara, f"Pessoa {n}") for n in range(4)]
    counted = CountingConnection(db)
    rows = list(snapshot.snapshot_rows(counted, [person_id, *extra], AS_OF))
    assert len(rows) == 5
    reads = [s for s in counted.statements if s.lstrip().upper().startswith(("SELECT", "WITH"))]
    assert len(reads) <= 5 * 13  # 13 reads per person, none per record (no N+1 inside a read)
