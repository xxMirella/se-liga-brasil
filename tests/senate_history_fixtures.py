"""Synthetic archive builders; fictitious people only, written under a temporary directory."""

import hashlib
import json
from pathlib import Path

from crawlers.senado.historical_period_archive import SenateArchive
from crawlers.senado.historical_period_plan import build_load_plan

DETAIL = "DetalheParlamentar"


def detail_payload(senator_id, civil_name="Pessoa Ficticia Um", birth="1950-05-17"):
    return {
        DETAIL: {
            "Parlamentar": {
                "IdentificacaoParlamentar": {
                    "CodigoParlamentar": senator_id,
                    "NomeParlamentar": "Ficticia Um",
                    "NomeCompletoParlamentar": civil_name,
                    "EmailParlamentar": "contato@example.invalid",
                },
                "DadosBasicosParlamentar": {"DataNascimento": birth},
            }
        }
    }


def mandate(code, first, second, role="Titular", exercises=None):
    row = {
        "UfParlamentar": "SC",
        "PrimeiraLegislaturaDoMandato": {
            "NumeroLegislatura": first[0],
            "DataInicio": first[1],
            "DataFim": first[2],
        },
        "SegundaLegislaturaDoMandato": {
            "NumeroLegislatura": second[0],
            "DataInicio": second[1],
            "DataFim": second[2],
        },
    }
    if code:
        row["CodigoMandato"] = code
    if role:
        row["DescricaoParticipacao"] = role
    if exercises:
        row["Exercicios"] = {"Exercicio": exercises}
    return row


TERM_49_50 = mandate("7", ("49", "1991-02-01", "1995-01-31"), ("50", "1995-02-01", "1999-01-31"))


def mandates_payload(senator_id, mandates):
    return {
        "MandatoParlamentar": {
            "Parlamentar": {"Codigo": senator_id, "Mandatos": {"Mandato": mandates}}
        }
    }


def affiliation(code, abbreviation, starts, ends=None, **extra):
    row = {
        "Partido": {
            "CodigoPartido": code,
            "SiglaPartido": abbreviation,
            "NomePartido": abbreviation,
        }
    }
    if starts:
        row["DataFiliacao"] = starts
    if ends:
        row["DataDesfiliacao"] = ends
    return row | extra


def affiliations_payload(senator_id, rows):
    return {
        "FiliacaoParlamentar": {
            "Parlamentar": {"Codigo": senator_id, "Filiacoes": {"Filiacao": rows}}
        }
    }


def parties_payload():
    rows = [
        {
            "Codigo": "22",
            "Sigla": "PFL",
            "Nome": "Partido da Frente Liberal",
            "DataCriacao": "1985-01-24",
            "DataExtincao": "2007-08-02",
        },
        {
            "Codigo": "92",
            "Sigla": "PRN",
            "Nome": "Partido da Reconstrução Nacional",
            "DataCriacao": "1989-02-22",
            "DataExtincao": "2001-06-08",
        },
        {
            "Codigo": "71",
            "Sigla": "PT",
            "Nome": "Partido dos Trabalhadores",
            "DataCriacao": "1980-02-10",
        },
        {"Codigo": "163", "Sigla": "S/Partido", "Nome": "Sem Partido"},
    ]
    return {"ListaPartidos": {"Partidos": {"Partido": rows}}}


class ArchiveBuilder:
    """Writes raw files and a manifest in the layout of the newer acquisition."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.entries = []
        (directory / "raw").mkdir(parents=True)

    def add(self, kind, senator_id, payload, *, corrupt_hash=False):
        name = f"{kind}-{senator_id or 'catalog'}.json"
        raw = json.dumps(payload).encode()
        (self.directory / "raw" / name).write_bytes(raw)
        digest = hashlib.sha256(b"other" if corrupt_hash else raw).hexdigest()
        self.entries.append(
            {
                "url": f"https://legis.senado.leg.br/dadosabertos/test/{name}",
                "kind": kind,
                "senator_id": senator_id,
                "http_status": 200,
                "baixado_em": "2026-10-28T21:57:53+00:00",
                "sha256": digest,
                "bytes": len(raw),
                "path": f"raw/{name}",
            }
        )
        return self

    def add_senator(self, senator_id, mandates, affiliations, **identity):
        self.add("detail", senator_id, detail_payload(senator_id, **identity))
        self.add("mandates", senator_id, mandates_payload(senator_id, mandates))
        return self.add("affiliations", senator_id, affiliations_payload(senator_id, affiliations))

    def finish(self) -> Path:
        (self.directory / "manifest.json").write_text(json.dumps(self.entries))
        return self.directory


def build_plan(tmp_path, builder_steps, senator_ids, project_root=None):
    builder = ArchiveBuilder(tmp_path / "source")
    builder.add("parties", None, parties_payload())
    builder_steps(builder)
    directory = builder.finish()
    archive = SenateArchive(project_root or tmp_path, directory)
    return build_load_plan(archive, senator_ids), archive
