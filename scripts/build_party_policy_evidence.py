"""Monta policies/parties/<PARTIDO>/party_policy_evidence.json a partir dos dados arquivados.

Só lê dados já coletados (derived/, raw/, curated/); não acessa rede nem banco. Cada bloco declara
fonte, nível de prova e tipo de afirmação. Famílias de siglas (linhagens) são AGRUPAMENTO DE LEITURA
declarado aqui, não identidade jurídica: o detalhe por sigla é preservado em `por_sigla`.
"""
# ruff: noqa: E501, SIM117  # hardcode-ok: textos longos de fonte e prosa metodológica

from __future__ import annotations

import collections
import csv
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from party_policy_evidence_catalog import (  # noqa: E402
    CPDOC_DIR,
    DERIVED,
    DIMENSION_OF_PREFIX,
    DISCLAIMER,
    EXECUTIVE_EVIDENCE,
    LINEAGES,
    MIN_PROPOSITIONS_PER_PERIOD,
    MIN_PROPOSITIONS_PER_THEME,
    NORMATIVE_GROUPS,
    PERIODS,
    POLICIES,
    PRESIDENT_PARTY_TO_LINEAGE,
    ROOT,
    SENTINELS,
    THEME_TO_INDICATORS,
)
from party_policy_expert_estimates import expert_estimates  # noqa: E402


def period_of(year: int) -> str | None:
    return next((name for name, (first, last) in PERIODS.items() if first <= year <= last), None)


def load_camara() -> list[dict]:
    path = next(DERIVED.glob("camara_party_theme_counts_*.csv"))
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def aggregate_projects(rows: list[dict], labels: set[str]) -> dict:
    mine = collections.defaultdict(collections.Counter)  # periodo -> (tema) -> n
    totals = collections.defaultdict(collections.Counter)
    by_label = collections.defaultdict(collections.Counter)
    oversight = collections.Counter()
    for row in rows:
        period = period_of(int(row["ano"]))
        if (
            period is None
            or row["metrica"] != "proposicoes_assinadas"
            or row["partido_do_autor"] not in labels
        ):
            continue
        if (
            row["grupo_de_tipo"] == "requerimento_de_informacao"
            and row["tema_oficial"] == "__total__"
        ):
            oversight[period] += int(row["contagem"])
        if row["grupo_de_tipo"] not in NORMATIVE_GROUPS:
            continue
        if row["tema_oficial"] == "__total__":
            totals[period]["n"] += int(row["contagem"])
            by_label[period][row["partido_do_autor"]] += int(row["contagem"])
        else:
            mine[period][row["tema_oficial"]] += int(row["contagem"])
    return {"themes": mine, "totals": totals, "by_label": by_label, "oversight": oversight}


def baseline_shares(rows: list[dict]) -> dict:
    themes = collections.defaultdict(collections.Counter)
    totals = collections.Counter()
    for row in rows:
        period = period_of(int(row["ano"]))
        if (
            period is None
            or row["metrica"] != "proposicoes_assinadas"
            or row["grupo_de_tipo"] not in NORMATIVE_GROUPS
        ):
            continue
        if row["tema_oficial"] == "__total__":
            totals[period] += int(row["contagem"])
        else:
            themes[period][row["tema_oficial"]] += int(row["contagem"])
    return {"themes": themes, "totals": totals}


def summarize_period(period: str, mine: dict, baseline: dict) -> dict:
    total = mine["totals"][period]["n"]
    if total < MIN_PROPOSITIONS_PER_PERIOD:
        return {
            "proposicoes_normativas": total,
            "status": "amostra_insuficiente",
            "por_sigla": dict(mine["by_label"][period]),
        }
    ranked, buckets = [], collections.Counter()
    for theme, count in mine["themes"][period].items():
        share = count / total
        base = baseline["themes"][period][theme] / baseline["totals"][period]
        indicators = THEME_TO_INDICATORS.get(theme, [])
        for code in indicators:
            buckets[DIMENSION_OF_PREFIX[code[0]]] += count
        if count >= MIN_PROPOSITIONS_PER_THEME and theme not in SENTINELS:
            ranked.append(
                {
                    "tema_oficial": theme,
                    "proposicoes": count,
                    "parcela": round(share, 3),
                    "parcela_de_todos_os_partidos": round(base, 3),
                    "razao_foco": round(share / base, 2) if base else None,
                    "indicadores_rubrica_por_saliencia": indicators,
                }
            )
    ranked.sort(key=lambda item: -item["proposicoes"])
    return {
        "proposicoes_normativas": total,
        "status": "ok",
        "por_sigla": dict(mine["by_label"][period]),
        "requerimentos_de_informacao": mine["oversight"][period],
        "temas_mais_frequentes": ranked[:8],
        "temas_com_maior_razao_foco": sorted(ranked, key=lambda i: -(i["razao_foco"] or 0))[:5],
        "incidencias_por_dimensao_da_rubrica": dict(buckets),
    }


