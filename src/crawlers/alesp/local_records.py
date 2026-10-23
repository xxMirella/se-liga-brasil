"""Stream immutable ALESP XML exports and join authors using a temporary disk index."""

import sqlite3
import tempfile
import xml.etree.ElementTree as ElementTree
import zipfile
from contextlib import contextmanager
from pathlib import Path

from service.ingestion.contracts import IngestionError
from storage.files import hash_content


def xml_rows(path, record_tag):
    """Clear root children after each record, keeping memory bounded by one record."""
    with open_xml(path) as stream:
        events = ElementTree.iterparse(stream, events=("start", "end"))
        _, root = next(events)
        for event, element in events:
            if event == "end" and element.tag == record_tag:
                yield {child.tag: (child.text or "").strip() for child in element}
                root.clear()


@contextmanager
def open_xml(path):
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            members = [name for name in archive.namelist() if name.endswith(".xml")]
            if len(members) != 1:
                raise IngestionError("ALESP_XML_ARCHIVE_AMBIGUOUS")
            with archive.open(members[0]) as stream:
                yield stream
    else:
        with path.open("rb") as stream:
            yield stream


def verified_author_index(roster_path, resolutions, person_ids=None):
    verified = {}
    for resolution in resolutions:
        if resolution["status"] != "matched":
            continue
        person_id = str(resolution["person_id"])
        if person_ids is not None and person_id not in person_ids:
            continue
        for subject in resolution.get("official_subjects", []):
            key = subject["source_subject_id"]
            assign_unique_person(verified, key, person_id)
    authors = {}
    for member in xml_rows(roster_path, "Deputado"):
        person_id = verified.get(member["IdDeputado"])
        if person_id and member.get("IdSPL"):
            key = member["IdSPL"]
            assign_unique_person(authors, key, person_id)
    return authors


def assign_unique_person(index, key, person_id):
    if index.setdefault(key, person_id) != person_id:
        raise IngestionError("ALESP_AUTHOR_PERSON_AMBIGUOUS")


@contextmanager
def indexed_authorships(path, authors):
    with tempfile.TemporaryDirectory(prefix="alesp-authorship-") as directory:
        connection = sqlite3.connect(Path(directory) / "authors.sqlite")
        try:
            connection.execute(
                "CREATE TABLE authors(document TEXT,person TEXT,PRIMARY KEY(document,person))"
            )
            connection.execute("PRAGMA cache_size=-4096")
            for row in xml_rows(path, "DocumentoAutor"):
                person_id = authors.get(row["IdAutor"])
                if person_id:
                    connection.execute(
                        "INSERT OR IGNORE INTO authors VALUES(?,?)", (row["IdDocumento"], person_id)
                    )
            connection.commit()
            yield connection
        finally:
            connection.close()


def authored_propositions(dataset_directory, resolutions, person_ids=None):
    authors = verified_author_index(dataset_directory / "61_deputados.xml", resolutions, person_ids)
    if not authors:
        return
    with indexed_authorships(dataset_directory / "81_documento_autor.zip", authors) as index:
        for row in unique_proposition_rows(index, dataset_directory / "56_proposituras.zip"):
            people = index.execute(
                "SELECT person FROM authors WHERE document=?", (row["IdDocumento"],)
            )
            for (person_id,) in people:
                yield normalize_proposition(row, person_id)


def unique_proposition_rows(index, path):
    """Collapse repeated export rows on disk; conflicting source versions need review."""
    index.execute("CREATE TABLE propositions(document TEXT PRIMARY KEY,content_hash TEXT)")
    for row in xml_rows(path, "propositura"):
        content_hash = hash_content(row)
        inserted = index.execute(
            "INSERT OR IGNORE INTO propositions VALUES(?,?)", (row["IdDocumento"], content_hash)
        ).rowcount
        if inserted:
            yield row
            continue
        previous = index.execute(
            "SELECT content_hash FROM propositions WHERE document=?", (row["IdDocumento"],)
        ).fetchone()[0]
        if previous != content_hash:
            raise IngestionError("ALESP_PROPOSITION_EXPORT_CONFLICT")


def normalize_proposition(row, person_id):
    year = int(row["AnoLegislativo"])
    if not 1800 <= year <= 2200 or not row["NroLegislativo"] or not row["IdNatureza"]:
        raise IngestionError("ALESP_PROPOSITION_INVALID")
    return {
        "personId": person_id,
        "officialKey": row["IdDocumento"],
        "kind": "alesp_natureza:" + row["IdNatureza"],
        "number": row["NroLegislativo"],
        "year": year,
        "title": f"ALESP {row['IdNatureza']} {row['NroLegislativo']}/{year}",
        "summary": row.get("Ementa") or None,
        "introducedOn": None,
        "publishedAt": row.get("DtPublicacao") or None,
        "role": "author",
        "coverage": "authorship_only_approval_not_inferred",
    }
