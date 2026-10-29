"""Real SQL for the Senate history load, in a throwaway schema that is always dropped.

Requires TEST_DATABASE_URL or SE_LIGA_BRASIL_TEST_ENV_FILE pointing at a disposable database.
"""

import os
from uuid import uuid4

import pytest
from senate_history_fixtures import TERM_49_50, affiliation, build_plan, mandate

from crawlers.senado.historical_period_rows import person_id_for, term_key
from database.historical_senate_load import TABLES, HistoricalSenateWriter
from database.operations import PROJECT_ROOT, read_sql_file, strip_transaction_wrapper
from service.ingestion.contracts import IngestionError
from service.ingestion.historical_load import LoadMode, run_historical_load

pytestmark = pytest.mark.integration
EXERCISE = [{"DataInicio": "1991-02-01", "DataFim": "1993-12-31"}]
LOAD_TABLES = tuple(name for name in TABLES if name not in {"source", "institution"})


class SchemaScopedConnection:
    """Redirects the project's schema name to a private one, preserving transaction control."""

    def __init__(self, connection, schema_name):
        self.connection = connection
        self.schema_name = schema_name

    @property
    def info(self):
        return self.connection.info

    @property
    def autocommit(self):
        return self.connection.autocommit

    def execute(self, query, parameters=None):
        return self.connection.execute(
            query.replace("se_liga_brasil", self.schema_name), parameters
        )

    def transaction(self, **options):
        return self.connection.transaction(**options)

    def count(self, table):
        return self.execute(f"SELECT count(*) AS total FROM se_liga_brasil.{table}").fetchone()[
            "total"
        ]


@pytest.fixture
def scoped():
    import psycopg
    from dotenv import dotenv_values
    from psycopg.rows import dict_row

    url = os.getenv("TEST_DATABASE_URL")
    if not url and os.getenv("SE_LIGA_BRASIL_TEST_ENV_FILE"):
        values = dotenv_values(os.environ["SE_LIGA_BRASIL_TEST_ENV_FILE"])
        url = values.get("DATABASE_URL") or values.get("SUPABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL or SE_LIGA_BRASIL_TEST_ENV_FILE for isolated SQL tests")
    schema = f"se_liga_brasil_test_{uuid4().hex[:12]}"
    connection = psycopg.connect(url, autocommit=True, row_factory=dict_row, prepare_threshold=None)
    wrapper = SchemaScopedConnection(connection, schema)
    try:
        for name in project_schema_files():
            wrapper.execute(strip_transaction_wrapper(read_sql_file(name)))
        yield wrapper
    finally:
        connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        connection.close()


def project_schema_files():
    migrations = sorted(p.name for p in (PROJECT_ROOT / "db/migrations").glob("*.sql"))
    return ["schema.sql", *(f"migrations/{name}" for name in migrations if name >= "0003")]


def snapshot(scoped):
    return {table: scoped.count(table) for table in LOAD_TABLES}


def history_steps(builder):
    builder.add_senator(
        "9001",
        [
            mandate(
                "7",
                ("49", "1991-02-01", "1995-01-31"),
                ("50", "1995-02-01", "1999-01-31"),
                exercises=EXERCISE,
            )
        ],
        [
            affiliation("22", "PFL", "1991-02-01", "1992-12-31"),
            affiliation("92", "PRN", "1993-01-01", "1993-12-31"),
            affiliation("163", "S/Partido", "1994-01-01", "1994-06-30"),
            affiliation("22", "PFL", "1994-07-01"),
        ],
    )
    builder.add_senator(
        "9002",
        [TERM_49_50],
        [affiliation("71", "PT", "1991-02-01")],
        civil_name="Pessoa Ficticia Dois",
        birth="1960-01-02",
    )


@pytest.fixture
def plan(tmp_path):
    return build_plan(tmp_path, history_steps, ["9001", "9002"])[0]


def test_dry_run_reports_counts_proves_idempotency_and_leaves_nothing(scoped, plan):
    before = snapshot(scoped)
    run = run_historical_load(scoped, HistoricalSenateWriter(scoped), plan)
    assert not run.committed and run.idempotent
    inserted = run.first_pass.inserted
    assert inserted["person"] == 2 and inserted["person_identifier"] == 2
    assert inserted["office_term"] == 2 and inserted["office_exercise"] == 1
    assert inserted["political_party_affiliation"] == 4
    assert inserted["political_party"] == 3
    assert snapshot(scoped) == before


def test_dry_run_leaves_nothing_when_the_second_statement_fails(scoped, plan, monkeypatch):
    before = snapshot(scoped)
    writer = HistoricalSenateWriter(scoped)

    def fail(*_):
        raise RuntimeError("simulated failure after partial writes")

    monkeypatch.setattr(writer, "_store_terms_and_exercises", fail)
    with pytest.raises(RuntimeError):
        run_historical_load(scoped, writer, plan)
    assert snapshot(scoped) == before


