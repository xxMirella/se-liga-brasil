"""Normalize archived Senate API responses; every end date becomes exclusive, nothing is guessed."""

from datetime import date, timedelta

from crawlers.senado.historical_period_contracts import (
    ArchivedDocument,
    PendingItem,
    SenateAffiliation,
    SenateExercise,
    SenateParty,
    SenateTerm,
    SenatorIdentity,
    YearOnlyAffiliationClaim,
)
from normalization.scalars import normalize_date, normalize_text
from service.ingestion.contracts import IngestionError


def as_list(value) -> list:
    if value is None or value == "":
        return []
    return value if isinstance(value, list) else [value]


def parse_iso_date(value) -> date | None:
    text = normalize_date(value, date_format="%Y-%m-%d")
    return date.fromisoformat(text) if text else None


def inclusive_end_to_exclusive(value) -> date | None:
    """The Senate publishes last days inclusively; the database stores the next day."""
    last_day = parse_iso_date(value)
    return last_day + timedelta(days=1) if last_day else None


def normalize_identity(document: ArchivedDocument, senator_id: str) -> SenatorIdentity:
    try:
        profile = document.payload["DetalheParlamentar"]["Parlamentar"]
        identification = profile["IdentificacaoParlamentar"]
        published_id = str(identification["CodigoParlamentar"])
        civil_name = normalize_text(identification["NomeCompletoParlamentar"], required=True)
        display_name = normalize_text(identification["NomeParlamentar"], required=True)
        birth_date = parse_iso_date(profile["DadosBasicosParlamentar"].get("DataNascimento"))
    except (KeyError, TypeError, IngestionError) as error:
        raise IngestionError("SENATOR_IDENTITY_DOCUMENT_INCOMPLETE") from error
    if published_id != senator_id:
        raise IngestionError("SENATOR_SOURCE_ID_MISMATCH")
    if birth_date is None:
        raise IngestionError("SENATOR_BIRTH_DATE_MISSING")
    return SenatorIdentity(senator_id, civil_name, display_name, birth_date, document)


def normalize_party_catalog(document: ArchivedDocument) -> dict[str, SenateParty]:
    try:
        rows = as_list(document.payload["ListaPartidos"]["Partidos"]["Partido"])
        parties = [_party(row, document) for row in rows]
    except (KeyError, TypeError) as error:
        raise IngestionError("SENATE_PARTY_CATALOG_SCHEMA_CHANGED") from error
    return {party.senate_party_code: party for party in parties}


def _party(row: dict, document: ArchivedDocument) -> SenateParty:
    return SenateParty(
        senate_party_code=str(row["Codigo"]),
        abbreviation=normalize_text(row["Sigla"], required=True),
        name=normalize_text(row["Nome"], required=True),
        created_on=parse_iso_date(row.get("DataCriacao")),
        extinguished_on=parse_iso_date(row.get("DataExtincao")),
        document=document,
    )


def normalize_mandates(
    document: ArchivedDocument, senator_id: str
) -> tuple[list[SenateTerm], list[SenateExercise], list[PendingItem]]:
    try:
        parliamentarian = document.payload["MandatoParlamentar"]["Parlamentar"]
        mandates = as_list(parliamentarian.get("Mandatos", {}).get("Mandato"))
        published_id = str(parliamentarian["Codigo"])
    except (KeyError, TypeError, AttributeError) as error:
        raise IngestionError("SENATOR_MANDATES_SCHEMA_CHANGED") from error
    if published_id != senator_id:
        raise IngestionError("SENATOR_SOURCE_ID_MISMATCH")
    terms, exercises, pending = [], [], []
    for mandate in mandates:
        try:
            term = _term(mandate, senator_id, document)
        except (KeyError, TypeError, IngestionError, ValueError) as error:
            pending.append(PendingItem("MANDATE_NOT_NORMALIZABLE", senator_id, repr(error)))
            continue
        terms.append(term)
        exercises.extend(_exercises(mandate, term, document))
    return terms, exercises, pending


