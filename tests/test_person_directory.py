"""person_directory: build SQL shape, reader contract, release-based selection and SQL parity."""

from datetime import UTC, date, datetime
from itertools import product
from types import SimpleNamespace
from uuid import uuid4

import pytest
from serving_fakes import FakeServingConnection
from test_public_profile_integration import create_public_read_fixture

from database.public_people import PublicPeopleRepository
from database.public_people_directory import (
    DirectoryPeopleRepository,
    like_pattern,
    normalize_search_term,
    open_people_repository,
    search_people_from_directory,
)
from service.public_profile.people import PeopleQuery
from service.serving import build_dataset
from service.serving.person_directory import person_directory_insert_sql, person_directory_spec
from service.serving.registry import SERVING_DATASETS

AS_OF = date(2026, 11, 5)


class RecordingConnection:
    def __init__(self):
        self.calls = []

    def execute(self, sql, parameters=None):
        self.calls.append((sql, parameters))
        return SimpleNamespace(fetchall=lambda: [])


def test_dataset_is_registered_and_inlines_as_of_without_bind_parameters():
    assert SERVING_DATASETS["person_directory"] is person_directory_spec
    sql = person_directory_insert_sql(AS_OF)
    assert "%(" not in sql
    assert "DATE '2026-11-05'" in sql
    assert "unaccent(display_name)" in sql
    assert "p.photo_url AS photo" in sql
    spec = person_directory_spec(None, AS_OF)
    assert spec.name == "person_directory"
    assert any("gin (uf)" in index for index in spec.indexes)
    assert sql.format(table="t").startswith("INSERT INTO t(")


def test_build_runs_through_the_atomic_builder():
    connection = FakeServingConnection()
    release = build_dataset(connection, person_directory_spec(None, AS_OF), AS_OF)
    assert release.name == "person_directory"


@pytest.mark.parametrize(
    ("text", "expected"),
    [("José", "jose"), ("JOSÉ da Conceição", "jose da conceicao"), ("Ñandú", "nandu")],
)
def test_search_term_is_normalised_like_name_search(text, expected):
    assert normalize_search_term(text) == expected


def test_like_pattern_escapes_wildcards_and_leaves_folding_to_sql():
    assert like_pattern("A%_\\É") == "%A\\%\\_\\\\É%"


@pytest.mark.parametrize("sort", ["name", "party", "state"])
def test_reader_uses_the_matching_keyset_and_fetches_one_extra_row(sort):
    connection = RecordingConnection()
    cursor = ("0MDB", "Ana", str(uuid4()))
    search_people_from_directory(connection, PeopleQuery(sort=sort, limit=3), cursor)
    sql, parameters = connection.calls[0]
    assert parameters["limit"] == 4 and "OFFSET" not in sql
    if sort == "name":
        assert "(display_name,person_id)>(%(after_name)s" in sql
        assert "'' AS sort_key" in sql
    else:
        column = f"{sort}_sort_key"
        assert f"({column},display_name,person_id)>(%(after_key)s" in sql
        assert f"ORDER BY {column},display_name,person_id" in sql


def test_reader_omits_keyset_without_cursor():
    connection = RecordingConnection()
    search_people_from_directory(connection, PeopleQuery(q="José"), None)
    sql, parameters = connection.calls[0]
    assert ")>(" not in sql
    assert parameters["pattern"] == "%José%"
    assert "name_search LIKE lower(unaccent(%(pattern)s))" in sql


def test_party_list_and_search_read_the_directory_table_when_release_is_valid():
    connection = RecordingConnection()
    connection.release_table_installed = True
    repository = DirectoryPeopleRepository(connection)
    repository.list_current_political_parties(AS_OF)
    repository.search_people(PeopleQuery(), AS_OF, None)
    assert all("se_liga_brasil_serving.person_directory" in sql for sql, _ in connection.calls)


