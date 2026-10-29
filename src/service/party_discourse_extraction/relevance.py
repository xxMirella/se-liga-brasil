"""Keyword pre-filter: cheap and transparent, it only decides which passages reach the model."""

import unicodedata
from dataclasses import dataclass

# Stems without accents; a hit means "worth reading", never a classification.
KEYWORDS_BY_INDICATOR: dict[str, tuple[str, ...]] = {
    "E1": ("privatiz", "estatal", "estatiz", "empresa publica", "concessao", "petrobras"),
    "E2": ("assistencia social", "bem-estar", "politica social", "saude publica", "sus ", "renda"),
    "E3": ("tribut", "imposto", "carga fiscal", "taxacao", "contribuic"),
    "E4": ("trabalhis", "sindic", "salario minimo", "direitos trabalh", "emprego", "clt"),
    "E5": ("previdenc", "aposentador", "pensao"),
    "E6": ("livre iniciativa", "concorrenc", "regulac", "desregulament", "mercado", "burocra"),
    "E7": ("gasto publico", "deficit", "orcamento", "responsabilidade fiscal", "teto de gastos"),
    "E8": ("reforma agraria", "terra", "propriedade", "latifund", "moradia"),
    "E9": ("comercio exterior", "capital estrangeiro", "abertura comercial", "protecionis"),
    "C1": ("racis", "igualdade", "discriminac", "minoria", "indigen", "lgbt", "mulher", "genero"),
    "C2": ("aborto", "familia", "sexualidade", "drogas", "costumes", "vida desde"),
    "C3": ("religi", "laico", "deus", "igreja"),
    "C4": ("seguranca publica", "policia", "penal", "criminal", "maioridade", "encarcer"),
    "C5": ("armas", "armamento", "desarmamento"),
    "C6": ("imigra", "nacionalis", "identidade cultural", "refugiad"),
    "C7": ("meio ambiente", "ambiental", "clima", "desmatament", "sustentab", "amazonia"),
    "C8": ("soberania", "politica externa", "multilateral", "onu", "mercosul", "integracao"),
    "C9": ("liberdade de expressao", "imprensa", "liberdades civis", "direitos humanos", "censura"),
    "G1": ("democracia", "eleicoes livres", "pluralismo", "multipartidar", "estado de direito"),
    "G2": ("oposicao", "legitimidade", "resultado eleitoral", "alternancia"),
    "G3": ("violencia politica", "milicia", "paramilitar", "terroris"),
    "G4": ("golpe", "ruptura", "intervencao militar", "ditadura", "autoritar"),
}
MIN_WORDS = 15


@dataclass(frozen=True)
class RelevanceResult:
    is_relevant: bool
    indicator_hints: tuple[str, ...]


def fold_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def assess_relevance(text: str) -> RelevanceResult:
    if len(text.split()) < MIN_WORDS:
        return RelevanceResult(False, ())
    folded = fold_accents(text)
    hints = tuple(
        code
        for code, stems in KEYWORDS_BY_INDICATOR.items()
        if any(stem in folded for stem in stems)
    )
    return RelevanceResult(bool(hints), hints)
