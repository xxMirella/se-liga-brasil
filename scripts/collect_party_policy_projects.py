"""Coleta e agrega proposições de autoria parlamentar por partido e tema.

Fontes oficiais, arquivos em lote (sem N+1 remoto):
- Câmara: arquivos CSV anuais proposicoesAutores, proposicoesTemas e proposicoes.
- Senado: /dadosabertos/materia/pesquisa/lista?ano=AAAA (campo Autor traz partido/UF).

Os arquivos brutos são gravados comprimidos com SHA256 em manifest.json; a agregação
vai para derived/. Uso: .venv/bin/python scripts/collect_party_policy_projects.py 1980 2026
"""

from __future__ import annotations

import collections
import csv
import gzip
import hashlib
import http.client
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data/political-orientation/party-model/policies"
RAW = ROOT / "raw"
DERIVED = ROOT / "derived"
CAMARA_URL = (
    "https://dadosabertos.camara.leg.br/arquivos/"  # hardcode-ok: arquivos oficiais
    "{kind}/csv/{kind}-{year}.csv"
)
SENADO_URL = (
    "https://legis.senado.leg.br/dadosabertos/"  # hardcode-ok: fonte oficial
    "materia/pesquisa/lista?ano={year}"
)
CAMARA_KINDS = ("proposicoesAutores", "proposicoesTemas", "proposicoes")
LEGISLATIVE_TYPES = {"PL", "PLP", "PEC", "PDL", "PDC", "PLN", "PLV", "PLS", "PDS", "PRS"}
SENATE_AUTHORED_TYPES = {"PLS", "PL", "PLP", "PEC", "PDS", "PDL", "PRS"}
OVERSIGHT_TYPES = {"RIC", "REQ", "INC", "PRC"}
TYPE_GROUPS = {
    "PL": "projeto_de_lei",
    "PLP": "projeto_de_lei_complementar",
    "PEC": "emenda_constitucional",
    "PDL": "decreto_legislativo",
    "PDC": "decreto_legislativo",
    "PDS": "decreto_legislativo",
    "RIC": "requerimento_de_informacao",
    "REQ": "requerimento",
    "INC": "indicacao",
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def download(url: str, destination: Path, manifest: dict) -> bool:
    """Baixa e grava comprimido; registra url, sha256 do conteúdo original e data."""
    if destination.exists() and destination.name in manifest:
        return True
    for attempt in range(3):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/json" if "senado" in url else "*/*",
                    "User-Agent": "se-liga-brasil-research",
                },
            )
            with urllib.request.urlopen(request, timeout=180) as response:
                content = response.read()
            break
        except urllib.error.HTTPError as error:
            if error.code == 404:
                manifest[destination.name] = {
                    "url": url,
                    "status": "indisponivel_http_404",
                    "baixado_em": now_iso(),
                }
                return False
            time.sleep(3 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, http.client.IncompleteRead):
            time.sleep(3 * (attempt + 1))
    else:
        manifest[destination.name] = {
            "url": url,
            "status": "falha_de_rede",
            "baixado_em": now_iso(),
        }
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(gzip.compress(content, 6))
    manifest[destination.name] = {
        "url": url,
        "sha256_conteudo_original": hashlib.sha256(content).hexdigest(),
        "bytes_originais": len(content),
        "baixado_em": now_iso(),
        "status": "ok",
    }
    return True


def read_csv(path: Path):
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle, delimiter=";")


def proposition_id(uri: str) -> str:
    return uri.rstrip("/").rsplit("/", 1)[-1]


def camara_proposition_themes(year: int, folder: Path):
    themes = collections.defaultdict(set)
    for row in read_csv(folder / f"proposicoesTemas-{year}.csv.gz"):
        themes[proposition_id(row["uriProposicao"])].add(row["tema"])
    return themes


def camara_party_authorship(year: int, folder: Path, proposition_types):
    signed = collections.defaultdict(set)
    proponent = collections.defaultdict(set)
    for row in read_csv(folder / f"proposicoesAutores-{year}.csv.gz"):
        if row["tipoAutor"] != "Deputado(a)" or row["idProposicao"] not in proposition_types:
            continue
        political_party = row["siglaPartidoAutor"] or "SEM_PARTIDO_REGISTRADO"
        signed[political_party].add(row["idProposicao"])
        if row["proponente"] == "1":
            proponent[political_party].add(row["idProposicao"])
    return (("proposicoes_assinadas", signed), ("proposicoes_como_proponente", proponent))


def count_proposition_themes(proposition_ids, proposition_types, proposition_themes):
    counter = collections.Counter()
    for proposition in proposition_ids:
        group = TYPE_GROUPS.get(proposition_types[proposition])
        if group is None:
            continue
        counter[(group, "__total__")] += 1
        for theme in proposition_themes.get(proposition, {"__sem_tema_oficial__"}):
            counter[(group, theme)] += 1
    return counter


def aggregate_camara_year(year: int, folder: Path) -> list[list]:
    """Linhas (ano, partido, grupo_de_tipo, tema, métrica, contagem) para um ano."""
    types = {row["id"]: row["siglaTipo"] for row in read_csv(folder / f"proposicoes-{year}.csv.gz")}
    themes = camara_proposition_themes(year, folder)
    rows = []
    for metric, by_party in camara_party_authorship(year, folder, types):
        for political_party, proposition_ids in by_party.items():
            counter = count_proposition_themes(proposition_ids, types, themes)
            rows.extend(
                [year, political_party, group, theme, metric, count]
                for (group, theme), count in counter.items()
            )
    return rows


SENATOR_AUTHOR = re.compile(
    r"^Senador[a]?\s+(?P<name>.+?)\s+\((?P<party>[^/)]*)/(?P<uf>[A-Z]{0,2})\)"
)


def aggregate_senado_year(path: Path, year: int) -> list[list]:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            materias = json.load(handle)["PesquisaBasicaMateria"]["Materias"]["Materia"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []  # Ano sem dados: preservar vazio no derivado.
    counter = collections.Counter()
    for materia in materias:
        match = SENATOR_AUTHOR.match(materia.get("Autor") or "")
        if materia["Sigla"] in SENATE_AUTHORED_TYPES and match:
            counter[
                (
                    match["party"] or "SEM_PARTIDO_REGISTRADO",
                    TYPE_GROUPS.get(materia["Sigla"], "projeto_de_lei"),
                )
            ] += 1
    return [
        [year, party, group, "__total__", "proposicoes_primeiro_autor_senador", n]
        for (party, group), n in counter.items()
    ]


def main(first_year: int, last_year: int) -> None:
    manifest_path = ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    camara_rows, senado_rows = [], []
    for year in range(first_year, last_year + 1):
        folder = RAW / "camara"
        ok = all(
            download(CAMARA_URL.format(kind=k, year=year), folder / f"{k}-{year}.csv.gz", manifest)
            for k in CAMARA_KINDS
        )
        if ok:
            camara_rows += aggregate_camara_year(year, folder)
        senate_path = RAW / "senado" / f"lista-{year}.json.gz"
        if download(SENADO_URL.format(year=year), senate_path, manifest) is False:
            continue
        senado_rows += aggregate_senado_year(senate_path, year)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
        print(year, len(camara_rows), len(senado_rows), flush=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    for name, rows in (
        ("camara_party_theme_counts", camara_rows),
        ("senado_party_type_counts", senado_rows),
    ):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            ["ano", "partido_do_autor", "grupo_de_tipo", "tema_oficial", "metrica", "contagem"]
        )
        writer.writerows(rows)
        (DERIVED / f"{name}_{first_year}_{last_year}.csv").write_text(buffer.getvalue())


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
