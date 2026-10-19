"""Annual bulk resources reuse shared immutable cache, retry and host pacing."""

from urllib.parse import urlencode

from crawlers.cmsp.configuration import API_BASE
from normalization.scalars import normalize_year
from service.acquisition.downloader import download_resource
from service.ingestion.contracts import DownloadBudget, IngestionError, Resource
from storage.files import hash_content

ANNUAL_OPERATIONS = {
    "projects": ("ProjetosPorAno", "Ano", "cmsp_projects"),
    "authorship": ("ProjetosAutores", "ano", "cmsp_authorship"),
    "deliberations": ("FasesDeDeliberacao", "ano", "cmsp_deliberations"),
}


def annual_resources(years, domains=("projects", "authorship", "deliberations")):
    """Deduplicate partitions; none of these official methods defines pagination."""
    seen = set()
    for year in years:
        normalized_year = normalize_year(year, minimum=1948, maximum=2200)
        for domain in domains:
            if domain not in ANNUAL_OPERATIONS:
                raise IngestionError("CMSP_UNSUPPORTED_DOMAIN")
            operation, year_parameter, kind = ANNUAL_OPERATIONS[domain]
            parameters = {year_parameter: normalized_year}
            if domain == "authorship":
                parameters.update(tipo="", numero="")
            url = API_BASE + operation + "?" + urlencode(parameters)
            if url in seen:
                continue
            seen.add(url)
            yield Resource(
                "cmsp-" + hash_content(url),
                operation,
                url,
                kind,
                normalized_year,
                "cmsp-legislative",
                "SP",
                ".xml",
            )


class MunicipalAcquisition:
    def __init__(self, configuration, client):
        self.configuration = configuration
        self.client = client
        self.budget = DownloadBudget()

    def acquire(self, resource):
        return download_resource(resource, self.configuration, self.client, self.budget)
