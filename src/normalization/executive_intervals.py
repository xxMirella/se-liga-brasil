"""Pure interval normalization for documented executive substitutions."""

from collections import defaultdict
from datetime import date, timedelta


def remove_documented_temporary_overlap(records):
    temporary_by_institution = defaultdict(list)
    for row in records:
        if row.get("exercise_kind") == "temporary":
            temporary_by_institution[executive_institution_key(row)].append(row)
    result = []
    for row in records:
        replacements = temporary_by_institution[executive_institution_key(row)]
        result.extend(split_documented_holder(row, replacements))
    return result


def executive_institution_key(row):
    return row.get("territory_code"), row.get("institution_code")


def split_documented_holder(row, replacements):
    if row.get("exercise_kind") != "holder":
        return [row]
    end = row.get("ends_before")
    if not end and row.get("observed_through"):
        end = (date.fromisoformat(row["observed_through"]) + timedelta(days=1)).isoformat()
    if not end:
        return [row]
    intervals = [(row["starts_on"], end)]
    for replacement in replacements:
        if replacement["starts_on"] >= row["starts_on"] and replacement["ends_before"] <= end:
            intervals = subtract_interval(intervals, replacement)
    result = []
    for first, last in intervals:
        actual_end = None if last == end and not row.get("ends_before") else last
        result.append(dict(row, starts_on=first, ends_before=actual_end))
    return result


def subtract_interval(intervals, replacement):
    result = []
    for first, last in intervals:
        start, end = replacement["starts_on"], replacement["ends_before"]
        if start >= last or end <= first:
            result.append((first, last))
            continue
        if first < start:
            result.append((first, start))
        if end < last:
            result.append((end, last))
    return result
