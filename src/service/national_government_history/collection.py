"""Acquire and normalize dated official observations without backward or forward fill."""

import httpx

from crawlers.state_government.national_observations import newspaper_text, require_locators
from crawlers.state_government.parsing import evidence, source_exercise, visible_text
from service.ingestion.contracts import IngestionError
from service.national_government_history.article_observations import ARTICLE_OBSERVATIONS
from service.national_government_history.current_2026 import CURRENT_2026_OBSERVATIONS
from service.national_government_history.party_2026 import (
    PARTY_2026_OBSERVATIONS,
    PARTY_STATEMENT_URLS,
    qualify_party_statement,
)
from service.national_government_history.reviewed_2019 import (
    NEWSPAPER_2019_URL,
    NORTHEAST_2019,
    NORTHEAST_2019_URL,
    NORTHEAST_OFFICE_LOCATOR,
    OBSERVATIONS_2019,
)
from service.national_government_history.reviewed_current_2026 import reviewed_2026_fallback
from service.national_government_history.reviewed_legal_observations import (
    reviewed_2019_office_records,
)
from service.national_government_history.reviewed_observations import (
    NEWSPAPER_OBSERVATIONS,
    NEWSPAPER_URL,
    SENATE_URL,
)
from service.national_government_history.reviewed_transcriptions import es_reviewed_observation
from storage.files import save_json


def annual_observation(artifact, text, *, uf, name, party, page=None, locators,
                       observed_on="2023-01-01", published_on="2023-01-02", kind="inauguration"):
    require_locators(text, locators)
    year = int(observed_on[:4])
    record = source_exercise(name, uf, f"national-observation-{year}:" + name)
    proof = evidence(artifact, "; ".join(locators))
    proof.update(observed_on=observed_on, published_on=published_on, page=page)
    proof["source_kind"] = "official_newspaper_publication" if page else "official_reporting"
    record.update(
        institution_code="district_government" if uf == "DF" else "state_government",
        date_precision="year", starts_on=None, ends_before=None, year_start=year, year_end=year,
        source_observed_on=observed_on, observation_kind=kind,
        source_url=artifact.resource.url, evidence=[proof],
        limitation="dated_observation_not_full_year_or_continuous_affiliation",
    )
    if any("interinamente" in locator for locator in locators):
        record["exercise_capacity"] = "acting"
    if party:
        status = ("verified_official_inauguration_observation" if kind == "inauguration"
                  else "verified_official_dated_government_observation")
        record.update(
            political_party_abbreviation=party,
            political_party_status=status,
            political_party_context=("party_reported_at_inauguration" if kind == "inauguration"
                                     else "party_reported_during_government"),
            political_party_limitation="dated_observation_not_continuous_affiliation",
            political_party_year_start=year, political_party_year_end=year,
            political_party_evidence=[proof],
        )
    return record


def collect_article_observations(acquisition):
    records, failures = [], []
    catalog = (*ARTICLE_OBSERVATIONS, *CURRENT_2026_OBSERVATIONS, *PARTY_2026_OBSERVATIONS)
    for uf, name, party, observed, published, kind, url, locators in catalog:
        try:
            artifact = acquisition.acquire(url, uf)
            source_text = newspaper_text(artifact.path) if "/escriba-servicosweb/pdf/" in url else (
                visible_text(artifact.path.read_bytes())
            )
            record = annual_observation(
                artifact, source_text, uf=uf, name=name, party=party,
                observed_on=observed, published_on=published, kind=kind, locators=locators,
            )
            if url.endswith("/api/noticias/content/131276"):
                record["source_url"] = (
                    "https://al.ms.gov.br/Noticias/131276/"
                    "posse-dos-24-deputados-estaduais-da-inicio-a-12-legislatura"
                )
            if url in PARTY_STATEMENT_URLS:
                qualify_party_statement(record)
            records.append(record)
        except IngestionError as error:
            failures.append({"uf": uf, "url": url, "error_code": error.code})
        except httpx.HTTPError as error:
            failures.append({"uf": uf, "url": url, "error_code": type(error).__name__})
    return records, failures


def collect_2019_observations(acquisition):
    newspaper = acquisition.acquire(NEWSPAPER_2019_URL, "BR", ".pdf")
    pages = newspaper_text(newspaper.path).split("\f")
    return [annual_observation(
        newspaper, pages[page - 1], uf=uf, name=name, party=party, page=page, locators=locators,
        observed_on="2019-01-01", published_on="2019-01-02",
    ) for page, uf, name, party, locators in OBSERVATIONS_2019]


def collect_northeast_2019(acquisition):
    newspaper = acquisition.acquire(NORTHEAST_2019_URL, "BR", ".pdf")
    page = newspaper_text(newspaper.path).split("\f")[12]
    return [annual_observation(
        newspaper, page, uf=uf, name=name, party=party, page=13,
        locators=(NORTHEAST_OFFICE_LOCATOR, locator, "Criado em 14 de março"),
        observed_on="2019-03-14", published_on="2019-05-25", kind="office_observation",
    ) for uf, name, party, locator in NORTHEAST_2019]


def collect_national_government_observations(acquisition, output):
    newspaper = acquisition.acquire(NEWSPAPER_URL, "BR", ".pdf")
    text = newspaper_text(newspaper.path)
    pages = text.split("\f")
    records = [annual_observation(
        newspaper, pages[page - 1], uf=uf, name=name, party=party, page=page, locators=locators,
    ) for page, uf, name, party, locators in NEWSPAPER_OBSERVATIONS]
    senate = acquisition.acquire(SENATE_URL, "DF")
    records.append(annual_observation(
        senate, visible_text(senate.path.read_bytes()), uf="DF", name="Ibaneis Rocha", party="MDB",
        locators=("27 governadores foram empossados em 1° de janeiro",
                  "O governador do Distrito Federal, Ibaneis Rocha, do MDB"),
    ))
    articles, failures = collect_article_observations(acquisition)
    records.extend(articles)
    if not any(record["territory_code"] == "ES" and record["year_start"] == 2023
               for record in records):
        records.append(es_reviewed_observation(acquisition.configuration.storage_directory))
    historic = collect_2019_observations(acquisition)
    records.extend(historic)
    records.extend(collect_northeast_2019(acquisition))
    records.extend(reviewed_2019_office_records(acquisition.configuration.storage_directory))
    records.extend(reviewed_2026_fallback(
        acquisition.configuration.storage_directory, {row["url"] for row in failures},
    ))
    coverage = observation_coverage(records)
    payload = {
        "schema_version": "national_government_observations.v1", "exercises": records,
        "coverage": coverage,
        "source_failures": failures,
        "limitations": ["Only dated inauguration observations; no continuous party affiliation.",
                        "No inference for other years or annual year-end snapshots."],
    }
    save_json(output, payload)
    return payload["coverage"]


def observation_coverage(records):
    counts = {
        year: len({r["territory_code"] for r in records if r["year_start"] == year})
        for year in (2019, 2023, 2026)
    }
    return {
        "year": 2023, "uf_count": counts[2023], "complete": counts[2023] == 27,
        "scope": "territories_with_dated_observation_not_complete_annual_history",
        "additional_years": {
            str(year): {"uf_count": counts[year], "complete": counts[year] == 27}
            for year in (2019, 2026)
        },
    }
