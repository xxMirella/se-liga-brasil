"""Acquire official ALESP identity evidence without resolving people or writing a database."""

import json
import re
import xml.etree.ElementTree as ElementTree
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

from crawlers.alesp.photos import normalize_profile_photo
from parsing.html import decode_html
from service.acquisition.downloader import download_resource
from service.ingestion.contracts import DownloadBudget, IngestionError, Resource
from storage.files import save_json

ROSTER_URL = "https://www.al.sp.gov.br/repositorioDados/deputados/deputados.xml"
PROFILE_BASE_URL = "https://legis-api-portal-prd.al.sp.gov.br/parlamentar-portal/detalhes/"
TELEPHONE_BASE_URL = "https://www.al.sp.gov.br/alesp/telefones/?idUA="


def nullable_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if text.lower() in {"", "null", "none"} else text


def normalize_birthday(value) -> str | None:
    text = nullable_text(value)
    if text is None or not re.fullmatch(r"\d{2}/\d{2}", text):
        return None
    try:
        datetime.strptime(f"{text}/2000", "%d/%m/%Y")
    except ValueError:
        return None
    return text


def parse_identity_roster(payload: bytes) -> list[dict]:
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as error:
        raise IngestionError("ALESP_IDENTITY_ROSTER_INVALID_XML") from error
    if root.tag != "Deputados" or not 1 <= len(root) <= 500:
        raise IngestionError("ALESP_IDENTITY_ROSTER_SCHEMA_CHANGED")
    members, identifiers = [], set()
    for member in root:
        item = {child.tag: nullable_text(child.text) for child in member}
        keys = (item.get("IdDeputado"), item.get("Matricula"), item.get("IdUA"))
        if any(not value or not value.isdigit() for value in keys):
            raise IngestionError("ALESP_IDENTITY_ROSTER_IDENTIFIER_MISSING")
        if keys[0] in identifiers:
            raise IngestionError("ALESP_IDENTITY_ROSTER_DUPLICATE_SUBJECT")
        identifiers.add(keys[0])
        members.append(item)
    return members


