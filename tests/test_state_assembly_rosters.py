"""Official roster completeness must not depend on canonical identity matches."""

import pytest

from crawlers.alerj.roster import parse_current_roster as parse_alerj
from crawlers.almg.roster import parse_current_roster as parse_almg
from service.ingestion.contracts import IngestionError
from service.state_assembly_rosters.aggregation import aggregate_current_roster
from service.state_assembly_rosters.identities import verified_subject_identities


def card(identifier, leader=False):
    css = "controle_deputado lider" if leader else "controle_deputado"
    return (
        f'<div class="{css}"><div class="partido">PL</div><div class="nome">'
        f'<a href="/Deputados/PerfilDeputado/{identifier}">Pessoa {identifier}</a></div></div>'
    )


def test_alerj_leadership_cards_are_counted_and_total_is_verified():
    heading = "<h2>13º Legislatura (2023 – 2027)<span> 2 deputados</span></h2>"
    rows = parse_alerj((heading + card(1) + card(2, leader=True)).encode())
    assert len(rows) == 2
    with pytest.raises(IngestionError, match="TOTAL_MISMATCH"):
        parse_alerj((heading + card(1)).encode())


def test_official_roster_counts_source_qualified_people_without_false_profile_links():
    members = [
        {"provider_subject_id": "1", "name": "Pessoa A", "political_party": "União Brasil"},
        {"provider_subject_id": "2", "name": "Pessoa B", "political_party": "PL"},
    ]
    identity = {"1": {"person_id": "verified-uuid", "source_record_id": "proof"}}
    evidence = {"url": "https://official.example", "fetched_at": "2026-10-23T22:00:00+00:00"}
    partition = aggregate_current_roster(members, "alesp", "SP", evidence, identity)
    assert partition["total"] == 2
    assert partition["canonical_roster_matches"] == 1
    assert {row["person_id"] for row in partition["members"]} == {"verified-uuid", "alesp:deputy:2"}
    assert sum(row["count"] for row in partition["political_parties"]) == 2
    assert partition["snapshot_on"] == "2026-10-23"
    assert {row["abbreviation"] for row in partition["political_parties"]} == {"UNIÃO", "PL"}


def test_roster_duplicate_subjects_and_unverified_identity_bridges_are_rejected():
    members = [{"provider_subject_id": "1", "name": "Pessoa", "political_party": "PL"}]
    evidence = {"fetched_at": "2026-10-23T22:00:00+00:00"}
    with pytest.raises(ValueError, match="DUPLICATE"):
        aggregate_current_roster(members * 2, "alerj", "RJ", evidence)
    resolutions = [
        {
            "status": "matched",
            "person_id": "unverified",
            "official_subjects": [{"source_subject_id": "1"}],
        }
    ]
    assert verified_subject_identities(resolutions, {}) == {}


def test_minas_current_endpoint_rejects_empty_or_changed_schema():
    assert parse_almg(b'{"list":[{"id":1,"nome":"Pessoa","partido":"PT"}]}')[0]["name"] == "Pessoa"
    with pytest.raises(IngestionError, match="SCHEMA_CHANGED"):
        parse_almg(b'{"list":[]}')


def test_generic_regeneration_preserves_complete_official_roster():
    from service.state_assembly_rosters.aggregation import preserve_official_assembly_rosters

    raw = {"territory_code": "SP", "institution_code": "alesp", "total": 89}
    complete = {
        **raw,
        "total": 94,
        "aggregation_basis": "verified_current_official_assembly_roster",
    }
    assert preserve_official_assembly_rosters([raw], [{"payload": complete}]) == [complete]


def test_district_government_cannot_be_published_as_state_government():
    from datetime import date

    from service.political_dashboard_dataset.executive import build_annual_executive_partitions

    source = {
        "territory_code": "DF",
        "institution_code": "state_government",
        "year_start": 2026,
        "year_end": 2026,
        "date_precision": "year",
        "name": "Pessoa",
    }
    with pytest.raises(ValueError, match="TERRITORY_INSTITUTION_MISMATCH"):
        build_annual_executive_partitions([source], 2026, date(2026, 10, 23))


