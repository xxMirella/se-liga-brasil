"""Foco temático das plataformas de candidatos a presidente (TSE DivulgaCand 2018 e 2022).

Para cada PDF registrado, extrai o texto (pdftotext), localiza candidato/partido em consulta_cand
pelo SQ_CANDIDATO do nome do arquivo e conta ocorrências de um léxico explícito por tema, por 10 mil
palavras. É medida de SALIÊNCIA de vocabulário, não de posição: citar "privatização" para criticá-la
conta igual. Saída: derived/presidential_platform_theme_focus.json.
"""
# ruff: noqa: E501, SIM117  # hardcode-ok: textos longos de fonte e prosa metodológica

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import subprocess
import unicodedata
import zipfile
from pathlib import Path

POLICIES = Path(__file__).resolve().parents[1] / "data/political-orientation/party-model/policies"
PLATFORM_ZIP = POLICIES / "raw/tse_platforms/proposta_governo_{year}_BR.zip"
CANDIDATE_ZIP = POLICIES / "raw/tse/consulta_cand_{year}.zip"
# 2010 e 2014 ficam de fora: o número do PDF não corresponde ao SQ_CANDIDATO de consulta_cand (verificado), logo a autoria não é comprovável.
YEARS = (2018, 2022)

# Léxico transparente (radicais sem acento). Dimensão: econômica (E), sociocultural (S) ou setorial (N).
THEME_LEXICON = {
    "mercado_e_ajuste_fiscal": (
        "E",
        [
            "privatiza",
            "livre iniciativa",
            "livre mercado",
            "desburocrat",
            "equilibrio fiscal",
            "responsabilidade fiscal",
            "teto de gastos",
            "concessoes",
            "parceria publico-privada",
            "ambiente de negocios",
            "seguranca juridica",
            "reducao de impostos",
            "estado minimo",
        ],
    ),
    "estado_indutor_e_redistribuicao": (
        "E",
        [
            "bolsa familia",
            "transferencia de renda",
            "salario minimo",
            "reforma agraria",
            "desigualdade",
            "programas sociais",
            "estado indutor",
            "banco publico",
            "pre-sal",
            "politica industrial",
            "direitos trabalhistas",
            "taxacao de grandes fortunas",
            "tributacao progressiva",
            "renda basica",
            "soberania nacional",
        ],
    ),
    "seguranca_e_ordem": (
        "S",
        [
            "seguranca publica",
            "policia",
            "armas|",
            "crime|",
            "violencia urbana",
            "maioridade penal",
            "sistema prisional",
            "narcotrafico",
            "facc",
        ],
    ),
    "valores_tradicionais_e_religiao": (
        "S",
        [
            "familia",
            "valores cristaos",
            "deus|",
            "vida desde a concepcao",
            "ideologia de genero",
            "liberdade religiosa",
            "igreja",
            "tradicao",
        ],
    ),
    "direitos_e_diversidade": (
        "S",
        [
            "igualdade racial",
            "diversidade",
            "lgbt",
            "violencia contra a mulher",
            "igualdade de genero",
            "povos indigenas",
            "quilombola",
            "direitos humanos",
            "discriminacao",
            "racismo",
        ],
    ),
    "meio_ambiente_e_clima": (
        "N",
        ["meio ambiente", "clima|", "desmatamento", "sustentab", "amazonia", "energia renovavel"],
    ),
    "educacao": ("N", ["educacao", "escola", "universidade", "professor", "ensino"]),
    "saude": ("N", ["saude", "sus|", "hospital", "vacina"]),
    "corrupcao_e_transparencia": ("N", ["corrupcao", "transparencia", "probidade", "lava jato"]),
}


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def candidates_by_sequence(year: int) -> dict[str, dict]:
    result = {}
    with zipfile.ZipFile(str(CANDIDATE_ZIP).format(year=year)) as archive:
        with archive.open(f"consulta_cand_{year}_BR.csv") as raw:
            for row in csv.DictReader(
                io.TextIOWrapper(raw, encoding="latin-1", newline=""), delimiter=";"
            ):
                if row["DS_CARGO"] == "PRESIDENTE":
                    result[row["SQ_CANDIDATO"]] = {
                        "nome": row["NM_CANDIDATO"],
                        "partido": row["SG_PARTIDO"],
                        "situacao": row["DS_SIT_TOT_TURNO"],
                    }
    return result


def extract_text(pdf_bytes: bytes) -> str:
    done = subprocess.run(
        ["pdftotext", "-layout", "-", "-"],
        input=pdf_bytes,
        capture_output=True,
        timeout=120,
        check=False,
    )
    return done.stdout.decode("utf-8", errors="replace")


def term_pattern(term: str) -> str:
    """Início de palavra sempre; o sufixo | exige palavra inteira (evita casar 'armas' dentro de outra palavra; plural simples aceito)."""
    if term.endswith("|"):
        return r"\b" + re.escape(term[:-1]) + r"s?\b"
    return r"\b" + re.escape(term)


def measure_focus(text: str) -> dict:
    folded = fold(text)
    words = max(len(folded.split()), 1)
    focus = {}
    for theme, (dimension, terms) in THEME_LEXICON.items():
        hits = sum(len(re.findall(term_pattern(term), folded)) for term in terms)
        focus[theme] = {
            "dimensao": dimension,
            "ocorrencias": hits,
            "por_10mil_palavras": round(hits * 10000 / words, 1),
        }
    return {"palavras": words, "temas": focus}


def analyze_year(year: int) -> list[dict]:
    candidates = candidates_by_sequence(year)
    records = []
    with zipfile.ZipFile(str(PLATFORM_ZIP).format(year=year)) as archive:
        for name in sorted(archive.namelist()):
            match = re.search(r"BR(\d+)\.pdf$", name)
            if not match or "leiame" in name.lower():
                continue
            pdf = archive.read(name)
            candidate = candidates.get(match.group(1)) or candidates.get(match.group(1).lstrip("0"))
            record = {
                "ano": year,
                "arquivo": name,
                "sha256_pdf": hashlib.sha256(pdf).hexdigest(),
                "candidato": candidate or "nao_identificado_em_consulta_cand",
            }
            record.update(measure_focus(extract_text(pdf)))
            records.append(record)
    return records


def main() -> None:
    output = {str(year): analyze_year(year) for year in YEARS}
    path = POLICIES / "derived/presidential_platform_theme_focus.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
