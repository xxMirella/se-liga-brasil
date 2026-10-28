"""Audit national orientation evidence year by year without inventing missing labels."""

import argparse
import json
from collections import Counter
from pathlib import Path

from service.political_dashboard.orientation_historical_context import (
    documented_legislative_absence,
)
from service.political_dashboard.orientation_timeline import orientation_cell

MANIFEST_NAMES = (
    "presidency-manifest.json", "senate-history-manifest.json",
    "senate-elections-manifest.json", "senate-reports-manifest.json",
    "camara-history-manifest.json", "camara-full-history-manifest.json", "manifest-2026.json",
)


def national_partitions(directory):
    """Later manifests supersede earlier observations of the same institution/year."""
    indexed = {}
    for name in MANIFEST_NAMES:
        manifest = json.loads((directory / name).read_text())
        partitions = manifest.get("partitions", []) if isinstance(manifest, dict) else manifest
        for row in partitions:
            if row["territory_code"] == "BR":
                indexed[(row["institution_code"], row["year"])] = row
    return indexed


def annual_orientation_record(directory, partition, institution_code, year):
    result = {"year": year, "institution_code": institution_code, "sources": []}
    absence = documented_legislative_absence(institution_code, year)
    if absence:
        return result | {"status": "suspended", **absence,
                         "sources": [row["source_url"] for row in absence["source_evidence"]]}
    if institution_code == "presidency" and year < 1889:
        return result | {"status": "not_applicable", "label": "Presidência inexistente"}
    if partition is None:
        return result | {"status": "missing_composition", "label": "Sem composição publicada"}
    payload = json.loads((directory / partition["file"]).read_text())
    result["composition_file"] = partition["file"]
    result["composition_coverage"] = payload.get("coverage")
    result["institutional_status"] = payload.get("institutional_status")
    if payload.get("institutional_status") == "suspended_whole_year":
        return result | {"status": "suspended", "label": "Sem funcionamento"}
    kind = "executive" if institution_code == "presidency" else "legislative"
    cell = orientation_cell(payload, year, kind)
    result.update(label=cell["label"], detail=cell.get("detail"), state=cell["state"])
    result["evidence"] = cell.get("source_evidence", [])
    result["sources"] = sorted({row["source_url"] for row in result["evidence"]})
    counts = orientation_counts(payload, year) if kind == "legislative" else {}
    if kind == "legislative" and any(key in counts for key in ("left", "center", "right")):
        from service.political_dashboard.political_orientation_catalog import (
            ORIENTATION_METHODOLOGY_URL,
        )

        result["sources"].append(ORIENTATION_METHODOLOGY_URL)
    result["orientation_counts"] = counts
    classified = sum(counts.get(key, 0) for key in ("left", "center", "right"))
    documented = bool(result["evidence"]) or classified > 0
    result["status"] = "documented_partial" if documented else "no_dated_classification"
    result["exercise_segments"] = [
        {key: segment.get(key) for key in ("exercise_id", "name", "starts_on", "ends_before")}
        for segment in payload.get("segments", [])
    ]
    return result


def orientation_counts(payload, year):
    from service.political_dashboard.orientation_composition import group_orientation_category

    counts = Counter()
    for group in payload.get("political_parties", []):
        category = group_orientation_category(group, year, payload.get("institution_code"))
        counts[category] += group.get("count", 0)
    return dict(counts)


def audit_orientation_years(directory, first_year, last_year):
    partitions = national_partitions(directory)
    return [annual_orientation_record(directory, partitions.get((code, year)), code, year)
            for year in range(first_year, last_year + 1)
            for code in ("presidency", "senado", "camara")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("data/political-dashboard"))
    parser.add_argument("--first-year", type=int, default=1880)
    parser.add_argument("--last-year", type=int, default=2026)
    parser.add_argument("--output", type=Path,
                        default=Path("data/political-orientation/annual-audit-1880-2026.json"))
    options = parser.parse_args()
    rows = audit_orientation_years(options.directory, options.first_year, options.last_year)
    report = {"schema_version": "political_orientation_annual_audit.v1",
              "as_of": "2026-10-28", "year_start": options.first_year,
              "year_end": options.last_year, "records": rows,
              "limitation": "Annual rows audit existing evidence, not annual independent "
                            "measurements. Missing labels are research tasks, never center.",
              "status_counts": dict(Counter(row["status"] for row in rows))}
    options.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["status_counts"]))


if __name__ == "__main__":
    main()
