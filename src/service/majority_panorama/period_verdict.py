"""The one-sentence reading of a period, computed only from documented data."""

from service.majority_panorama.blocs import BLOC_BY_KEY
from service.majority_panorama.period_selection import (
    has_solo_majority,
    largest_ideological_bloc,
    main_president,
)

NO_SOLO_MAJORITY_SENTENCE = (
    "Nenhum bloco tem maioria sozinho em nenhuma das Casas: aprovar leis exige somar blocos."
)


def _president_phrase(president):
    bloc = BLOC_BY_KEY[president.bloc_key]
    if bloc.ideological:
        return f"Presidente de {bloc.label.lower()}"
    return f"Presidente com categoria “{bloc.label.lower()}”"


def _missing_houses_sentence(legislature):
    missing = []
    if legislature.camara is None:
        missing.append("da Câmara")
    if legislature.senado is None:
        missing.append("do Senado")
    where = " nem ".join(missing)
    return f"Não há composição documentada {where} neste período; nada foi estimado."


def _solo_majority_sentence(legislature):
    holders = [
        f"{BLOC_BY_KEY[largest_ideological_bloc(house)].label} {place}"
        for place, house in (("na Câmara", legislature.camara), ("no Senado", legislature.senado))
        if has_solo_majority(house)
    ]
    if not holders:
        return NO_SOLO_MAJORITY_SENTENCE
    return "Tem maioria sozinho: " + " e ".join(holders) + "."


def _same_bloc_sentence(legislature):
    verb = "tem" if has_solo_majority(legislature.camara) else "não tem"
    return (
        ", e o mesmo bloco é o maior nas duas Casas. "
        f"Ainda assim, {verb} maioria sozinho na Câmara."
    )


def _largest_blocs_sentence(legislature):
    camara_label = BLOC_BY_KEY[largest_ideological_bloc(legislature.camara)].label.lower()
    senado_label = BLOC_BY_KEY[largest_ideological_bloc(legislature.senado)].label.lower()
    return (
        f"O maior bloco é {camara_label} na Câmara e {senado_label} no Senado. "
        + _solo_majority_sentence(legislature)
    )


def _president_bloc_leads_both_houses(legislature, president):
    largest = {largest_ideological_bloc(legislature.camara),
               largest_ideological_bloc(legislature.senado)}
    return president is not None and largest == {president.bloc_key}


def build_period_verdict(panorama, legislature):
    president = main_president(panorama, legislature)
    if not legislature.has_data:
        missing = _missing_houses_sentence(legislature)
        if president is None:
            return f"Não há presidente documentado neste período. {missing}"
        return f"{_president_phrase(president)}. {missing}"
    if _president_bloc_leads_both_houses(legislature, president):
        return _president_phrase(president) + _same_bloc_sentence(legislature)
    blocs = _largest_blocs_sentence(legislature)
    if president is None:
        return f"Não há presidente documentado neste período. {blocs}"
    return f"{_president_phrase(president)}. {blocs}"