def _term(mandate: dict, senator_id: str, document: ArchivedDocument) -> SenateTerm:
    first, second = mandate["PrimeiraLegislaturaDoMandato"], mandate["SegundaLegislaturaDoMandato"]
    return SenateTerm(
        senator_id=senator_id,
        mandate_code=normalize_text(mandate.get("CodigoMandato")),
        represented_uf=normalize_text(mandate["UfParlamentar"], required=True),
        capacity=_capacity(mandate.get("DescricaoParticipacao")),
        legislature_key=f"{first['NumeroLegislatura']}-{second['NumeroLegislatura']}",
        starts_on=parse_iso_date(first["DataInicio"]),
        ends_before=inclusive_end_to_exclusive(second["DataFim"]),
        document=document,
    )


def _capacity(description) -> str | None:
    """Missing participation is kept as None; it only matters when the mandate is in scope."""
    text = normalize_text(description)
    if text is None:
        return None
    if text == "Titular":
        return "holder"
    if "Suplente" in text:
        return "substitute"
    raise IngestionError("MANDATE_PARTICIPATION_UNKNOWN")


def _exercises(mandate: dict, term: SenateTerm, document: ArchivedDocument) -> list:
    rows = as_list(mandate.get("Exercicios", {}).get("Exercicio"))
    return [
        SenateExercise(
            senator_id=term.senator_id,
            legislature_key=term.legislature_key,
            starts_on=parse_iso_date(row["DataInicio"]),
            ends_before=inclusive_end_to_exclusive(row.get("DataFim")),
            capacity=term.capacity,
            departure_cause_code=normalize_text(row.get("SiglaCausaAfastamento")),
            departure_cause=normalize_text(row.get("DescricaoCausaAfastamento")),
            document=document,
        )
        for row in rows
    ]


def normalize_affiliations(
    document: ArchivedDocument, senator_id: str
) -> tuple[list[SenateAffiliation], list[YearOnlyAffiliationClaim], list[PendingItem]]:
    try:
        parliamentarian = document.payload["FiliacaoParlamentar"]["Parlamentar"]
        published_id = str(parliamentarian["Codigo"])
        rows = as_list((parliamentarian.get("Filiacoes") or {}).get("Filiacao"))
    except (KeyError, TypeError, AttributeError) as error:
        raise IngestionError("SENATOR_AFFILIATIONS_SCHEMA_CHANGED") from error
    if published_id != senator_id:
        raise IngestionError("SENATOR_SOURCE_ID_MISMATCH")
    affiliations, year_only, pending = [], [], []
    for row in rows:
        try:
            _classify_affiliation(row, senator_id, document, affiliations, year_only, pending)
        except (KeyError, TypeError, IngestionError, ValueError) as error:
            pending.append(PendingItem("AFFILIATION_NOT_NORMALIZABLE", senator_id, repr(error)))
    return affiliations, year_only, pending


def _classify_affiliation(row, senator_id, document, affiliations, year_only, pending) -> None:
    party = row["Partido"]
    code, abbreviation = party.get("CodigoPartido"), party.get("SiglaPartido")
    if not code or not abbreviation:
        pending.append(PendingItem("AFFILIATION_PARTY_NOT_IDENTIFIED", senator_id, _brief(row)))
        return
    if not row.get("DataFiliacao"):
        year_only.append(_year_only_claim(row, senator_id, document))
        return
    affiliations.append(
        SenateAffiliation(
            senator_id=senator_id,
            senate_party_code=str(code),
            abbreviation=normalize_text(abbreviation, required=True),
            starts_on=parse_iso_date(row["DataFiliacao"]),
            ends_before=inclusive_end_to_exclusive(row.get("DataDesfiliacao")),
            document=document,
            raw_element=row,
        )
    )


def _year_only_claim(row, senator_id, document) -> YearOnlyAffiliationClaim:
    party = row["Partido"]
    return YearOnlyAffiliationClaim(
        senator_id=senator_id,
        senate_party_code=str(party["CodigoPartido"]),
        party_abbreviation=party["SiglaPartido"],
        year_from=_optional_year(row.get("AnoFiliacao")),
        year_until=_optional_year(row.get("AnoDesfiliacao")),
        document=document,
        raw_element=row,
    )


def _optional_year(value) -> int | None:
    text = normalize_text(value)
    return int(text) if text and text.isdigit() else None


def _brief(row: dict) -> str:
    party = row.get("Partido", {})
    starts = row.get("DataFiliacao") or row.get("AnoFiliacao")
    ends = row.get("DataDesfiliacao") or row.get("AnoDesfiliacao")
    return f"party={party.get('NomePartido')!r} from={starts} until={ends}"