def fake_with_release(as_of, installed=True):
    connection = FakeServingConnection()
    connection.release_table_installed = installed
    if as_of:
        connection.releases["person_directory"] = {
            "name": "person_directory",
            "version": "v",
            "built_at": datetime.now(UTC),
            "as_of": as_of,
            "row_count": 1,
        }
    return connection


@pytest.mark.parametrize(
    ("release_as_of", "installed", "expected"),
    [
        (AS_OF, True, DirectoryPeopleRepository),
        (date(2026, 11, 4), True, DirectoryPeopleRepository),
        (date(2026, 11, 1), True, PublicPeopleRepository),  # stale
        (date(2026, 11, 6), True, PublicPeopleRepository),  # built for a later day
        (None, True, PublicPeopleRepository),  # never built
        (None, False, PublicPeopleRepository),  # migration not applied
    ],
)
def test_directory_is_used_only_with_a_valid_release(release_as_of, installed, expected):
    connection = fake_with_release(release_as_of, installed)
    assert type(open_people_repository(connection, AS_OF)) is expected


# -- SQL parity (isolated schema, rolled back; skipped without a test database) --------------


def insert_person(connection, record_id, name, slug_suffix=""):
    identifier = str(uuid4())
    connection.execute(
        "INSERT INTO se_liga_brasil.person(id,slug,civil_name,display_name,primary_record_id) "
        "VALUES(%s,%s,'Privado',%s,%s)",
        (identifier, identifier + slug_suffix, name, record_id),
    )
    return identifier


def insert_mandate(connection, record_id, institution_id, person_id, kind, uf, ends=None):
    term_id = connection.execute(
        "INSERT INTO se_liga_brasil.office_term(person_id,institution_id,office_kind,"
        "represented_uf,legislature_key,official_term_key,term_start,source_record_id) "
        "VALUES(%s,%s,%s,%s,'f',%s,'2026-01-01',%s) RETURNING id",
        (person_id, institution_id, kind, uf, str(uuid4()), record_id),
    ).fetchone()["id"]
    connection.execute(
        "INSERT INTO se_liga_brasil.office_exercise"
        "(term_id,starts_on,ends_before,capacity,source_record_id) "
        "VALUES(%s,'2026-02-01',%s,'holder',%s)",
        (term_id, ends, record_id),
    )


def insert_affiliation(connection, record_id, person_id, party_id, observed, **extra):
    values = {"evidence_kind": "administrative", "valid_until": None} | extra
    connection.execute(
        "INSERT INTO se_liga_brasil.political_party_affiliation(person_id,political_party_id,"
        "observed_on,source_record_id,evidence_kind,valid_until) VALUES(%s,%s,%s,%s,%s,%s)",
        (person_id, party_id, observed, record_id, values["evidence_kind"], values["valid_until"]),
    )


