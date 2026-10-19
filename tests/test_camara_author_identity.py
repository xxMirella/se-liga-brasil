from types import SimpleNamespace

import pytest

from crawlers.camara.author_identity import author_profile_key, prepare_author_resolver
from crawlers.camara.configuration import API_BASE
from crawlers.camara.voting_normalization import normalize_individual_vote


@pytest.mark.parametrize("value", [None, "https://example.com/deputados/1",
                                   API_BASE + "deputados/1?cpf=123", API_BASE + "deputados/0"])
def test_author_identity_rejects_untrusted_or_malformed_profile_links(value):
    assert author_profile_key({"uri": value}) is None


def test_author_profiles_are_deduplicated_and_download_budget_is_explicit(monkeypatch):
    from crawlers.camara import author_identity as module

    requests = []
    rows = [{"uri": API_BASE + "deputados/1"}, {"uri": API_BASE + "deputados/2"}]

    class Acquisition:
        configuration = SimpleNamespace()

        def pages(self, path, kind):
            yield rows, None

        def json_document(self, path, kind):
            requests.append(path)
            return {}, "artifact"

    monkeypatch.setattr(module, "cached_profile_artifact", lambda *_: None)
    calls = []
    def resolve(connection, artifacts):
        calls.append(artifacts)
        return {"1": {"person_id": "canonical-person"}}
    monkeypatch.setattr(module, "resolve_voting_people", resolve)
    resolver, result = prepare_author_resolver(
        Acquisition(), None, [API_BASE + "proposicoes/10", API_BASE + "proposicoes/11"], maximum=1,
    )
    assert requests == ["deputados/1"]
    assert len(calls) == 1
    assert resolver(rows[0]) == "canonical-person"
    assert resolver(rows[1]) is None
    assert result["identity_unresolved"] == 1


@pytest.mark.parametrize(("label", "status"), [("Ausente", "absent"),
                                               ("Ausência justificada", "excused"),
                                               (None, "unknown"), ("", "unknown")])
def test_only_explicit_source_absences_are_classified(label, status):
    assert normalize_individual_vote({"tipoVoto": label}) == {
        "vote_choice": None, "participation_status": status,
    }
