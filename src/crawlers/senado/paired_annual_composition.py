"""Read the final column of explicitly paired initial/final political-party tables."""

import re
from collections import Counter
from datetime import date

from crawlers.senado.annual_composition import (
    parse_final_senate_composition,
    validated_composition_counts,
)
from crawlers.senado.early_annual_composition import (
    REVIEWED_SESSION_ENDS,
    parse_early_final_senate_composition,
)
from crawlers.senado.modern_annual_composition import parse_modern_final_senate_composition

PAIRED_REFERENCE = re.compile(r"Em\s+(\d{1,2})/(\d{1,2})/(\d{4}):\s*(\d+)\s+integrante")
POLITICAL_HEADER = re.compile(r"^\s*[A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-ZÁÀÃÂÉÊÍÓÔÕÚÇ ,()]+[–-]\s*"
                              r"([A-Za-z][A-Za-z0-9]*)\s*\**(?:\([^)]*\))?\s*$")


def parse_paired_final_senate_composition(content, year, evidence):
    starts = list(re.finditer(
        r"B\.3\s*[–-]\s*Composi[^\n]*(?:Partidos|PARTIDOS)", content, re.IGNORECASE,
    ))
    if not starts:
        raise ValueError("SENATE_REPORT_PAIRED_FINAL_SECTION_NOT_RECOGNIZED")
    start = starts[-1].start()
    section = content[start:]
    end = re.search(r"B\.4\s*[–-]", section)
    if end:
        section = section[:end.start()]
    counts, dates = Counter(), set()
    political_party = None
    for line in section.splitlines():
        if header := POLITICAL_HEADER.fullmatch(line):
            political_party = header[1]
        if "SEM PARTIDO" in line.upper():
            political_party = "S/Partido"
        references = PAIRED_REFERENCE.findall(line)
        if references:
            group, reference = paired_final_group(references, political_party, year)
            counts.update(group)
            dates.add(reference)
            political_party = None
    first_page = content[:start].count("\f") + 1
    return validated_composition_counts(counts, dates, year, evidence, first_page)


def paired_final_group(references, political_party, year):
    if len(references) != 2 or not political_party:
        raise ValueError("SENATE_REPORT_INITIAL_FINAL_COLUMNS_NOT_VERIFIED")
    day, month, source_year, count = references[-1]
    reference = date(int(source_year), int(month), int(day))
    if reference.year != year or reference.month != 12:
        raise ValueError("SENATE_REPORT_FINAL_COLUMN_REFERENCE_NOT_VERIFIED")
    return {political_party: int(count)}, reference.isoformat()


def parse_report_senate_composition(content, year, evidence):
    if year >= 2015:
        return parse_modern_final_senate_composition(content, year, evidence)
    if year in REVIEWED_SESSION_ENDS:
        return parse_early_final_senate_composition(content, year, evidence)
    try:
        return parse_final_senate_composition(content, year, evidence)
    except ValueError as error:
        if str(error) != "SENATE_REPORT_FINAL_COMPOSITION_SECTION_NOT_RECOGNIZED":
            raise
    return parse_paired_final_senate_composition(content, year, evidence)
