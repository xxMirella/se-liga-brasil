"""Reviewed legal baselines; uncovered local duties remain explicit gaps."""

import json
from dataclasses import asdict
from hashlib import sha256

from service.office_duties import LIMITATIONS
from service.office_duties.catalog import (
    CATALOGS,
    REVIEWED_ON,
    OfficeDuty,
    constitutional_source,
)
from service.office_duties.state_executive import state_executive_competencies

LEGAL_CATALOG_VERSION = "2026-10-18.2"
LOCAL_LIMITATION = (
    "Competências privativas locais dependem de lei orgânica e regimento não revisados."
)
GENERAL_LIMITATION = "Síntese inicial não exaustiva; não é avaliação jurídica individual."


def legal_rule(code, title, description, reference, *, scope="collective_institution"):
    return asdict(OfficeDuty(code, title, description, (constitutional_source(reference),), scope))


SEPARATION = legal_rule(
    "separation_of_powers",
    "Respeitar a separação de Poderes",
    "A competência legislativa não transfere ao parlamentar a direção da administração executiva.",
    "art. 2º",
)
RESERVED_INITIATIVE = legal_rule(
    "reserved_initiative",
    "Respeitar matérias de iniciativa reservada",
    "A apresentação e tramitação de propostas obedecem às reservas constitucionais de iniciativa.",
    "art. 61, § 1º",
    scope="individual",
)
PARLIAMENTARY_INCOMPATIBILITIES = legal_rule(
    "incompatibilities",
    "Observar incompatibilidades constitucionais",
    "Contratos, cargos e atividades sujeitos às hipóteses e exceções do art. 54, "
    "com marcos distintos de diplomação e posse; não é proibição geral de renda privada.",
    "art. 54",
    scope="individual",
)
PUBLIC_ADMINISTRATION = legal_rule(
    "public_administration_principles",
    "Observar os princípios da administração pública",
    "A atuação administrativa deve respeitar legalidade, impessoalidade, moralidade, "
    "publicidade e eficiência.",
    "art. 37, caput",
)


def build_scope_record(
    office_kind,
    jurisdiction,
    competencies,
    restrictions,
    *,
    coverage_status="reviewed_baseline",
    limitations=(),
):
    sources = {}
    for rule in (*competencies, *restrictions):
        for source in rule["sources"]:
            sources[(source["url"], source["reference"])] = source
    record = {
        "office_kind": office_kind,
        "jurisdiction": jurisdiction,
        "catalog_version": LEGAL_CATALOG_VERSION,
        "reviewed_on": REVIEWED_ON.isoformat(),
        "legal_valid_from": None,
        "legal_valid_until": None,
        "coverage_status": coverage_status,
        "competencies": list(competencies),
        "restrictions": list(restrictions),
        "sources": list(sources.values()),
        "limitations": [*LIMITATIONS, GENERAL_LIMITATION, *limitations],
    }
    record["content_sha256"] = scope_record_hash(record)
    return record


def scope_record_hash(record):
    content = {key: value for key, value in record.items() if key != "content_sha256"}
    encoded = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode()).hexdigest()


def legislative_scope_records():
    records = []
    for (office_kind, jurisdiction), catalog in CATALOGS.items():
        restrictions = [SEPARATION]
        coverage_status = "reviewed_baseline"
        if office_kind in {"federal_deputy", "senator"}:
            restrictions += [RESERVED_INITIATIVE, PARLIAMENTARY_INCOMPATIBILITIES]
        elif office_kind == "state_deputy":
            restrictions.append(
                legal_rule(
                    "state_competence",
                    "Respeitar as competências estaduais",
                    "A legislação estadual se limita às competências constitucionais do estado.",
                    "arts. 22, 24 e 25, § 1º",
                )
            )
            restrictions.append(
                legal_rule(
                    "state_incompatibilities",
                    "Observar impedimentos parlamentares",
                    "Aplicam-se os impedimentos constitucionais aos deputados estaduais; "
                    "cada hipótese exige avaliação dos fatos e das exceções.",
                    "art. 27, § 1º, e art. 54",
                    scope="individual",
                )
            )
        else:
            coverage_status = "local_law_required"
            restrictions.append(
                legal_rule(
                    "municipal_incompatibilities",
                    "Observar incompatibilidades dos vereadores",
                    "As proibições e incompatibilidades seguem a "
                    "Constituição e a lei orgânica local.",
                    "art. 29, IX",
                    scope="individual",
                )
            )
        records.append(
            build_scope_record(
                office_kind,
                jurisdiction,
                tuple(asdict(item) for item in catalog.items),
                restrictions,
                coverage_status=coverage_status,
                limitations=catalog.limitations,
            )
        )
    return records


def executive_scope_records():
    records = []
    for jurisdiction in ("SP", "RJ"):
        records.append(
            build_scope_record(
                "governor",
                jurisdiction,
                state_executive_competencies("governor", jurisdiction),
                (
                    PUBLIC_ADMINISTRATION,
                    legal_rule(
                        "other_public_office",
                        "Observar a vedação de acumulação prevista",
                        "Assumir outro cargo ou função pública pode causar perda do mandato, "
                        "ressalvada a hipótese constitucional de concurso público.",
                        "art. 28, § 1º",
                        scope="individual",
                    ),
                ),
                coverage_status="reviewed_baseline",
                limitations=(
                    "Síntese executiva parcial; competências adicionais exigem revisão local.",
                ),
            )
        )
        records.append(
            build_scope_record(
                "vice_governor",
                jurisdiction,
                state_executive_competencies("vice_governor", jurisdiction),
                (),
                coverage_status="reviewed_baseline",
                limitations=(
                    "Substituição, sucessão e atribuições dependem da constituição estadual.",
                ),
            )
        )
    for office_kind in ("mayor", "vice_mayor"):
        records.append(
            build_scope_record(
                office_kind,
                "BR",
                (),
                (PUBLIC_ADMINISTRATION,),
                coverage_status="local_law_required",
                limitations=(LOCAL_LIMITATION,),
            )
        )
    return records


def build_legal_scope_records():
    """Generate one bounded batch, including explicit records for unsupported office meanings."""
    records = legislative_scope_records() + executive_scope_records()
    records.append(
        build_scope_record(
            "senator_substitute",
            "BR",
            (),
            (
                legal_rule(
                    "exercise_requires_assumption",
                    "Distinguir suplência de exercício efetivo",
                    "A condição de suplente não prova "
                    "exercício: convocação ocorre nas hipóteses legais.",
                    "art. 56, § 1º",
                    scope="individual",
                ),
            ),
        )
    )
    records.append(
        build_scope_record(
            "district_deputy",
            "DF",
            (),
            (),
            coverage_status="local_law_required",
            limitations=(
                "Lei Orgânica do Distrito Federal e competências distritais não catalogadas.",
            ),
        )
    )
    records.append(
        build_scope_record(
            "other",
            "BR",
            (),
            (),
            coverage_status="unclassified",
            limitations=("Cargo genérico exige classificação antes de atribuir competências.",),
        )
    )
    return records