def test_apply_keeps_a_returning_party_and_is_idempotent(scoped, plan):
    run = run_historical_load(scoped, HistoricalSenateWriter(scoped), plan, LoadMode.APPLY)
    assert run.committed
    again = run_historical_load(scoped, HistoricalSenateWriter(scoped), plan, LoadMode.APPLY)
    assert sum(again.first_pass.inserted.values()) == 0
    person_id = str(person_id_for("9001"))
    rows = scoped.execute(
        "SELECT p.code,a.valid_from::text AS valid_from,a.valid_until::text AS valid_until,"
        "a.information_scope,a.observed_on::text AS observed_on "
        "FROM se_liga_brasil.political_party_affiliation a "
        "JOIN se_liga_brasil.political_party p ON p.id=a.political_party_id "
        "WHERE a.person_id=%s ORDER BY a.valid_from",
        (person_id,),
    ).fetchall()
    assert [(r["code"], r["valid_from"], r["valid_until"]) for r in rows] == [
        ("senado:party:22", "1991-02-01", "1993-01-01"),
        ("senado:party:92", "1993-01-01", "1994-01-01"),
        ("senado:party:22", "1994-07-01", None),
    ]
    assert {r["information_scope"] for r in rows} == {"institution:senado:historical_affiliations"}
    assert [r["observed_on"] for r in rows] == [r["valid_from"] for r in rows]


def test_no_party_interval_is_a_fact_and_never_a_party(scoped, plan):
    run_historical_load(scoped, HistoricalSenateWriter(scoped), plan, LoadMode.APPLY)
    assert (
        scoped.execute(
            "SELECT count(*) AS total FROM se_liga_brasil.political_party "
            "WHERE code='senado:party:163' OR abbreviation ILIKE 's/partido'"
        ).fetchone()["total"]
        == 0
    )
    fact = scoped.execute(
        "SELECT normalized_value FROM se_liga_brasil.person_fact WHERE person_id=%s "
        "AND field_name='senate_no_affiliation_intervals'",
        (str(person_id_for("9001")),),
    ).fetchone()
    assert fact["normalized_value"][0]["valid_until"] == "1994-07-01"


def test_terms_and_exercises_use_exclusive_ends_and_the_roster_term_key(scoped, plan):
    run_historical_load(scoped, HistoricalSenateWriter(scoped), plan, LoadMode.APPLY)
    person_id = str(person_id_for("9001"))
    row = scoped.execute(
        "SELECT t.official_term_key,t.term_end::text AS term_end,e.ends_before::text AS ends,"
        "e.capacity FROM se_liga_brasil.office_term t JOIN se_liga_brasil.office_exercise e "
        "ON e.term_id=t.id WHERE t.person_id=%s",
        (person_id,),
    ).fetchone()
    assert row["official_term_key"] == term_key(person_id, "49-50")
    assert (row["term_end"], row["ends"], row["capacity"]) == ("1999-02-01", "1994-01-01", "holder")


def test_historical_abbreviation_never_duplicates_a_current_party_row(scoped, plan):
    record = scoped.execute(
        "INSERT INTO se_liga_brasil.source_record(source_id,external_key,source_url,content_sha256,"
        "payload) SELECT id,'current-party','https://example.invalid/p',repeat('a',64),'{}' "
        "FROM se_liga_brasil.source LIMIT 1 RETURNING id"
    ).fetchone()["id"]
    scoped.execute(
        "INSERT INTO se_liga_brasil.political_party(code,name,abbreviation,source_record_id) "
        "VALUES('13','PARTIDO ATUAL','PT',%s)",
        (record,),
    )
    run = run_historical_load(scoped, HistoricalSenateWriter(scoped), plan)
    assert run.first_pass.party_abbreviations["senado:party:71"] == "PT (1980-)"
    assert run.first_pass.party_abbreviations["senado:party:22"] == "PFL"


def seed_existing_person(scoped, senator_id, *, with_identifier):
    record = scoped.execute(
        "INSERT INTO se_liga_brasil.source_record(source_id,external_key,source_url,content_sha256,"
        "payload) SELECT id,%s,'https://example.invalid/p',repeat('b',64),'{}' "
        "FROM se_liga_brasil.source WHERE code='senado' RETURNING id,source_id",
        (f"seed:{senator_id}",),
    ).fetchone()
    person_id = scoped.execute(
        "INSERT INTO se_liga_brasil.person(slug,civil_name,display_name,birth_date,"
        "primary_record_id,normalized_name) VALUES(%s,'PESSOA FICTICIA DOIS','X','1960-01-02',%s,"
        "'pessoa ficticia dois') RETURNING id::text AS id",
        (f"seed-{senator_id}", record["id"]),
    ).fetchone()["id"]
    if with_identifier:
        scoped.execute(
            "INSERT INTO se_liga_brasil.person_identifier(source_id,namespace,external_id,"
            "person_id,source_record_id) VALUES(%s,'senator',%s,%s,%s)",
            (record["source_id"], senator_id, person_id, record["id"]),
        )
    return person_id