def test_generic_assembly_history_includes_cldf_outside_initial_sp_rj_mapping():
    from datetime import date

    from service.political_dashboard.contracts import DashboardQuery
    from service.political_dashboard_dataset.query import annual_history

    query = DashboardQuery("DF", date(2026, 10, 23), level="state")
    rows = [
        {
            "year": 2026,
            "territory_code": "DF",
            "institution_code": "cldf",
            "total": 24,
            "office_kinds": ["district_deputy"],
        }
    ]
    history = annual_history(rows, query, 2026)[-1]
    assert history["assembly_observations"] == 24
    assert history["documented_records"] == 24
    assert history["government_observations"] == 0


def test_parana_all_officers_are_included_and_contact_links_not_duplicated():
    from crawlers.alep.roster import parse_current_roster

    cards = "".join(
        f'<a href="https://www.assembleia.pr.leg.br/deputados/perfil/{i}">'
        f'<h3>Pessoa {i}</h3><p class="text-gray-500 text-sm italic">PL</p></a>'
        for i in range(54)
    )
    assert len(parse_current_roster(cards.encode())) == 54
    with pytest.raises(IngestionError, match="EXPECTED_54"):
        parse_current_roster(cards.replace("Pessoa 0", "").encode())


def test_santa_catarina_card_requires_name_party_and_profile():
    from crawlers.alesc.roster import parse_current_roster

    def card_sc(i):
        return (
            f'<article class="lab-card-team"><a href="https://www.alesc.sc.gov.br/deputado/{i}/">'
            f'<h3 class="lab-title-news">Pessoa {i}</h3><span class="lab-button">PT</span>'
            "</a></article>"
        )

    assert len(parse_current_roster("".join(card_sc(i) for i in range(40)).encode())) == 40
    with pytest.raises(IngestionError, match="CARD_INVALID"):
        parse_current_roster(card_sc(1).replace("lab-title-news", "changed-class").encode())


def test_pernambuco_deduplicates_two_display_modes_and_verifies_declared_total():
    from crawlers.alepe.roster import parse_current_roster

    card = (
        '<a href="/parlamentar/pessoa" class="parlamentares-list-a">'
        '<h2 class="title parlamentares-nome">Pessoa</h2>'
        '<span class="subtitle parlamentares-partido">PL</span></a>'
    )
    heading = '<span class="numbers">1</span> Deputados do'
    assert len(parse_current_roster((heading + card * 2).encode())) == 1
    with pytest.raises(IngestionError, match="DECLARED_TOTAL_MISMATCH"):
        parse_current_roster((heading.replace(">1<", ">2<") + card).encode())


def test_maranhao_does_not_count_licensed_deputies_as_current_seats():
    from crawlers.alema.roster import parse_current_roster

    def card_ma(name):
        return (
            f'<h3 class="news-card-title"><a href="https://official/{name}">{name}</a></h3>'
            '<p class="news-card-chapeu">PT</p>'
        )

    html = card_ma("Current") + "<!-- Exibir deputados licenciados -->" + card_ma("Licensed")
    rows = parse_current_roster(html.encode())
    assert [row["name"] for row in rows] == ["Current"]
    evidence = {"fetched_at": "2026-10-24T13:00:00+00:00"}
    partition = aggregate_current_roster(rows, "alema", "MA", evidence)
    assert partition["coverage"] == "observed_partial"
    assert partition["expected_seats"] == 42
    assert partition["total"] == 1


def test_mato_grosso_rejects_incomplete_current_directory():
    from crawlers.almt.roster import parse_current_roster
    from service.ingestion.contracts import IngestionError

    with pytest.raises(IngestionError, match="EXPECTED_24"):
        parse_current_roster(b'<h6 class="card-title fw-semibold fs-14">Name</h6>')


def test_para_profile_keys_must_correspond_to_every_card():
    from crawlers.alepa.roster import parse_current_roster
    from service.ingestion.contracts import IngestionError

    cards = "<div class='card-info'><span>Deputado</span><span>Name</span><p>PT</p>" * 41
    with pytest.raises(IngestionError, match="PROFILE_KEYS_INVALID"):
        parse_current_roster(("'stateObject':{'keys':['1','2']}" + cards).encode())


