"""Older final-session tables use cover-dated periods and member labels within blocs."""

import re
from collections import Counter

from crawlers.senado.annual_composition import validated_composition_counts

REVIEWED_SESSION_ENDS = {
    1999: ("1999-12-15", "a 15.12.99"),
    2000: ("2000-12-15", "a 15.12.2000"),
    2001: ("2001-12-17", "a 17.12.2001"),
}
GROUP_HEADER = re.compile(r"^\s*((?:PARTIDO|BLOCO)[A-ZÁÀÃÂÉÊÍÓÔÕÚÇa-z0-9 /–-]+)"
                          r"(?:\s*\(\s*(\d+)\s+integrante[^)]*\))?\s*$")
MEMBER_LABEL = re.compile(r"\(([A-Za-z][A-Za-z0-9]*)\)")


def early_final_section(content):
    starts = list(re.finditer(
        r"Ao final da[^\n]*\n[^\n]*[Pp]artidária[^\n]*", content,
    ))
    if not starts:
        raise ValueError("SENATE_REPORT_EARLY_FINAL_SECTION_NOT_RECOGNIZED")
    start = starts[-1].start()
    section = content[start:]
    end = re.search(r"(?:B\.3|B\.2\.4)\s*[–-]", section)
    if not end:
        raise ValueError("SENATE_REPORT_EARLY_FINAL_SECTION_END_NOT_RECOGNIZED")
    return section[:end.start()], content[:start].count("\f") + 1


def collect_early_groups(section):
    groups = {}
    current = None
    for line in section.splitlines():
        if header := GROUP_HEADER.fullmatch(line):
            current = " ".join(header[1].split())
            group = groups.setdefault(current, {"declared": None, "lines": []})
            if header[2]:
                group["declared"] = int(header[2])
        if current:
            groups[current]["lines"].append(line)
            count = re.search(r"\(\s*(\d+)\s+integrante", line)
            if count:
                groups[current]["declared"] = int(count[1])
    return groups


def early_group_counts(header, group):
    if group["declared"] is None:
        raise ValueError("SENATE_REPORT_EARLY_GROUP_DECLARED_COUNT_MISSING")
    if header.startswith("BLOCO"):
        counts = Counter(MEMBER_LABEL.findall("\n".join(group["lines"])))
        if sum(counts.values()) != group["declared"]:
            raise ValueError("SENATE_REPORT_EARLY_BLOC_MEMBER_LABEL_SUM_MISMATCH")
        return counts
    abbreviation = re.search(r"[–-]\s*([A-Za-z][A-Za-z0-9]*)\s*$", header)
    if abbreviation:
        return {abbreviation[1]: group["declared"]}
    if header == "PARTIDO POPULAR SOCIALISTA":
        return {"PPS": group["declared"]}
    raise ValueError("SENATE_REPORT_EARLY_POLITICAL_PARTY_HEADER_NOT_RECOGNIZED")


def parse_early_final_senate_composition(content, year, evidence):
    reviewed = REVIEWED_SESSION_ENDS.get(year)
    if not reviewed or reviewed[1] not in content[:15000]:
        raise ValueError("SENATE_REPORT_ORDINARY_SESSION_END_NOT_VERIFIED")
    section, page = early_final_section(content)
    counts = Counter()
    for header, group in collect_early_groups(section).items():
        counts.update(early_group_counts(header, group))
    if unreported := re.search(r"SEM PARTIDO\s*[–-]\s*(\d+)", section):
        counts["S/Partido"] = int(unreported[1])
    result = validated_composition_counts(counts, {reviewed[0]}, year, evidence, page)
    result["evidence"]["reference_date_locator"] = (
        "Final da sessão legislativa ordinária; término documentado na folha de rosto: "
        + reviewed[1]
    )
    return result
