"""Explain documented presidential transitions without inferring causes from duration."""

from datetime import date

from service.political_dashboard.executive_context import render_government_context_observations
from service.political_dashboard.presidential_transition_catalog import REVIEWED_TRANSITION_EVENTS
from service.public_profile_web.security import official_url, text

PRESIDENTIAL_EVENTS = (
    (2018, "2018-05-15", "Renomeação da legenda",
     "A sigla PMDB passou a ser MDB por decisão do TSE; trata-se da renomeação da legenda.",
     "https://www.tse.jus.br/comunicacao/noticias/2018/Maio/"
     "aprovada-mudanca-do-nome-do-partido-do-movimento-democratico-brasileiro-pmdb"),
    (1954, "1954-08-24", "Falecimento e sucessão",
     "Após a morte de Getúlio Vargas, o vice-presidente Café Filho assumiu a Presidência.",
     "https://www.gov.br/arquivonacional/pt-br/canais_atendimento/imprensa/noticias/"
     "serie-presidentes-da-republica-cafe-filho"),
    (1961, "1961-08-25", "Renúncia e substituição temporária",
     "Jânio Quadros renunciou. Ranieri Mazzilli assumiu enquanto João Goulart estava ausente.",
     "https://www2.camara.leg.br/atividade-legislativa/plenario/discursos/escrevendohistoria/"
     "a-crise-politica-de-1961/Acontecimentos%20do%20dia%2025%20de%20agosto%20de%201961"),
    (1964, "1964-04-02", "Vacância declarada durante o golpe",
     "O Congresso declarou vago o cargo de João Goulart, ainda no Brasil; "
     "Ranieri Mazzilli foi declarado presidente.",
     "https://www12.senado.leg.br/noticias/materias/2013/11/14/"
     "tumulto-marcou-sessao-que-decretou-vacancia-do-cargo-de-jango-em-64"),
    (1992, "1992-10-02", "Afastamento e exercício provisório",
     "Fernando Collor foi afastado; Itamar Franco assumiu provisoriamente.",
     "https://www2.camara.leg.br/atividade-legislativa/plenario/discursos/escrevendohistoria/"
     "20-anos-do-impeachment/20-anos-do-impeachment-do-presidente-fernando-collor"),
    (1992, "1992-12-29", "Renúncia durante o julgamento",
     "Collor apresentou a renúncia durante o processo de impeachment; "
     "Itamar assumiu a Presidência.",
     "https://www12.senado.leg.br/noticias/materias/2016/05/12/"
     "senado-julgara-um-presidente-da-republica-pela-segunda-vez"),
    (2016, "2016-05-12", "Afastamento e interinidade",
     "A abertura do processo afastou Dilma Rousseff; Michel Temer passou a exercer a Presidência.",
     "https://www12.senado.leg.br/noticias/materias/2016/05/12/"
     "senado-abre-processo-de-impeachment-contra-dilma-rousseff"),
    (2016, "2016-08-31", "Impeachment e posse definitiva",
     "O Senado retirou o mandato de Dilma Rousseff; Temer assumiu definitivamente.",
     "https://www12.senado.leg.br/noticias/materias/2016/08/31/"
     "dilma-rousseff-perde-o-mandato-e-temer-e-confirmado-presidente"),
)


PRESIDENTIAL_EVENTS = tuple(sorted(
    (*PRESIDENTIAL_EVENTS, *REVIEWED_TRANSITION_EVENTS), key=lambda event: event[1]
))


def presidency_institution(row):
    return next((item for item in row.get("institutions", [])
                 if item.get("institution_code") == "presidency"), None)


def presidential_person_key(record):
    return record.get("person_id") or record.get("name")


def date_value(value):
    try:
        return date.fromisoformat(value or "")
    except (ValueError, TypeError):
        return None


def presidential_duration(record):
    start, end = date_value(record.get("starts_on")), date_value(record.get("ends_before"))
    if record.get("date_precision", "day") != "day" or not start or not end or end <= start:
        return None
    return (end - start).days


def presidential_party_changes(records, year):
    changes = []
    by_person = {}
    for record in records:
        by_person.setdefault(presidential_person_key(record), []).extend(
            record.get("political_party_periods") or []
        )
    for periods in by_person.values():
        ordered = sorted(periods, key=lambda item: item.get("starts_on") or "")
        for previous, current in zip(ordered, ordered[1:], strict=False):
            start = date_value(current.get("starts_on"))
            before, after = previous.get("political_party"), current.get("political_party")
            if start and start.year == year and before and after and before != after:
                changes.append(presidential_party_transition(previous, current, start))
    return list({(item["date"], item["before"], item["after"]): item for item in changes}.values())



def presidential_party_transition(previous, current, start):
    label = (
        f"Classificação anual: {start.year}" if current.get("date_precision") == "year"
        else f"Registro a partir de {start.isoformat()}"
    )
    previous_end = date_value(previous.get("ends_before"))
    gap_note = (
        "Há intervalo sem comprovação entre esses registros; a data não indica o dia da troca."
        if previous_end and previous_end < start else ""
    )
    return {"date": start.isoformat(), "date_label": label, "gap_note": gap_note,
            "before": previous["political_party"], "after": current["political_party"],
            "source_url": current.get("source_url")}


def is_interim(record):
    capacity = record.get("exercise_capacity") or ""
    return "interim" in capacity or capacity == "acting_president"


