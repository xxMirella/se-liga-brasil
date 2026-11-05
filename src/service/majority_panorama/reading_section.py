"""The "Como ler" section: three disclosures that say how to read, and not to over-read."""

from service.majority_panorama.blocs import BLOC_BY_KEY
from service.majority_panorama.selection import series_first_year
from web_components import render_disclosure
from web_components.escaping import escape_text

COMPARISON_PATH = "/comparacao-de-classificacoes"
INDEPENDENT_BLOCS_SENTENCE = (
    "Cada partido entra no bloco que a classificação ideológica do catálogo do Se Liga lhe "
    "atribui para o ano: Esquerda, Centro, Direita ou Extrema direita. Três grupos ficam fora "
    "dessa escala e não entram na conta do maior bloco: “{undetermined}” (não há classificação "
    "datada disponível; isso não significa centro), “{controversial}” (fontes classificam o "
    "partido de formas diferentes no mesmo ano) e “{unaffiliated}” (parlamentares sem partido)."
)
BEFORE_SERIES_TEXT = (
    "Esta linha do tempo começa em {first_year}. O Se Liga acompanha instituições desde 1880 "
    "em outras partes do projeto, mas não tem classificação partidária contínua e comprovada "
    "por fonte para esse período mais longo: anos sem observação datada ficam como "
    "“{undetermined}” e nunca são "
    "preenchidos por interpolação ou tratados como centro. O regime militar (1964–1985) tem "
    "classificação própria como regime e não é aplicado às bancadas, e entre 1938 e 1945 o "
    "Parlamento não esteve instalado. Por isso esses períodos não aparecem aqui nem são "
    "comparados diretamente com o sistema atual."
)


def _paragraph(inner_html):
    return f"<p>{inner_html}</p>"


def _blocs_disclosure():
    labels = {key: escape_text(BLOC_BY_KEY[key].label) for key in BLOC_BY_KEY}
    sentence = INDEPENDENT_BLOCS_SENTENCE.format(**labels)
    comparison = (
        " Classificações acadêmicas diferem entre si e alguns partidos mudam de posição ao longo "
        "do tempo. Veja as alternativas em "
        f'<a href="{COMPARISON_PATH}">Comparação de classificações</a>.'
    )
    return render_disclosure(
        "Como os partidos foram agrupados em blocos", _paragraph(sentence + comparison)
    )


def _sources_disclosure(panorama):
    parts = []
    if panorama.sources_note:
        parts.append(_paragraph(escape_text(panorama.sources_note)))
    parts.extend(_paragraph(escape_text(note)) for note in panorama.coverage_notes)
    parts.append(_paragraph(
        "Períodos sem composição documentada aparecem como “sem dados”: nada é estimado. "
        "Maior bloco não significa base do governo. "
        f"Painel gerado em {panorama.generated_on.strftime('%d/%m/%Y')}."
    ))
    return render_disclosure("De onde vêm os números", "".join(parts))


def _before_series_disclosure(panorama):
    first_year = series_first_year(panorama) or "—"
    text = BEFORE_SERIES_TEXT.format(
        first_year=first_year, undetermined=escape_text(BLOC_BY_KEY["undetermined"].label)
    )
    return render_disclosure(f"E antes de {first_year}?", _paragraph(text))


def render_reading_section(panorama, state=None):
    """Section 'Como ler' with the three disclosures; `state` is accepted for a uniform API."""
    return (
        '<section class="ds-reading" aria-label="Como ler">'
        f"{_blocs_disclosure()}{_sources_disclosure(panorama)}"
        f"{_before_series_disclosure(panorama)}</section>"
    )
