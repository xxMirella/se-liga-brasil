"""Retired deputy histories expand coverage without speculative canonical links or majorities."""

import pytest

from crawlers.camara.historical_universe import register_discovered_members
from service.political_dashboard_dataset.camara_full_history import (
    historical_universe_members,
    historical_universe_partitions,
)

LEGISLATURES = {51: {"dataInicio": "1999-02-01", "dataFim": "2003-01-31"}}


def test_roster_discovery_uses_requested_scope_without_claiming_effective_status():
    people = {}
    register_discovered_members(people, [{"id": 73909, "idLegislatura": 52}], 51)
    assert people == {"73909": {"id": "73909", "legislatures": [51]}}
    assert "situacao" not in people["73909"]


def history(identifier="123", situation="Exercício"):
    return {"official_deputy_id": identifier,
            "events": [{"id": int(identifier), "idLegislatura": 51,
                        "dataHora": "1999-02-01T00:00:00", "situacao": situation,
                        "nome": "Nome registrado", "siglaPartido": "PMDB", "siglaUf": "SP"}],
            "evidence": [{"fetched_at": "2026-10-26T00:00:00+00:00", "sha256": "a" * 64}]}


def test_retired_source_person_is_included_without_creating_canonical_identity():
    members = historical_universe_members([history()], LEGISLATURES, {}, {"123": "b" * 64}, 2000)
    assert members[0]["person_id"] == "camara:123"
    assert members[0]["source_person_id"] == "123"
    assert members[0]["political_party"] == "PMDB"
    assert members[0]["official_url"].endswith("/123/historico")


def test_only_already_verified_identity_bridge_is_used_and_licensed_status_is_excluded():
    identities = {"123": {"person_id": "known-canonical-id"}}
    members = historical_universe_members([history()], LEGISLATURES, identities,
                                           {"123": "b" * 64}, 2000)
    assert members[0]["person_id"] == "known-canonical-id"
    assert historical_universe_members([history(situation="Licença")], LEGISLATURES, identities,
                                        {"123": "b" * 64}, 2000) == []
    assert historical_universe_members([history()], LEGISLATURES, identities,
                                        {"123": "b" * 64}, 2004) == []


def test_incomplete_historical_universe_never_claims_complete_chamber():
    members = historical_universe_members([history()], LEGISLATURES, {}, {"123": "b" * 64}, 2000)
    partitions = historical_universe_partitions(members, 2000, 1, 2323, "c" * 64)
    national = next(row for row in partitions if row["territory_code"] == "BR")
    assert national["coverage"] == "observed_partial"
    assert national["total"] == 1
    assert national["historical_universe_people"] == 2323
    assert national["reference_on"] == "2000-12-31"


def test_more_than_513_effective_statuses_is_rejected_before_publication():
    members = [{"uf": "SP"}] * 514
    with pytest.raises(ValueError, match="EXCEEDS_LEGAL_CAPACITY"):
        historical_universe_partitions(members, 2000, 600, 2323, "c" * 64)
