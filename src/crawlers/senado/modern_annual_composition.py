"""Read explicit initial/final aggregate columns and the report's dated session boundary."""

import re
from collections import Counter
from datetime import date

from crawlers.senado.annual_composition import validated_composition_counts

KNOWN_MODERN_LABELS = frozenset(name.casefold() for name in (
    "PMDB", "MDB", "PSDB", "PFL", "DEM", "PL", "PR", "PP", "PSB", "PSD", "PT", "PDT",
    "PODE", "PODEMOS", "PSL", "PRTB", "PRB", "REPUBLICANOS", "PROS", "PPS", "CIDADANIA",
    "PCdoB", "PSOL", "PSC", "PTB", "PTC", "PV", "REDE", "AVANTE", "PATRIOTA", "PATRI", "PRP",
    "PEN", "PMB", "DC", "SD", "SDD", "SOLIDARIEDADE", "UNIÃO", "UNIAO", "NOVO",
    "Sem partido", "S/Partido",
))
COUNTS = re.compile(r"\b(\d+)\s+INTEGRANTES?\b", re.IGNORECASE)
LEFT_LABEL = re.compile(r"^\s{0,35}([A-Za-zÀ-ÿ/]+(?:\s+partido)?)\**(?:\s{2,}|$)",
                        re.IGNORECASE)


def modern_composition_section(content):
    starts = list(re.finditer(r"B\.2\.1\s*[–-]\s*COMPOSIÇÃO E ALTERAÇÕES", content, re.IGNORECASE))
    if not starts:
        raise ValueError("SENATE_REPORT_MODERN_TABLE_SECTION_NOT_RECOGNIZED")
    start = starts[-1].start()
    section = content[start:]
    end = re.search(r"B\.2\.2\s*[–-]", section)
    if not end:
        raise ValueError("SENATE_REPORT_MODERN_TABLE_SECTION_END_NOT_RECOGNIZED")
    return section[:end.start()], content[:start].count("\f") + 1


def report_session_reference(content, year):
    references = re.findall(
        rf"PERÍODO\s+DE\s+\d{{1,2}}/\d{{1,2}}/{year}\s+A\s+(\d{{1,2}})/(\d{{1,2}})/{year}",
        content[:15000], re.IGNORECASE,
    )
    dates = {date(year, int(month), int(day)).isoformat() for day, month in references}
    if len(dates) != 1:
        raise ValueError("SENATE_REPORT_MODERN_SESSION_REFERENCE_NOT_VERIFIED")
    return dates.pop()


def modern_group_label(lines):
    labels = set()
    for line in lines:
        match = LEFT_LABEL.match(line)
        if match and match[1].casefold() in KNOWN_MODERN_LABELS:
            labels.add(match[1])
    if len(labels) != 1:
        raise ValueError("SENATE_REPORT_MODERN_GROUP_LABEL_NOT_UNAMBIGUOUS")
    label = labels.pop()
    return "S/Partido" if label.casefold() in {"sem partido", "s/partido"} else label


def parse_modern_final_senate_composition(content, year, evidence):
    section, page = modern_composition_section(content)
    reference = report_session_reference(content, year)
    lines = section.splitlines()
    count_rows = [index for index, line in enumerate(lines) if COUNTS.search(line)]
    counts = Counter()
    for offset, index in enumerate(count_rows):
        values = COUNTS.findall(lines[index])
        if len(values) != 2:
            raise ValueError("SENATE_REPORT_MODERN_INITIAL_FINAL_COUNTS_NOT_VERIFIED")
        end = count_rows[offset + 1] if offset + 1 < len(count_rows) else len(lines)
        segment = trim_modern_table_body(lines[index:end])
        label = modern_group_label(segment)
        if label in counts:
            raise ValueError("SENATE_REPORT_MODERN_POLITICAL_PARTY_REPEATED")
        counts[label] = int(values[-1])
    result = validated_composition_counts(counts, {reference}, year, evidence, page)
    result["evidence"]["reference_date_locator"] = (
        "Final da sessão; período explícito na folha de rosto"
    )
    return result


def trim_modern_table_body(lines):
    for index, line in enumerate(lines):
        if re.match(r"^\s*(?:Alterações ocorridas|SENADORES QUE MUDARAM DE PARTIDO)",
                    line, re.IGNORECASE):
            return lines[:index]
    return lines