class TelephoneEvidenceParser(HTMLParser):
    """Read explicit paragraphs/headings and links; HTML comments never become evidence."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.paragraphs: list[str] = []
        self.headings: list[str] = []
        self.matriculas: set[str] = set()
        self.active_tag: str | None = None
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        if tag in {"p", "h5"}:
            self.active_tag, self.parts = tag, []
        if tag == "a":
            href = dict(attrs).get("href", "")
            parsed = urlsplit(href)
            if parsed.path == "/deputado/":
                self.matriculas.update(parse_qs(parsed.query).get("matricula", []))

    def handle_data(self, data) -> None:
        if self.active_tag:
            self.parts.append(data)

    def handle_endtag(self, tag) -> None:
        if tag == self.active_tag:
            text = " ".join("".join(self.parts).split())
            (self.paragraphs if tag == "p" else self.headings).append(text)
            self.active_tag = None


def parse_telephone_evidence(payload: bytes, matricula: str) -> dict:
    parser = TelephoneEvidenceParser()
    parser.feed(decode_html(payload))
    names = [
        text.partition(":")[2].strip()
        for text in parser.paragraphs
        if text.startswith("Responsável:")
    ]
    if len(names) != 1 or not names[0]:
        raise IngestionError("ALESP_TELEPHONE_RESPONSIBLE_AMBIGUOUS")
    if parser.matriculas and parser.matriculas != {matricula}:
        raise IngestionError("ALESP_TELEPHONE_MATRICULA_MISMATCH")
    headings = [text for text in parser.headings if text.upper().startswith("GABINETE DEP.")]
    if len(headings) != 1:
        raise IngestionError("ALESP_TELEPHONE_GABINET_MISSING")
    return {
        "legal_name": names[0],
        "membership_evidence": {
            "gabinet_heading": headings[0],
            "profile_link_confirmed": matricula in parser.matriculas,
            "role_deputy_confirmed": "Cargo: Deputado(a)" in parser.paragraphs,
        },
    }


def parse_member_profile(payload: bytes, member: dict) -> dict:
    try:
        profile = json.loads(payload)
    except (ValueError, UnicodeDecodeError) as error:
        raise IngestionError("ALESP_IDENTITY_PROFILE_INVALID_JSON") from error
    if not isinstance(profile, dict) or (
        str(profile.get("nuMatricula")) != member["Matricula"]
        or str(profile.get("idParlamentar")) != member["IdDeputado"]
    ):
        raise IngestionError("ALESP_IDENTITY_PROFILE_SUBJECT_MISMATCH")
    biography = profile.get("biografia") or {}
    if not isinstance(biography, dict):
        raise IngestionError("ALESP_IDENTITY_PROFILE_SCHEMA_CHANGED")
    birthday = normalize_birthday(biography.get("dtAniversario"))
    roster_birthday = normalize_birthday(member.get("Aniversario"))
    if birthday and roster_birthday and birthday != roster_birthday:
        raise IngestionError("ALESP_IDENTITY_BIRTHDAY_CONFLICT")
    names = {nullable_text(profile.get(field)) for field in ("txNomeParlamentar", "txNomePlenario")}
    names.add(member.get("NomeParlamentar"))
    return {
        "parliamentary_names": sorted(name for name in names if name),
        "birthday": birthday or roster_birthday,
        "photo_url": normalize_profile_photo(biography.get("txFotoGrande")),
        "political_party_abbreviation": nullable_text(profile.get("txPartido")),
        "political_party_code": current_party_code(profile),
        "is_in_office": profile.get("isEmExercicio")
        if isinstance(profile.get("isEmExercicio"), bool)
        else None,
        "affiliations": profile.get("listaFiliacoes") or [],
        "mandates": profile.get("listaMandatos") or [],
    }


def current_party_code(profile: dict) -> str | None:
    affiliations = profile.get("listaFiliacoes") or []
    if not isinstance(affiliations, list):
        raise IngestionError("ALESP_IDENTITY_PROFILE_SCHEMA_CHANGED")
    codes = set()
    for affiliation in affiliations:
        if not isinstance(affiliation, dict):
            raise IngestionError("ALESP_IDENTITY_PROFILE_SCHEMA_CHANGED")
        political_party = affiliation.get("partido") or {}
        if not isinstance(political_party, dict):
            raise IngestionError("ALESP_IDENTITY_PROFILE_SCHEMA_CHANGED")
        if nullable_text(affiliation.get("dtFim")) is None:
            code = nullable_text(political_party.get("nuLegenda"))
            if code:
                codes.add(code.zfill(2))
    return next(iter(codes)) if len(codes) == 1 else None


def identity_resource(identifier: str, url: str, suffix: str) -> Resource:
    return Resource(
        f"alesp-identity-{identifier}",
        f"ALESP identity {identifier}",
        url,
        "identity_evidence",
        datetime.now(UTC).year,
        "alesp-identity",
        "SP",
        file_suffix=suffix,
    )


def acquire_identity_resource(resource, configuration, client, budget) -> tuple[bytes, dict]:
    artifact = download_resource(resource, configuration, client, budget)
    source = {
        "url": resource.url,
        "path": str(artifact.path),
        "sha256": artifact.sha256,
        "fetched_at": artifact.fetched_at,
        "acquisition_status": artifact.acquisition_status,
    }
    return artifact.path.read_bytes(), source


def collect_member_evidence(member, roster_source, configuration, client, budget) -> dict:
    matricula = member["Matricula"]
    evidence = {
        "source_subject_id": member["IdDeputado"],
        "matricula": matricula,
        "administrative_unit_id": member["IdUA"],
        "legal_name": None,
        "parliamentary_names": [member["NomeParlamentar"]] if member.get("NomeParlamentar") else [],
        "birthday": normalize_birthday(member.get("Aniversario")),
        "political_party_abbreviation": member.get("Partido"),
        "political_party_code": None,
        "sources": [roster_source],
        "source_errors": [],
    }
    resources = (
        (
            "profile",
            identity_resource(f"profile-{matricula}", PROFILE_BASE_URL + matricula, ".json"),
        ),
        (
            "telephone",
            identity_resource(
                f"telephone-{member['IdUA']}", TELEPHONE_BASE_URL + member["IdUA"], ".html"
            ),
        ),
    )
    for kind, resource in resources:
        try:
            payload, source = acquire_identity_resource(resource, configuration, client, budget)
            evidence["sources"].append(source | {"evidence_kind": kind})
            parsed = (
                parse_member_profile(payload, member)
                if kind == "profile"
                else parse_telephone_evidence(payload, matricula)
            )
            evidence.update(parsed)
        except Exception as error:
            evidence["source_errors"].append(
                {
                    "url": resource.url,
                    "evidence_kind": kind,
                    "code": error.code
                    if isinstance(error, IngestionError)
                    else type(error).__name__,
                }
            )
            if isinstance(error, IngestionError) and error.code == "RUN_DOWNLOAD_LIMIT_EXCEEDED":
                raise
    return evidence


def collect_identity_evidence(configuration, client) -> list[dict]:
    """Use shared immutable archives/cache and one download budget for the entire collection."""
    budget = DownloadBudget()
    resource = identity_resource("roster", ROSTER_URL, ".xml")
    payload, roster_source = acquire_identity_resource(resource, configuration, client, budget)
    roster = parse_identity_roster(payload)
    evidence = []
    manifest = configuration.storage_directory / "identity-evidence.json"
    for member in roster:
        evidence.append(
            collect_member_evidence(member, roster_source, configuration, client, budget)
        )
        save_json(manifest, evidence)
    return evidence
