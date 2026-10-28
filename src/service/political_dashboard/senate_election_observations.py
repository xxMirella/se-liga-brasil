"""Present election labels separately from verified annual Senate composition."""

from service.public_profile_web.security import official_url, text


def render_election_observation(record):
    party = text(record.get("political_party_literal"), "Legenda não informada pela fonte")
    qualification = (
        " · Mais de uma legenda ou coligação registrada pela fonte"
        if record.get("political_party_interpretation") == "multiple_labels" else ""
    )
    evidence = record.get("evidence") or {}
    source = official_url(evidence.get("url"))
    link = (
        f'<a href="{text(source)}" target="_blank" rel="noopener noreferrer">'
        'Ler registro eleitoral ↗</a>' if source else ""
    )
    return (
        f'<li><strong>{text(record["name"])}</strong>'
        f'<span>{text(record.get("territory_code"))} · Eleição de '
        f'{text(record["election_year"])}</span><span>{party}{qualification}</span>{link}</li>'
    )


def render_senate_election_observations(composition):
    records = composition.get("election_observations") or []
    if not records:
        return ""
    rows = "".join(render_election_observation(record) for record in sorted(
        records, key=lambda item: (item.get("territory_code", ""), item["name"])
    ))
    return (
        '<details class="panorama-election-observations panorama-members">'
        '<summary>Partidos registrados na eleição deste ano</summary>'
        '<p class="panorama-caption">Informações eleitorais publicadas pelo Senado. '
        'Ser eleito não comprova posse, exercício ou filiação durante todo o ano. '
        'Esses registros não são usados para calcular a maior bancada.</p>'
        f'<ul>{rows}</ul></details>'
    )