def test_rondonia_profile_name_must_match_directory_member():
    from crawlers.alero.roster import parse_profile_party
    from service.ingestion.contracts import IngestionError

    profile = (
        '<h1 class="text-xl font-bold text-sky-700">Other person</h1>'
        '<p class="text-gray-500 text-xs">Partido Liberal</p>'
    )
    with pytest.raises(IngestionError, match="IDENTITY_OR_PARTY_MISSING"):
        parse_profile_party(profile.encode(), "Directory member")


def test_ms_groups_parties_without_absorbing_next_group():
    from crawlers.alems.roster import parse_current_roster

    groups = []
    for political_party, identifiers in [("PT", range(1, 13)), ("PL", range(13, 25))]:
        groups.append('<div class="party"><div class="party-name">' + political_party + "</div>")
        groups.extend(
            f'<a class="party-deputy" href="/Deputados/Visualizar/{identifier}">'
            f'<div class="">Person{identifier}</div></a>'
            for identifier in identifiers
        )
    members = parse_current_roster("".join(groups).encode())
    assert len(members) == 24
    assert [row["political_party"] for row in members].count("PT") == 12
    assert [row["political_party"] for row in members].count("PL") == 12


def test_registered_active_members_cannot_exceed_simultaneous_state_seats():
    members = [
        {
            "provider_subject_id": str(identifier),
            "name": f"Person{identifier}",
            "political_party": "PT",
        }
        for identifier in range(33)
    ]
    with pytest.raises(ValueError, match="EXCEEDS_SIMULTANEOUS_SEAT_CAPACITY"):
        aggregate_current_roster(members, "aleal", "AL", {})


def test_nopaper_inactive_fieldset_does_not_enter_current_composition():
    from datetime import date

    from crawlers.nopapercloud.roster import parse_current_roster

    def member(identifier):
        return (
            f"<a href='parlamentar.aspx?id={identifier}' class='kt-widget__username pb-1'>"
            f"Person{identifier}</a><span class='kt-widget__username pt-0'><small>(PT)</small>"
        )

    payload = (
        '<h5 id="ContentPlaceHolder1_legislatura_data">01/02/2023 a 31/01/2027</h5>'
        "<div class='custom-fieldset'><div class='custom-legend legend-pill'>Ativo</div>"
        + member(1)
        + "<div class='custom-fieldset'><div class='custom-legend legend-pill'>Inativo</div>"
        + member(2)
    )
    members = parse_current_roster(
        payload.encode(), "https://official.example/spl/", 1, reference=date(2026, 10, 24)
    )
    assert [row["provider_subject_id"] for row in members] == ["1"]


def test_ceara_licensed_titular_excluded_and_substitute_retained():
    from crawlers.alece.roster import parse_current_roster

    def member(identifier, licensed=False):
        css = " licenciado" if licensed else ""
        return (
            f'<div class="deputado_card{css}"><p class="deputado_card--nome s-font-1">'
            f'<a href="https://www.al.ce.gov.br/deputados/{identifier}">Person{identifier}</a></p>'
            '<p class="deputado_card--partido s-font-1">PT</p></div>'
        )

    payload = member(0, licensed=True) + "".join(member(i) for i in range(1, 47))
    members = parse_current_roster(payload.encode())
    assert len(members) == 46
    assert all(row["name"] != "Person0" for row in members)
    assert members[-1]["name"] == "Person46"


def test_sapl_active_registry_is_not_individual_exercise_confirmation():
    evidence = {"url": "https://sapl.al.pi.leg.br", "fetched_at": "2026-10-24T13:00:00Z"}
    members = [{"provider_subject_id": "1", "name": "Person", "political_party": "PT"}]
    partition = aggregate_current_roster(members, "alepi", "PI", evidence)
    assert partition["coverage"] == "observed_active_registry"
    assert partition["aggregation_basis"] == (
        "official_active_legislature_registry_not_individual_exercise_confirmation"
    )
    assert partition["coverage_limitation"] == "active_registry_not_individually_confirmed_exercise"


