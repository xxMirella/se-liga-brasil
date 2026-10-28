"""National filter catalog and pure dashboard query validation."""

from dataclasses import dataclass
from datetime import date

from service.public_profile import PublicProfileError

STATE_NAMES = dict(
    zip(
        (
            "AC",
            "AL",
            "AP",
            "AM",
            "BA",
            "CE",
            "DF",
            "ES",
            "GO",
            "MA",
            "MT",
            "MS",
            "MG",
            "PA",
            "PB",
            "PE",
            "PI",
            "PR",
            "RJ",
            "RN",
            "RS",
            "RO",
            "RR",
            "SC",
            "SP",
            "SE",
            "TO",
        ),
        (
            "Acre",
            "Alagoas",
            "Amapá",
            "Amazonas",
            "Bahia",
            "Ceará",
            "Distrito Federal",
            "Espírito Santo",
            "Goiás",
            "Maranhão",
            "Mato Grosso",
            "Mato Grosso do Sul",
            "Minas Gerais",
            "Pará",
            "Paraíba",
            "Pernambuco",
            "Piauí",
            "Paraná",
            "Rio de Janeiro",
            "Rio Grande do Norte",
            "Rio Grande do Sul",
            "Rondônia",
            "Roraima",
            "Santa Catarina",
            "São Paulo",
            "Sergipe",
            "Tocantins",
        ),
        strict=True,
    )
)
ASSEMBLIES = {"SP": "alesp", "RJ": "alerj"}
HISTORY_START = date(1826, 5, 6)


@dataclass(frozen=True)
class DashboardQuery:
    uf: str
    as_of: date
    senate_uf: str | None = None
    level: str = "federal"
    municipality_ibge: str | None = None
    view: str = "political_party"

    @property
    def year(self):
        return self.as_of.year

    @classmethod
    def from_parameters(cls, parameters, today):
        parameters = geography_parameters(parameters)
        view = parameters.get("view", "political_party")
        if view not in {"political_party", "political_orientation"}:
            raise PublicProfileError("INVALID_DASHBOARD_VIEW")
        uf = parameters.get("uf", "SP")
        level = parameters.get("level", "federal")
        municipality_ibge = parameters.get("municipality_ibge") or None
        if level not in {"federal", "state", "municipal"}:
            raise PublicProfileError("INVALID_DASHBOARD_LEVEL")
        if municipality_ibge and (
            len(municipality_ibge) != 7
            or not municipality_ibge.isascii()
            or not municipality_ibge.isdigit()
        ):
            raise PublicProfileError("INVALID_DASHBOARD_MUNICIPALITY")
        if uf == "DF" and (level == "municipal" or municipality_ibge):
            raise PublicProfileError("DISTRICT_HAS_NO_MUNICIPALITIES")
        senate_uf = parameters.get("senate_uf") or None
        if uf not in STATE_NAMES or (senate_uf and senate_uf not in STATE_NAMES):
            raise PublicProfileError("INVALID_DASHBOARD_STATE")
        as_of = parse_reference_date(parameters, today)
        if not HISTORY_START <= as_of <= today:
            raise PublicProfileError("INVALID_DASHBOARD_DATE")
        return cls(uf, as_of, senate_uf, level, municipality_ibge, view)


def geography_parameters(parameters):
    territory = parameters.get("territory")
    if territory is None:
        return parameters
    municipality = parameters.get("municipality_ibge") or None
    if territory == "BR":
        if municipality:
            raise PublicProfileError("INVALID_DASHBOARD_MUNICIPALITY")
        return parameters | {"uf": "SP", "level": "federal", "senate_uf": ""}
    if territory not in STATE_NAMES:
        raise PublicProfileError("INVALID_DASHBOARD_STATE")
    return parameters | {
        "uf": territory,
        "level": "municipal" if municipality else "state",
        "senate_uf": territory,
    }


def parse_reference_date(parameters, today):
    if "date" in parameters:
        raise PublicProfileError("INVALID_DASHBOARD_DATE")
    try:
        if "year" in parameters:
            value = parameters["year"]
            if len(value) != 4 or not value.isascii() or not value.isdigit():
                raise ValueError("invalid year")
            year = int(value)
            if not HISTORY_START.year <= year <= today.year:
                raise ValueError("year out of range")
            return min(date(year, 12, 31), today)
        return today
    except (ValueError, TypeError) as error:
        raise PublicProfileError("INVALID_DASHBOARD_DATE") from error
