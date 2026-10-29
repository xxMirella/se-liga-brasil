"""Verified legal acts to implemented-policy evidence for the governing president's party."""

import re
from datetime import date

from service.party_orientation_evidence.records import (
    PROOF_SECONDARY,
    dimension_of,
    evidence_record,
)
from service.party_orientation_model.contracts import LAYER_IMPLEMENTED, Rubric

VERIFIED_STATUS = "verificado"
NO_PARTY_PREFIX = "sem partido"
COALITION_MARK = "coalizão"
PARTY_WITH_NOTE = re.compile(r"^(?P<party>[^\s(]+)(?:\s*\(.*\))?$")
ATTRIBUTION = "party_in_government"


def governing_party(act: dict) -> str | None:
    """Acronym of the president's party, or None when the act cannot be credited to one party.

    Coalition governments (Itamar) and a president without party are not credited: the
    government is not the party's own record (descriptor N1/N5 of the rubric).
    """
    label = act["president_party"].strip()
    if label.casefold().startswith(NO_PARTY_PREFIX) or COALITION_MARK in act["government"]:
        return None
    match = PARTY_WITH_NOTE.match(label)
    return match.group("party") if match else None


def act_description(act: dict) -> str:
    return (
        f"{act['topic']} ({act['government']}). Direção {act['proposed_direction']:+d} no "
        f"indicador {act['rubric_indicator']} proposta na codificação do coletor; a existência "
        "do ato foi verificada no LexML, mas a direção ainda não teve revisão humana. "
        "Ato de governo reflete também coalizão e restrições (descritor N1)."
    )


def legal_act_records(acts: list[dict], verification: dict[str, dict], rubric: Rubric):
    """Returns the records and, for transparency, the ids that could not be converted."""
    records, skipped = [], {}
    for act in acts:
        reason = _skip_reason(act, verification.get(act["id"]))
        if reason:
            skipped[act["id"]] = reason
            continue
        acted_on = date.fromisoformat(act["date"])
        verified = verification[act["id"]]
        records.append(
            evidence_record(
                evidence_id=f"implemented:{act['id']}",
                political_party=governing_party(act),
                layer=LAYER_IMPLEMENTED,
                dimension=dimension_of(rubric, act["rubric_indicator"]),
                indicator_id=act["rubric_indicator"],
                stance=float(act["proposed_direction"]),
                source_id=f"lexml:{act['urn']}",
                source_url=verified["url"],
                source_date=acted_on,
                year_start=acted_on.year,
                year_end=acted_on.year,
                proof_level=PROOF_SECONDARY,
                attribution_basis=ATTRIBUTION,
                description=act_description(act),
                policy_reference_id=act["urn"],
            )
        )
    return records, skipped


def _skip_reason(act: dict, verified: dict | None) -> str | None:
    if verified is None or verified.get("status") != VERIFIED_STATUS:
        return "ato_nao_verificado_no_lexml"
    if act.get("proposed_direction") not in (-1, 1):
        return "direcao_nao_codificada"
    if governing_party(act) is None:
        return "ato_sem_partido_unico_do_presidente_ou_governo_de_coalizao"
    return None


def policy_conversion_notes(skipped: dict[str, str]) -> list[str]:
    return [
        "Convertidos só atos legais verificados no LexML com direção codificada (+1/-1) e partido "
        "único do presidente; direção proposta pelo coletor, sem revisão humana (nível "
        "'documented_secondary').",
        "Não convertidos: temas de projetos de lei (medem foco, não direção), itens qualitativos "
        "do CPDOC (12 itens, 7 só do PDT e quase todos anteriores a 1995: a cobertura assimétrica "
        "distorceria a comparação), eleitos/coligações do TSE (não são política implementada), "
        "plataformas presidenciais por frequência de palavras.",
        f"Atos não convertidos: {len(skipped)} ({', '.join(sorted(set(skipped.values())))}).",
    ]