def test_rr_reconciliation_needs_replacement_and_contemporaneous_government_proof():
    from crawlers.alrr.reconciliation import GOVERNOR_ID, reconcile_current_directory

    members = [
        (GOVERNOR_ID, "Soldado Sampaio"),
        ("https://al.rr.leg.br/deputados/rogerio-da-silva-borges/", "Rogério da Silva Borges"),
    ]
    members.extend((f"https://al.rr.leg.br/deputados/{i}/", f"Person{i}") for i in range(23))
    directory = "Deputados Estaduais" + "".join(
        '<div class="wpb_column vc_column_container vc_col-sm-3 ">'
        f'<a href="{url}"></a><h4>{name}</h4><p>PT</p></div>'
        for url, name in members
    )
    replacement = (
        "Rogério Borges assume a vaga deixada por Soldado Sampaio; novamente temos 24 deputados"
    ).encode()
    government = (
        b"19 de outubro de 2026. O governador Soldado Sampaio recebeu nesta quinta-feira, 15"
    )
    with pytest.raises(IngestionError, match="OCTOBER_GOVERNMENT_OBSERVATION_MISSING"):
        reconcile_current_directory(directory.encode(), replacement, b"Old government observation")
    reconciled, excluded = reconcile_current_directory(directory.encode(), replacement, government)
    assert len(reconciled) == 24
    assert excluded["provider_subject_id"] == GOVERNOR_ID
    assert any(row["name"] == "Rogério da Silva Borges" for row in reconciled)


def test_amapa_migration_directory_keeps_limitation_and_has_no_snapshot():
    members = [
        {"provider_subject_id": str(i), "name": f"Person{i}", "political_party": "PT"}
        for i in range(24)
    ]
    partition = aggregate_current_roster(
        members, "alap", "AP", {"fetched_at": "2026-10-26T13:00:00Z"}
    )
    assert partition["snapshot_on"] is None
    assert partition["coverage"] == "observed_partial"
    assert partition["coverage_limitation"] == "official_portal_migration_updates_may_be_delayed"


def test_rn_source_projects_only_parliamentary_fields_and_uses_dated_affiliation():
    import json
    from datetime import date

    from crawlers.alrn.roster import parse_current_roster

    rows = [
        {
            "id": i,
            "nomeParlamentar": f"DEPUTADO Person{i}",
            "pessoa": {"cpf": "private-fixture-must-not-project"},
            "vigencia": {"inicio": "2023-02-01", "fim": "2027-01-31"},
            "filiacoes": [
                {
                    "vigencia": {"inicio": "2023-02-01", "fim": "2026-03-31"},
                    "partido": {"nome": "PSDB"},
                },
                {"vigencia": {"inicio": "2026-04-01", "fim": None}, "partido": {"nome": "PL"}},
            ],
        }
        for i in range(24)
    ]
    members = parse_current_roster(json.dumps({"dados": rows}), date(2026, 10, 26))
    assert len(members) == 24
    assert all(row["political_party"] == "PL" for row in members)
    assert all(set(row) == {"provider_subject_id", "name", "political_party"} for row in members)
    assert "private-fixture" not in json.dumps(members)


def test_rn_does_not_select_elected_future_term():
    from datetime import date

    from crawlers.alrn.roster import valid_on

    assert not valid_on({"inicio": "2027-02-01", "fim": "2031-01-31"}, date(2026, 10, 26))


def test_alagoas_dedicated_legislature_excludes_explicit_non_exercising_section():
    from crawlers.aleal.roster import BOUNDARY, parse_current_roster

    def member(identifier):
        return (
            f'<tr><td><a href="https://sapl.al.al.leg.br/parlamentar/{identifier}">'
            f"Person{identifier}</a><p>Partido: MDB</p></td></tr>"
        )

    payload = "20ª LEGISLATURA" + "".join(member(i) for i in range(27)) + BOUNDARY + member(99)
    members = parse_current_roster(payload.encode())
    assert len(members) == 27
    assert all(row["provider_subject_id"] != "99" for row in members)
