"""Extract point evidence of legislative exercise without inferring continuous seats."""

from xml.etree import ElementTree

RECORDED_VOTE_LABELS = frozenset({"Sim", "Não", "Abstenção", "Presidente"})
UNREPORTED_PARTIES = frozenset({"", "Sem registro", "Não informado", "Semregistro"})


def parse_dated_exercise_observations(content, source_url, period_start, period_end_exclusive):
    root = ElementTree.fromstring(content)
    observations = []
    for voting in root.findall(".//Votacoes/Votacao"):
        observed_on = voting.findtext("DataSessao") or ""
        if not period_start <= observed_on < period_end_exclusive:
            continue
        for member in voting.findall(".//VotoParlamentar"):
            if member.findtext("Voto") not in RECORDED_VOTE_LABELS:
                continue
            observations.append(dated_exercise_observation(member, voting, source_url))
    return observations


def dated_exercise_observation(member, voting, source_url):
    source_political_party = member.findtext("SiglaPartido") or ""
    return {
        "source_person_id": member.findtext("CodigoParlamentar"),
        "name": member.findtext("NomeParlamentar"),
        "uf": member.findtext("SiglaUF"),
        "observed_on": voting.findtext("DataSessao"),
        "voting_id": voting.findtext("CodigoSessaoVotacao"),
        "vote": member.findtext("Voto"),
        "source_political_party": source_political_party,
        "political_party_status": (
            "unreported"
            if source_political_party in UNREPORTED_PARTIES
            else "reported_in_voting_record_not_verified_affiliation"
        ),
        "source_url": source_url,
        "evidence_kind": "dated_recorded_vote",
        "limitation": "Comprova registro de atuação nesta data; não prova mandato contínuo, "
        "totalidade da composição ou filiação atualizada durante todo o ano.",
    }
