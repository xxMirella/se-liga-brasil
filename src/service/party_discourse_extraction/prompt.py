"""Versioned prompt and response schema; any wording change must bump PROMPT_VERSION."""

from service.party_discourse_extraction.rubric_indicators import RubricIndicator

PROMPT_VERSION = "discourse-extraction.v1"
DIRECTIONS = ("-1", "0", "+1", "nao_se_aplica")
COMMITMENT_TYPES = ("compromisso_concreto", "generico")
MAX_QUOTE_CHARACTERS = 400

INSTRUCTIONS = f"""Você codifica trechos de documentos oficiais de partidos políticos brasileiros \
(estatutos, programas, manifestos) usando uma rubrica fixa. O partido está oculto: não tente \
adivinhá-lo e não use conhecimento externo sobre ele.

Regras:
1. Considere SOMENTE o que o trecho afirma de forma explícita. Não infira intenções.
2. Para cada posição explícita sobre algum indicador da rubrica, devolva um item. Se o trecho não \
trata de nenhum indicador, devolva a lista vazia. Regras internas de organização partidária \
(filiação, convenções, finanças) não são posição ideológica: devolva a lista vazia.
3. "quote" deve ser uma cópia EXATA, palavra por palavra, de um pedaço contínuo do trecho \
(até {MAX_QUOTE_CHARACTERS} caracteres), sem corrigir, resumir ou traduzir.
4. "direction" é o lado da posição expressa segundo os polos do indicador: "-1" polo negativo, \
"+1" polo positivo, "0" posição equilibrada ou mista, "nao_se_aplica" se o trecho menciona o \
tema sem tomar posição.
5. "strength": 1 menção passageira; 2 posição clara; 3 posição central e enfática.
6. "commitment_type": "compromisso_concreto" se promete ou define medida, regra ou ação \
verificável; "generico" se é valor, princípio ou intenção ampla.
7. Marcadores como [PARTIDO], [LIDERANÇA] e [LINK] substituem nomes omitidos de propósito.

Rubrica (código — tema; polo -1; polo +1):"""


def build_system_instruction(indicators: tuple[RubricIndicator, ...]) -> str:
    lines = [
        f"{item.code} — {item.label}; -1: {item.pole_negative}; +1: {item.pole_positive}"
        for item in indicators
    ]
    return INSTRUCTIONS + "\n" + "\n".join(lines)


def build_response_schema(indicators: tuple[RubricIndicator, ...]) -> dict:
    item_properties = {
        "indicator": {"type": "string", "enum": [item.code for item in indicators]},
        "direction": {"type": "string", "enum": list(DIRECTIONS)},
        "strength": {"type": "integer", "minimum": 1, "maximum": 3},
        "commitment_type": {"type": "string", "enum": list(COMMITMENT_TYPES)},
        "quote": {"type": "string"},
    }
    return {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": item_properties,
                    "required": list(item_properties),
                },
            }
        },
        "required": ["items"],
    }


def build_user_text(segment_text: str) -> str:
    return f'Trecho:\n"""\n{segment_text}\n"""'