def senate_counts(labels: set[str]) -> dict:
    path = next(DERIVED.glob("senado_party_type_counts_*.csv"))
    result = collections.defaultdict(collections.Counter)
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            period = period_of(int(row["ano"]))
            if period and row["partido_do_autor"] in labels:
                result[period][row["grupo_de_tipo"]] += int(row["contagem"])
    return {period: dict(counter) for period, counter in result.items()}


def executive_classifications() -> list[dict]:
    return json.loads(EXECUTIVE_EVIDENCE.read_text())["records"]


def government_record_for(year: int, records: list[dict]) -> dict | None:
    match = next(
        (r for r in records if r["institution"] == "presidency" and year in r["valid_years"]), None
    )
    if not match:
        return None
    return {
        "executive_source_id": match["executive_source_id"],
        "categoria_academica": match["category"],
        "fonte": match.get("source_title"),
        "doi": match.get("source_doi"),
        "tipo_de_afirmacao": "interpretacao_academica",
        "limite": "classifica o discurso/governo estudado, não o partido nem cada política",
    }


def occupied_governments(tse_labels: set[str], elected: dict, records: list[dict]) -> dict:
    presidents, governors, capitals, totals, seats = [], {}, {}, {}, {}
    for year, block in sorted(elected.items()):
        for office in block["executivos_estaduais_e_federal"]:
            if office["partido"] not in tse_labels:
                continue
            if office["cargo"] == "PRESIDENTE":
                presidents.append(
                    {
                        "eleicao": int(year),
                        "nome": office["nome"],
                        "classificacao_do_governo": government_record_for(int(year) + 1, records),
                    }
                )
            else:
                governors.setdefault(year, []).append(office["uf"])
        mine_capitals = [c for c in block["prefeitos_de_capitais"] if c["partido"] in tse_labels]
        if mine_capitals:
            capitals[year] = [f"{c['municipio']}/{c['uf']}" for c in mine_capitals]
        mayors = sum(
            n
            for p, n in block["vagas_por_cargo_e_partido"].get("PREFEITO", {}).items()
            if p in tse_labels
        )
        if "PREFEITO" in block["vagas_por_cargo_e_partido"]:
            totals[year] = mayors
        seats[year] = {
            office: sum(n for p, n in by_party.items() if p in tse_labels)
            for office, by_party in block["vagas_por_cargo_e_partido"].items()
            if office in {"SENADOR", "DEPUTADO FEDERAL"}
        }
    return {
        "presidencia_eleicoes_vencidas": presidents,
        "governadores_eleitos_por_eleicao": governors,
        "prefeituras_de_capitais_por_eleicao": capitals,
        "prefeitos_eleitos_total_por_eleicao": totals,
        "cadeiras_eleitas_senado_e_camara_por_eleicao": {y: s for y, s in seats.items() if s},
        "fonte": "TSE consulta_cand (partido na candidatura; situação final de totalização)",
        "nivel_de_prova": "A_dado_oficial_agregado_localmente",
        "limites": [
            "cadeiras de deputado federal de 2002 e 2006 e de senador de 2002 e 2006 estão incompletas na fonte (rótulos de situação diferentes)",
            "2006: o arquivo do TSE não traz situação final da eleição presidencial (#NULO#)",
            "prefeituras de capitais de 2000 e 2004 incompletas (segundo turno sem rótulo eleito comparável)",
            "partido da candidatura não prova filiação contínua nem adesão programática do governante",
        ],
    }


def presidential_support(tse_labels: set[str], coalitions: dict) -> list[dict]:
    support = []
    for year, candidates in sorted(coalitions.items()):
        chosen = [
            c
            for c in candidates
            if tse_labels & set(c["partidos_da_coligacao"])
            or c["partido_do_candidato"] in tse_labels
        ]
        support += [
            {
                "eleicao": int(year),
                "candidato": c["candidato"],
                "partido_do_candidato": c["partido_do_candidato"],
                "resultado_1o_turno": c["resultado"],
                "forma": "proprio" if c["partido_do_candidato"] in tse_labels else "coligacao",
            }
            for c in chosen
        ]
        if not chosen:
            support.append(
                {
                    "eleicao": int(year),
                    "candidato": None,
                    "forma": "sem_apoio_formal_identificado_no_1o_turno",
                }
            )
    return support


def platform_focus(tse_labels: set[str]) -> list[dict]:
    data = json.loads((DERIVED / "presidential_platform_theme_focus.json").read_text())
    return [
        {
            "eleicao": int(year),
            "candidato": r["candidato"]["nome"],
            "palavras_no_pdf": r["palavras"],
            "ocorrencias_por_10mil_palavras": {
                t: v["por_10mil_palavras"] for t, v in r["temas"].items()
            },
            "aviso": "extração de PDF muito curta: provável PDF de imagem, sem OCR"
            if r["palavras"] < 200
            else None,
        }
        for year, items in data.items()
        for r in items
        if isinstance(r["candidato"], dict) and r["candidato"]["partido"] in tse_labels
    ]