def test_existing_official_identity_is_reused_not_duplicated(scoped, plan):
    existing = seed_existing_person(scoped, "9002", with_identifier=True)
    people_before = scoped.count("person")
    run = run_historical_load(scoped, HistoricalSenateWriter(scoped), plan)
    assert run.first_pass.inserted["person"] == 1
    assert run.first_pass.senators_linked_to_existing_identity == 1
    assert scoped.count("person") == people_before
    assert existing


def test_name_and_birth_match_without_official_id_waits_for_human_review(scoped, plan):
    existing = seed_existing_person(scoped, "9002", with_identifier=False)
    run = run_historical_load(scoped, HistoricalSenateWriter(scoped), plan)
    assert [(i.code, i.senator_id) for i in run.first_pass.review_required] == [
        ("IDENTITY_REVIEW_REQUIRED", "9002")
    ]
    assert run.first_pass.inserted["person"] == 1
    approved = HistoricalSenateWriter(scoped, {"9002": existing})
    run = run_historical_load(scoped, approved, plan)
    assert run.first_pass.review_required == [] and run.first_pass.inserted["person"] == 1
    assert run.first_pass.inserted["person_identifier"] == 2
    wrong = HistoricalSenateWriter(scoped, {"9002": str(person_id_for("9002"))})
    run = run_historical_load(scoped, wrong, plan)
    assert [i.code for i in run.first_pass.review_required] == ["IDENTITY_REVIEW_REQUIRED"]


def test_apply_aborts_without_writing_when_an_existing_term_disagrees(scoped, plan):
    run_historical_load(scoped, HistoricalSenateWriter(scoped), plan, LoadMode.APPLY)
    scoped.execute("UPDATE se_liga_brasil.office_term SET represented_uf='RS'")
    before = snapshot(scoped)
    run = run_historical_load(scoped, HistoricalSenateWriter(scoped), plan)
    assert {c["table"] for c in run.first_pass.conflicts} == {"office_term"}
    with pytest.raises(IngestionError, match="CONFLICT"):
        run_historical_load(scoped, HistoricalSenateWriter(scoped), plan, LoadMode.APPLY)
    assert snapshot(scoped) == before


def test_writer_refuses_to_run_outside_a_transaction(scoped, plan):
    with pytest.raises(IngestionError, match="TRANSACTION_REQUIRED"):
        HistoricalSenateWriter(scoped).write(plan)


def test_rollback_script_removes_exactly_what_the_load_inserted(scoped, plan):
    seed_existing_person(scoped, "9002", with_identifier=True)
    before = snapshot(scoped)
    run_historical_load(scoped, HistoricalSenateWriter(scoped), plan, LoadMode.APPLY)
    assert snapshot(scoped) != before
    script = (PROJECT_ROOT / "db/repairs/senate_history_1992_1994_rollback.sql").read_text()
    deletes = script.split("BEGIN;", 1)[1].split("-- END OF DELETES", 1)[0]
    with scoped.transaction():
        scoped.execute(deletes)
    assert snapshot(scoped) == before


def test_rollback_script_aborts_if_later_data_depends_on_a_created_person(scoped, plan):
    from psycopg.errors import ForeignKeyViolation

    run_historical_load(scoped, HistoricalSenateWriter(scoped), plan, LoadMode.APPLY)
    later = scoped.execute(
        "INSERT INTO se_liga_brasil.source_record(source_id,external_key,source_url,"
        "content_sha256,payload) SELECT id,'later-fact','https://example.invalid/p',"
        "repeat('c',64),'{}' FROM se_liga_brasil.source WHERE code='senado' RETURNING id"
    ).fetchone()["id"]
    scoped.execute(
        "INSERT INTO se_liga_brasil.person_fact(person_id,field_name,original_value,"
        "evidence_kind,source_record_id) SELECT person_id,'later_fact','{}','administrative',%s "
        "FROM se_liga_brasil.person_identifier LIMIT 1",
        (later,),
    )
    after_load = snapshot(scoped)
    script = (PROJECT_ROOT / "db/repairs/senate_history_1992_1994_rollback.sql").read_text()
    deletes = script.split("BEGIN;", 1)[1].split("-- END OF DELETES", 1)[0]
    with pytest.raises(ForeignKeyViolation), scoped.transaction():
        scoped.execute(deletes)
    assert snapshot(scoped) == after_load
