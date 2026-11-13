"""Positive, dated participation evidence with exact and unambiguous name resolution."""

import re
import subprocess
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path

from crawlers.alesp.local_records import assign_unique_person
from normalization.text import fold_text
from parsing.html import decode_html
from storage.files import hash_content, load_json


def participation_identity_indexes(resolutions, person_ids=None):
    registrations, names = {}, {}
    for resolution in resolutions:
        if resolution.get("status") != "matched":
            continue
        person = str(resolution["person_id"])
        if person_ids is not None and person not in person_ids:
            continue
        for subject in resolution.get("official_subjects", []):
            if subject.get("matricula"):
                assign_unique_person(registrations, str(subject["matricula"]), person)
            aliases = [subject.get("legal_name", ""), *subject.get("parliamentary_names", [])]
            for alias in filter(None, aliases):
                names.setdefault(fold_text(alias).replace(".", ""), set()).add(person)
    return registrations, {
        name: next(iter(people)) for name, people in names.items() if len(people) == 1
    }


def occurred_on(value):
    try:
        day = (
            datetime.strptime(value[:10], "%d/%m/%Y").date()
            if "/" in value
            else (date.fromisoformat(value[:10]))
        )
    except (ValueError, TypeError):
        return None
    return day.isoformat() if day <= date.today() else None


def participation_record(person, day, event, channel, reference, excerpt, name=None):
    return {
        "personId": person,
        "institution": "alesp",
        "date": day,
        "period": day[:7],
        "officialKey": hash_content([event, person, channel, reference["url"]]),
        "eventKey": event,
        "scope": "historical_participation_observed",
        "channel": channel,
        "presenceConfirmed": True,
        "matchedName": name,
        "sourceUrl": reference["url"],
        "sourceSha256": reference["sha256"],
        "observedAt": reference["fetched_at"],
        "excerpt": excerpt[:1200],
        "eventType": reference.get("event_type"),
    }


def structured_participation_rows(reference, registrations, names):
    payload = load_json(reference["path"], {})
    if reference["kind"] == "commission_export":
        return commission_participation_rows(payload, reference, registrations, names)
    if reference["kind"] == "meeting_participants":
        return meeting_participation_rows(payload, reference, registrations, names)
    return plenary_participation_rows(payload, reference, registrations)


def commission_participation_rows(payload, reference, registrations, names):
    for row in payload["presencasDeputadoReuniao"]:
        person = registrations.get(str(row.get("idDeputado")))
        name = row.get("deputado", "")
        day = occurred_on(row.get("dataReuniao", ""))
        if (
            person
            and names.get(fold_text(name).replace(".", "")) == person
            and day
            and row.get("idReuniao")
        ):
            yield participation_record(
                person,
                day,
                "committee:" + str(row["idReuniao"]),
                "committee_register",
                reference,
                name,
                name,
            )


def plenary_participation_rows(payload, reference, registrations):
    person = registrations.get(str(reference["registration"]))
    for row in payload:
        day = occurred_on(row.get("data", ""))
        if person and day and row.get("idSessaoPlenaria") and row.get("situacao") == "Presente":
            yield participation_record(
                person,
                day,
                "plenary:" + str(row["idSessaoPlenaria"]),
                "plenary_register",
                reference,
                row["situacao"],
            )


def meeting_participation_rows(payload, reference, registrations, names):
    day = occurred_on(payload.get("dtReuniao", ""))
    status = (payload.get("status") or {}).get("txNome")
    if not day or status not in {"Realizada", "Sem Quórum"}:
        return
    for row in payload.get("parlamentaresPresentes") or []:
        person = registrations.get(str(row.get("nuMatricula")))
        name = row.get("txNomeParlamentar", "")
        if person and names.get(fold_text(name).replace(".", "")) == person:
            yield participation_record(
                person,
                day,
                "committee:" + str(payload["idReuniao"]),
                "event_participants",
                reference,
                name,
                name,
            )


class ParticipationTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "head"}:
            self.hidden += 1
        if tag in {"p", "br", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "head"}:
            self.hidden = max(0, self.hidden - 1)
        if tag in {"p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def explicit_presence_passages(text):
    """Only presence lists and actual speaker turns qualify; roll-call pauses do not."""
    normalized = fold_text(text).replace("dr.", "dr").replace("dra.", "dra")
    list_pattern = (
        r"(?:estiveram presentes|compareceram|lista de presentes|participantes presentes|"
        r"participaram do evento|contou com a presenca de|"
        r"membros (?:efetivos|substitutos(?: eventuais)?) presentes)"
        r"\s*:?\s*(.{1,1600}?)(?=\.(?:\s|$)|\bausentes\b|\bhavendo\b|\bnada mais\b|$)"
    )
    for match in re.finditer(list_pattern, normalized):
        if normalized[: match.start()].endswith("nao "):
            continue
        yield match.group(1), "recorded_presence"
    for line in text.splitlines():
        line = re.sub(r"\bpresidente\s*-\s*", "", fold_text(line))
        match = re.match(r"(?:o sr|a sra)\.?\s+(.+?)\s+-\s+(.+)", line)
        if match and "(pausa" not in match[2] and "nao esta presente" not in match[2]:
            yield match[1].removeprefix("presidente - "), "recorded_speech"


def document_participation_rows(reference, names):
    text = participation_document_text(Path(reference["path"]))
    day = occurred_on(reference.get("event_date", ""))
    if not day or not reference.get("event_occurred"):
        return
    aliases = sorted(names, key=len, reverse=True)
    if not aliases:
        return
    pattern = re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape, aliases)) + r")(?!\w)")
    seen = set()
    for passage, proof in explicit_presence_passages(text):
        for match in pattern.finditer(passage.replace(".", "")):
            person = names[match[0]]
            if person in seen:
                continue
            seen.add(person)
            yield participation_record(
                person, day, reference["event_key"], reference["kind"], reference, passage, match[0]
            ) | {
                "proof": proof,
            }


def participation_document_text(path):
    if path.read_bytes()[:5] == b"%PDF-":
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"], capture_output=True, check=True, timeout=30
        )
        text = result.stdout.decode("utf-8")
        if not text.strip():
            raise ValueError("ALESP_PARTICIPATION_OCR_REQUIRED")
        return text
    parser = ParticipationTextParser()
    parser.feed(decode_html(path.read_bytes()))
    return "".join(parser.parts)
