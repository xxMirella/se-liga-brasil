"""Validate explicitly dated aggregate bancadas; never infer affiliation from elections."""

import re
from collections import Counter
from datetime import date

SINGLE_POLITICAL_PARTY_HEADERS = {
    "PARTIDO TRABALHISTA BRASILEIRO": "PTB",
    "PARTIDO DEMOCRÁTICO TRABALHISTA": "PDT",
    "PARTIDO SOCIALISMO E LIBERDADE": "PSOL",
    "PARTIDO COMUNISTA DO BRASIL": "PCdoB",
    "PARTIDO MUNICIPALISTA RENOVADOR": "PMR",
    "PARTIDO SOCIAL CRISTÃO": "PSC", "PARTIDO VERDE": "PV",
    "PARTIDO SOCIAL DEMOCRÁTICO": "PSD", "PARTIDO DA REPÚBLICA": "PR",
    "PARTIDO RENOVADOR TRABALHISTA BRASILEIRO": "PRTB",
}
FINAL_SECTION = re.compile(
    r"(?:B|C)\.4\s*[–-][^\n]*(?:COMPOSIÇÃO FINAL DAS BANCADAS|"
    r"REPRESENTAÇÕES DOS PARTIDOS[^\n]*AO FINAL|BANCADAS DOS PARTIDOS[^\n]*AO FINAL)[^\n]*"
)
COUNTS = re.compile(r"(?:Em\s+\d{1,2}/\d{1,2}/\d{4}:\s*|\(\s*)(\d+)\s+integrante")
DATED = re.compile(r"\bEm\s+(\d{1,2})/(\d{1,2})/(\d{4})")
COMPONENT = re.compile(r"\b([A-Za-z][A-Za-z0-9]*):\s*(\d+)")


def final_composition_section(content):
    starts = list(FINAL_SECTION.finditer(content))
    if not starts:
        raise ValueError("SENATE_REPORT_FINAL_COMPOSITION_SECTION_NOT_RECOGNIZED")
    start = starts[-1].start()
    section = content[start:]
    end = re.search(r"(?:B|C)\.5\s*[–-]", section)
    if end:
        section = section[:end.start()]
    return section, content[:start].count("\f") + 1


def infer_single_header(context):
    upper = context.upper()
    candidates = [(upper.rfind(header), abbreviation)
                  for header, abbreviation in SINGLE_POLITICAL_PARTY_HEADERS.items()
                  if header in upper]
    if "SEM PARTIDO" in upper:
        candidates.append((upper.rfind("SEM PARTIDO"), "S/Partido"))
    candidates.extend((match.start(), "PMDB") for match in re.finditer(
        r"MAIORIA\s*\(\s*PMDB\s*\)", upper
    ))
    if candidates:
        return max(candidates)[1]
    raise ValueError("SENATE_REPORT_SINGLE_POLITICAL_PARTY_HEADER_NOT_RECOGNIZED")


def parse_aggregate_group(lines, index, match):
    context = "\n".join(lines[max(0, index - 9):index + 1])
    component_text = lines[index] + " " + (lines[index + 1] if index + 1 < len(lines) else "")
    declared = int(match[1])
    components = COMPONENT.findall(component_text)
    if components:
        if sum(int(count) for _, count in components) != declared:
            raise ValueError("SENATE_REPORT_BLOC_COMPONENT_SUM_MISMATCH")
        counts = {abbreviation: int(count) for abbreviation, count in components}
    else:
        counts = {infer_single_header(context): declared}
    dates = DATED.findall(context)
    if not dates:
        raise ValueError("SENATE_REPORT_GROUP_HAS_NO_EXPLICIT_REFERENCE_DATE")
    day, month, year = dates[-1]
    return counts, date(int(year), int(month), int(day)).isoformat()


def parse_final_senate_composition(content, year, evidence):
    section, first_page = final_composition_section(content)
    lines = section.splitlines()
    counts, dates = Counter(), set()
    for index, line in enumerate(lines):
        if match := COUNTS.search(line):
            group, reference_on = parse_aggregate_group(lines, index, match)
            counts.update(group)
            dates.add(reference_on)
    return validated_composition_counts(counts, dates, year, evidence, first_page)


def validated_composition_counts(counts, dates, year, evidence, first_page):
    if len(dates) != 1 or not next(iter(dates), "").startswith(str(year)):
        raise ValueError("SENATE_REPORT_GROUP_REFERENCE_DATES_DISAGREE")
    if sum(counts.values()) != 81 or not 1995 <= year <= 2025:
        raise ValueError("SENATE_REPORT_COMPOSITION_TOTAL_NOT_VERIFIED")
    return {
        "year": year, "reference_on": next(iter(dates)), "total": 81,
        "political_parties": [{"abbreviation": name, "count": count}
                              for name, count in sorted(counts.items()) if count > 0],
        "evidence": {**{key: evidence[key] for key in ("url", "sha256", "fetched_at")
                        if key in evidence},
                     "locator": f"Composição final das bancadas; PDF p. {first_page}",
                     "first_pdf_page": first_page},
    }
