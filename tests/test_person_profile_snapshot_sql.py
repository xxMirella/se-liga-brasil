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
        "content_sha256,normalized_data,source_record_id,source_generated_at) "
        "VALUES(%s,%s,%s,repeat('b',64),'{}',%s,now()) RETURNING id",
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