def presidential_year_explanation(row):
    institution = presidency_institution(row)
    records = (institution or {}).get("segments") or []
    collective = [record for record in records
                  if record.get("exercise_capacity") == "collective_junta"]
    people = {presidential_person_key(record) for record in records
              if record.get("exercise_capacity") != "collective_junta"} - {None}
    short = [record for record in records if (duration := presidential_duration(record))
             is not None and duration < 365]
    interim = [record for record in records if is_interim(record)]
    changes = presidential_party_changes(records, row["year"])
    events = [event for event in PRESIDENTIAL_EVENTS if event[0] == row["year"]] if records else []
    government_context = (institution or {}).get("government_context_observations") or []
    has_context = (len(people) + len(collective) > 1 or short or interim or changes or events
                   or government_context)
    if not has_context:
        return None
    return {"year": row["year"], "people_count": len(people), "records": records,
            "short": short, "interim": interim, "collective_count": len(collective),
            "political_party_changes": changes,
            "events": events, "government_context": government_context}


def presidential_year_label(explanation):
    labels = []
    if explanation["collective_count"]:
        count = explanation["people_count"] + explanation["collective_count"]
        labels.append(f"{count} governos registrados, incluindo governo coletivo")
    elif explanation["people_count"] > 1:
        labels.append(f'{explanation["people_count"]} pessoas na Presidência')
    if explanation["interim"]:
        labels.append("exercício interino")
    if explanation["short"]:
        labels.append("exercício inferior a um ano")
    if explanation["political_party_changes"]:
        labels.append("mudança na atribuição partidária")
    if explanation.get("government_context"):
        labels.append("contexto partidário documentado")
    if explanation["events"] and not labels:
        labels.append("transição documentada")
    return " · ".join(labels)


def presidential_source(url, label="Verificar fonte"):
    safe = official_url(url)
    return (f'<a href="{text(safe)}" target="_blank" rel="noopener noreferrer">'
            f'{text(label)} ↗</a>') if safe else ""


def render_presidential_record(record):
    start, end = record.get("starts_on"), record.get("ends_before")
    period = f'{start or "Início não informado"} → {end or "fim ainda não documentado"}'
    duration = presidential_duration(record)
    qualifier = f" · {duration} dias entre as datas documentadas" if duration is not None else ""
    interim = " · exercício interino" if is_interim(record) else ""
    capacity_source = presidential_source(
        record.get("exercise_capacity_source_url"), "Fonte da interinidade"
    )
    return (f'<li><strong>{text(record.get("name") or "Nome não informado")}</strong>'
            f'<p>{text(period + qualifier + interim)}</p>'
            f'{presidential_source(record.get("source_url"))} '
            f'{capacity_source}'
            '</li>')


def render_presidential_year(explanation, selected_year=None):
    year = explanation["year"]
    records = "".join(render_presidential_record(record) for record in explanation["records"])
    events = "".join(f'<li><strong>{text(event[1])} · {text(event[2])}</strong>'
                     f'<p>{text(event[3])}</p>{presidential_source(event[4])}</li>'
                     for event in explanation["events"])
    changes = "".join(f'<li>{text(change["date_label"])} · {text(change["before"])} → '
                      f'{text(change["after"])} <span>{text(change["gap_note"], "")}</span> '
                      f'{presidential_source(change["source_url"])}</li>'
                      for change in explanation["political_party_changes"])
    expanded = " open" if year == selected_year else ""
    return (f'<details id="presidency-year-{year}" class="panorama-presidential-year"{expanded}>'
            f'<summary>{year} · {text(presidential_year_label(explanation))}</summary>'
            f'<ol>{records}</ol>' + (f'<ul>{events + changes}</ul>' if events or changes else "")
            + render_government_context_observations(explanation.get("government_context"))
            + '</details>')


def render_presidential_explanations(data):
    if data.get("level") != "federal":
        return ""
    explanations = [item for row in data.get("history", [])
                    if (item := presidential_year_explanation(row))]
    if not explanations:
        return ""
    selected = data.get("year")
    content = "".join(render_presidential_year(item, selected) for item in explanations)
    expanded = " open" if any(item["year"] == selected for item in explanations) else ""
    content = (f'<details class="panorama-presidential-all-years"{expanded}>'
               f'<summary>Explorar {len(explanations)} anos com transições</summary>'
               f'{content}</details>')
    return ('<section class="panorama-presidential-transitions" '
            'aria-labelledby="presidential-transitions-title">'
            '<h3 id="presidential-transitions-title">Entenda as mudanças na Presidência</h3>'
            '<p>Os círculos na faixa presidencial indicam anos com transições. '
            'Abra um ano para ver quem exerceu o cargo, datas e causas documentadas. '
            'Uma mesma pessoa pode ter mais de um período. As datas seguem os intervalos '
            'documentados nas fontes; os dias são calculados entre elas.</p>'
            f'{content}</section>')


def render_presidential_markers(history, years, x_start, width, y, view="political_party"):
    elements = []
    for row in history:
        explanation = presidential_year_explanation(row)
        if not explanation:
            continue
        x = x_start + (row["year"] - years[0] + .5) * width
        label = f'{row["year"]} · {presidential_year_label(explanation)} · Ver explicação abaixo'
        href = f'/panorama?territory=BR&amp;year={row["year"]}#presidency-year-{row["year"]}'
        if view == "political_orientation":
            href = href.replace("#presidency", "&amp;view=political_orientation#presidency")
        elements.append(f'<a href="{href}" aria-label="{text(label)}">'
                        f'<title>{text(label)}</title><circle cx="{x:.2f}" cy="{y - 6}" '
                        'r="4" fill="#183f31" stroke="#fff" stroke-width="1"/></a>')
    return "".join(elements)