def populate(connection):
    _, _, record_id, institutions, _ = create_public_read_fixture(connection)
    senate, other = institutions
    party = {}
    for code, abbreviation in (("1", "MDB (1980-)"), ("2", "PT"), ("3", "PL"), ("4", "NOVO")):
        party[abbreviation.split()[0]] = connection.execute(
            "INSERT INTO se_liga_brasil.political_party(code,name,abbreviation,source_record_id) "
            "VALUES(%s,%s,%s,%s) RETURNING id",
            (code, f"Partido {abbreviation}", abbreviation, record_id),
        ).fetchone()["id"]
    jose = insert_person(connection, record_id, "José Alves")
    insert_mandate(connection, record_id, senate, jose, "senator", "SP")
    insert_affiliation(connection, record_id, jose, party["MDB"], "2026-03-01")
    jose2 = insert_person(connection, record_id, "Jose Carlos")
    insert_mandate(connection, record_id, other, jose2, "federal_deputy", "RJ")
    insert_affiliation(connection, record_id, jose2, party["PT"], "2026-03-01")
    ana = insert_person(connection, record_id, "Ana Lima")
    insert_mandate(connection, record_id, senate, ana, "senator", "RJ")
    insert_mandate(connection, record_id, other, ana, "federal_deputy", "SP")
    insert_affiliation(connection, record_id, ana, party["PL"], "2026-01-01")
    insert_affiliation(connection, record_id, ana, party["PT"], "2026-05-01")
    carla = insert_person(connection, record_id, "Carla 100%_")
    insert_affiliation(connection, record_id, carla, party["MDB"], "2026-04-01")
    insert_affiliation(connection, record_id, carla, party["PT"], "2026-04-01")
    insert_mandate(connection, record_id, other, carla, "state_deputy", "SP", ends="2026-06-01")
    eva = insert_person(connection, record_id, "Eva Souza")
    insert_affiliation(
        connection, record_id, eva, party["NOVO"], "2026-03-01", valid_until="2026-04-01"
    )
    insert_affiliation(
        connection, record_id, eva, party["PL"], "2026-03-02", evidence_kind="electoral_declaration"
    )
    sven = insert_person(connection, record_id, "Søren Ærø")
    insert_mandate(connection, record_id, senate, sven, "senator", "MG")
    alias = insert_person(connection, record_id, "Ana Lima Duplicada")
    connection.execute(
        "INSERT INTO se_liga_brasil.person_identity_alias"
        "(alias_person_id,canonical_person_id,source_record_id,resolution_reason) "
        "VALUES(%s,%s,%s,'official_history')",
        (alias, ana, record_id),
    )
    for number in range(7):
        extra = insert_person(connection, record_id, f"Zélia Número {number}")
        insert_mandate(connection, record_id, other, extra, "federal_deputy", "SP")
        insert_affiliation(connection, record_id, extra, party["PT"], "2026-03-01")


def walk(read, query, cursor_row=None):
    """Every page for `query`, following the (sort_key, name, id) keyset like the service."""
    rows, cursor = [], None
    while True:
        page = read(query, cursor)
        rows.extend(page[: query.limit])
        if len(page) <= query.limit:
            return rows
        last = page[query.limit - 1]
        cursor = (last["sort_key"], last["display_name"], last["person_id"])


PARITY_FILTERS = [
    {},
    {"q": "jose"},
    {"q": "JOSÉ"},
    {"q": "100%"},
    {"q": "%_"},
    {"q": "zelia"},
    {"q": "soren"},
    {"q": "Ærø"},
    {"uf": "MG"},
    {"office_kind": "state_deputy"},
    {"political_party": "ZZZ"},
    {"uf": "RJ", "office_kind": "federal_deputy", "political_party": "PT"},
    {"uf": "SP"},
    {"uf": "RJ"},
    {"office_kind": "senator"},
    {"uf": "SP", "office_kind": "senator"},
    {"uf": "RJ", "office_kind": "senator"},
    {"uf": "SP", "office_kind": "federal_deputy"},
    {"political_party": "MDB"},
    {"political_party": "pt"},
    {"political_party": "NOVO"},
    {"political_party": "PL"},
    {"uf": "SP", "political_party": "PT", "q": "ze"},
]


@pytest.mark.integration
@pytest.mark.parametrize("sort", ["name", "party", "state"])
def test_directory_matches_canonical_sql_for_filters_orderings_and_pagination(
    integration_database, sort
):
    populate(integration_database)
    build_dataset(integration_database, person_directory_spec(None, AS_OF), AS_OF)
    canonical = PublicPeopleRepository(integration_database)
    directory = DirectoryPeopleRepository(integration_database)
    assert type(open_people_repository(integration_database, AS_OF)) is DirectoryPeopleRepository
    for filters, limit in product(PARITY_FILTERS, (2, 100)):
        query = PeopleQuery(sort=sort, limit=limit, **filters)
        expected = walk(lambda q, c: canonical.search_people(q, AS_OF, c), query)
        actual = walk(lambda q, c: directory.search_people(q, AS_OF, c), query)
        assert actual == expected, (filters, limit)
    # The pairing uf+office_kind must come from the SAME mandate: Ana is senator RJ / deputy SP.
    paired = PeopleQuery(sort=sort, uf="SP", office_kind="senator")
    assert [r["display_name"] for r in directory.search_people(paired, AS_OF, None)] == [
        "José Alves"
    ]