def acts_for_lineage(lineage: str, acts: list[dict], verified: dict) -> list[dict]:
    out = []
    for act in acts:
        president = act["president_party"]
        credited = PRESIDENT_PARTY_TO_LINEAGE.get(president.split(" ")[0].strip("()"))
        if credited != lineage:
            continue
        check = verified[act["id"]]
        out.append(
            {
                **act,
                "verificacao_lexml": check["status"],
                "titulo_na_fonte": check.get("titulo_retornado"),
                "url": check["url"],
                "tipo_de_afirmacao": "fato_o_ato_existe_e_foi_sancionado_na_data;_direcao_e_codificacao_proposta_pelo_agente",
                "atribuicao": "sancionada_em_governo_cujo_presidente_era_filiado_a_este_partido;_nao_prova_iniciativa_do_partido",
                "nivel_de_prova": "A_documento_primario_verificado"
                if check["status"] == "verificado"
                else "D_nao_verificado",
            }
        )
    return out


def qualitative_for(lineage: str) -> list[dict]:
    items = json.loads((POLICIES / "curated/qualitative_items.json").read_text())
    out = []
    for item in items:
        if lineage in item["party_ids"]:
            path = CPDOC_DIR / item["source"]
            digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
            out.append(
                {**item, "source_sha256": digest, "source_local_path": str(path.relative_to(ROOT))}
            )
    return out


def special_notes(lineage: str) -> list[str]:
    notes = {
        "PCdoB": [
            "Catálogo do projeto: PCdoB tem nota só em 2018 (1,92) e 2022 (1,78); demais anos ficam sem classificação por falta de onda do survey, não por falta de evidência de posição."
        ],
        "PDT": [
            "Hipótese da usuária (direita) e classificação atual (esquerda) tratadas sem conclusão prévia; ver docs/partidos-politicas-e-atuacao.md."
        ],
    }
    return notes.get(lineage, [])


def build_party(lineage: str, shared: dict) -> dict:
    camara_labels, tse_labels, expert_columns, power_row = LINEAGES[lineage]
    project_data = aggregate_projects(shared["camara"], set(camara_labels))
    periods = {p: summarize_period(p, project_data, shared["baseline"]) for p in PERIODS}
    return {
        "schema_version": "party_policy_evidence.v1",
        "gerado_em": date.today().isoformat(),
        "party_id": lineage,
        "agrupamento_de_siglas": {
            "camara": camara_labels,
            "tse": tse_labels,
            "aviso": "agrupamento de leitura; PL(1985-2006), PR(2006-2019) e PL(2019+) são siglas distintas no detalhe por_sigla",
        },
        "aviso_sobre_temas": DISCLAIMER,
        "notas": special_notes(lineage),
        "projetos_de_autoria_camara": {
            "fonte": "Câmara dos Deputados, arquivos proposicoesAutores/Temas/proposicoes (CSV anual)",
            "unidade": "proposições NORMATIVAS (PL, PLP, PEC) com ao menos um deputado do partido entre os autores; partido registrado pela Câmara na autoria",
            "nivel_de_prova": "A_dado_oficial_agregado_localmente",
            "periodos": periods,
        },
        "projetos_de_autoria_senado": {
            "fonte": "Senado, materia/pesquisa/lista (campo Autor: primeiro senador e partido)",
            "contagem_por_periodo_e_tipo": senate_counts(set(camara_labels)),
            "limite": "sem tema oficial na listagem; só primeiro autor de cada matéria; 'e outros' não decomposto",
        },
        "governos_ocupados": occupied_governments(
            set(tse_labels), shared["elected"], shared["executive_records"]
        ),
        "apoio_presidencial_1o_turno": presidential_support(set(tse_labels), shared["coalitions"]),
        "apoio_presidencial_limites": [
            "composição de coligação do TSE pode estar incompleta (1994 sem coligação na fonte; 1998 lista só 'PDT / PT' para Lula, mas o CPDOC registra PCdoB também nessa frente)",
            "só 1º turno: apoio declarado no 2º turno não aparece aqui (ex.: partidos que apoiaram Lula ou Bolsonaro depois de eliminados)",
            "coligação formal não prova afinidade programática",
        ],
        "plataformas_presidenciais_tse_2018_2022": platform_focus(set(tse_labels)),
        "estimativas_externas": expert_estimates(expert_columns, power_row),
        "politicas_implementadas_em_governos_do_presidente_filiado": acts_for_lineage(
            lineage, shared["acts"], shared["verified"]
        ),
        "itens_qualitativos_de_fonte_secundaria": qualitative_for(lineage),
    }


def main() -> None:
    shared = {
        "camara": load_camara(),
        "elected": json.loads((DERIVED / "tse_elected_offices.json").read_text()),
        "coalitions": json.loads((DERIVED / "presidential_coalition_support.json").read_text()),
        "executive_records": executive_classifications(),
        "acts": json.loads((POLICIES / "curated/legal_acts.json").read_text()),
        "verified": {
            v["id"]: v for v in json.loads((DERIVED / "legal_acts_verified.json").read_text())
        },
    }
    shared["baseline"] = baseline_shares(shared["camara"])
    for lineage in LINEAGES:
        target = POLICIES / "parties" / lineage / "party_policy_evidence.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(build_party(lineage, shared), ensure_ascii=False, indent=1))
        print(lineage, target.stat().st_size)


if __name__ == "__main__":
    main()
