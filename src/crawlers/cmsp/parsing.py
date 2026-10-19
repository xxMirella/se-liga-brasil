"""Bounded XML streaming, rejecting entity declarations and unexpected envelopes."""

from xml.etree import ElementTree

from crawlers.cmsp.configuration import XML_NAMESPACE
from service.ingestion.contracts import IngestionError

QUALIFIED_PROJECT = "{" + XML_NAMESPACE + "}Projeto"
ALLOWED_ROOTS = {"{" + XML_NAMESPACE + "}" + name for name in ("ArrayOfProjeto", "Projetos")}


def reject_xml_declarations(path):
    """Preflight the immutable file before the XML parser can expand entities."""
    tail = b""
    with path.open("rb") as source:
        while chunk := source.read(65536):
            inspected = (tail + chunk).upper()
            if b"\x00" in inspected or b"<!DOCTYPE" in inspected or b"<!ENTITY" in inspected:
                raise IngestionError("CMSP_UNSAFE_XML")
            tail = inspected[-16:]


def iter_projects(path, *, max_records):
    reject_xml_declarations(path)
    try:
        with path.open("rb") as source:
            events = ElementTree.iterparse(source, events=("start", "end"))
            _, root = next(events)
            if root.tag not in ALLOWED_ROOTS:
                raise IngestionError("CMSP_XML_SCHEMA_CHANGED")
            count = 0
            for event, element in events:
                if event != "end" or element.tag != QUALIFIED_PROJECT:
                    continue
                count += 1
                if count > max_records:
                    raise IngestionError("CMSP_RECORD_LIMIT_EXCEEDED")
                yield element
                element.clear()
                try:
                    root.remove(element)
                except ValueError as error:
                    raise IngestionError("CMSP_XML_SCHEMA_CHANGED") from error
            if len(root):
                raise IngestionError("CMSP_XML_SCHEMA_CHANGED")
    except (ElementTree.ParseError, StopIteration) as error:
        raise IngestionError("CMSP_INVALID_XML") from error


def element_text(element, name):
    child = element.find("{" + XML_NAMESPACE + "}" + name)
    return None if child is None else child.text


def child_elements(element, container, name):
    prefix = "{" + XML_NAMESPACE + "}"
    return element.findall(prefix + container + "/" + prefix + name)