@pytest.mark.integration
def test_party_list_matches_canonical_sql_and_aliases_are_excluded(integration_database):
    populate(integration_database)
    build_dataset(integration_database, person_directory_spec(None, AS_OF), AS_OF)
    expected = PublicPeopleRepository(integration_database).list_current_political_parties(AS_OF)
    actual = DirectoryPeopleRepository(integration_database).list_current_political_parties(AS_OF)
    assert [dict(row) for row in actual] == [dict(row) for row in expected]
    names = [
        row["display_name"]
        for row in DirectoryPeopleRepository(integration_database).search_people(
            PeopleQuery(q="duplicada"), AS_OF, None
        )
    ]
    assert names == []


@pytest.mark.integration
def test_accents_match_both_ways(integration_database):
    populate(integration_database)
    build_dataset(integration_database, person_directory_spec(None, AS_OF), AS_OF)
    directory = DirectoryPeopleRepository(integration_database)
    found = {
        term: sorted(
            r["display_name"] for r in directory.search_people(PeopleQuery(q=term), AS_OF, None)
        )
        for term in ("jose", "josé", "JOSE")
    }
    assert found["jose"] == found["josé"] == found["JOSE"] == ["Jose Carlos", "José Alves"]


@pytest.mark.integration
def test_directory_row_has_one_row_per_person_with_contract_columns(integration_database):
    populate(integration_database)
    build_dataset(integration_database, person_directory_spec(None, AS_OF), AS_OF)
    rows = integration_database.execute(
        "SELECT * FROM se_liga_brasil_serving.person_directory ORDER BY display_name"
    ).fetchall()
    names = [row["display_name"] for row in rows]
    assert "Ana Lima Duplicada" not in names
    ana = next(row for row in rows if row["display_name"] == "Ana Lima")
    assert ana["uf"] == ["RJ", "SP"] and ana["office_kinds"] == ["federal_deputy", "senator"]
    assert ana["party_abbr"] == "PT" and ana["party_sort_key"] == "0PT"
    assert ana["as_of"] == AS_OF and "photo" in ana and ana["slug"]
    soren = next(row for row in rows if row["display_name"] == "Søren Ærø")
    assert soren["name_search"] == "soren aero"


@pytest.mark.integration
def test_directory_indexes_exist_and_serve_the_public_queries(integration_database):
    populate(integration_database)
    build_dataset(integration_database, person_directory_spec(None, AS_OF), AS_OF)
    table = "se_liga_brasil_serving.person_directory"
    definitions = " ".join(
        row["indexdef"]
        for row in integration_database.execute(
            "SELECT indexdef FROM pg_indexes WHERE schemaname='se_liga_brasil_serving' "
            "AND tablename LIKE 'person_directory%'"
        ).fetchall()
    )
    for expected in (
        "(party_sort_key, display_name, person_id)",
        "(state_sort_key, display_name, person_id)",
        "gin (uf)",
    ):
        assert expected in definitions
    integration_database.execute("SET LOCAL enable_seqscan=off")
    plans = {
        "party": f"SELECT person_id FROM {table} ORDER BY party_sort_key,display_name,person_id",
        "state": f"SELECT person_id FROM {table} ORDER BY state_sort_key,display_name,person_id",
        "uf": f"SELECT person_id FROM {table} WHERE uf @> ARRAY['SP']",
    }
    for label, sql in plans.items():
        plan = " ".join(
            next(iter(row.values()))
            for row in integration_database.execute("EXPLAIN " + sql).fetchall()
        )
        assert "Index" in plan or "Bitmap" in plan, (label, plan)
