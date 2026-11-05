"""Presidential terms from 1985 onward: dated exercises, documented party labels, government bloc.

The bloc comes from the project's reviewed government evidence
(`classify_executive_orientation`), never from the party label. A term whose years carry more
than one classification, or a documented dispute, is `controversial`; a term with no reviewed
evidence is `undetermined`. Nothing is inferred.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from service.majority_panorama.contracts import PresidentialTerm
from service.majority_panorama.legislature_windows import window_containing

FIRST_TERM_START = date(1985, 1, 1)
SHORT_NAMES_BY_PERSON_ID = {
    "arquivo-nacional-president:198": "Sarney",
    "arquivo-nacional-president:200": "Collor",
    "arquivo-nacional-president:203": "Itamar",
    "arquivo-nacional-president:197": "FHC",
    "arquivo-nacional-president:204": "Lula",
    "arquivo-nacional-president:205": "Dilma",
    "arquivo-nacional-president:201": "Temer",
    "arquivo-nacional-president:199": "Bolsonaro",
}
NO_PARTY_LABEL = "sem partido"


@dataclass(frozen=True)
class PresidentialExercise:
    """One dated stretch of presidential exercise (interim and definitive are separate)."""

    exercise_id: str
    person_id: str
    full_name: str
    starts_on: date
    ends_before: date | None
    party_labels: tuple[str, ...]
    official_url: str | None = None
    party_limitation: str | None = None


def collect_presidential_exercises(segments_by_year, identities):
    """Join yearly segments (dates, party periods) with exercise identities (name, URL).

    `segments_by_year`: {year: [segment]}; `identities`: {exercise_id: {name, official_url,
    political_party_limitation}}. An exercise without a name is a data error and raises.
    """
    labels, base = {}, {}
    for year in sorted(segments_by_year):
        for segment in segments_by_year[year]:
            if segment["starts_on"] < FIRST_TERM_START.isoformat():
                continue
            base.setdefault(segment["exercise_id"], segment)
            known = labels.setdefault(segment["exercise_id"], [])
            known.extend(label for label in segment_party_labels(segment) if label not in known)
    exercises = [
        exercise_from_segment(segment, identities.get(exercise_id), tuple(labels[exercise_id]))
        for exercise_id, segment in base.items()
    ]
    return tuple(sorted(exercises, key=lambda exercise: exercise.starts_on))


def segment_party_labels(segment):
    periods = sorted(
        segment.get("political_party_periods") or (), key=lambda row: row.get("starts_on") or ""
    )
    labels = [row["political_party"] for row in periods if row.get("political_party")]
    if not labels and segment.get("political_party"):
        labels = [segment["political_party"]]
    return labels


def exercise_from_segment(segment, identity, party_labels):
    if not identity or not identity.get("name"):
        raise ValueError("PRESIDENT_NAME_MISSING")
    ends_before = segment.get("ends_before")
    return PresidentialExercise(
        exercise_id=segment["exercise_id"],
        person_id=segment["person_id"],
        full_name=identity["name"],
        starts_on=date.fromisoformat(segment["starts_on"]),
        ends_before=date.fromisoformat(ends_before) if ends_before else None,
        party_labels=party_labels,
        official_url=identity.get("official_url"),
        party_limitation=identity.get("political_party_limitation"),
    )


def merge_consecutive_exercises(exercises):
    """Groups of back-to-back exercises of the same person (interim then definitive)."""
    groups = []
    for exercise in exercises:
        last = groups[-1][-1] if groups else None
        if last and last.person_id == exercise.person_id and last.ends_before == exercise.starts_on:
            groups[-1].append(exercise)
        else:
            groups.append([exercise])
    return groups


def term_end(group, today):
    """Exclusive end of a term; the incumbent's is the end of the current legislature window."""
    end = group[-1].ends_before
    return end if end else window_containing(today, today).ends_on_exclusive


def term_years(start, end, today):
    return range(start.year, min((end - timedelta(days=1)).year, today.year) + 1)


def group_party_label(group):
    labels = []
    for exercise in group:
        labels.extend(label for label in exercise.party_labels if label not in labels)
    return " / ".join(labels) if labels else NO_PARTY_LABEL


def build_presidential_terms(exercises, today):
    started = [exercise for exercise in exercises if exercise.starts_on >= FIRST_TERM_START]
    terms = []
    for group in merge_consecutive_exercises(started):
        end = term_end(group, today)
        bloc_key, notes, urls = government_bloc(group, term_years(group[0].starts_on, end, today))
        terms.append(term_from_group(group, end, bloc_key, notes, urls))
    return tuple(terms)


def term_from_group(group, end, bloc_key, bloc_notes, evidence_urls):
    first = group[0]
    short_name = SHORT_NAMES_BY_PERSON_ID.get(first.person_id, first.full_name.split()[-1])
    return PresidentialTerm(
        full_name=first.full_name,
        short_name=short_name,
        political_party_label=group_party_label(group),
        bloc_key=bloc_key,
        start_on=first.starts_on,
        end_on=end,
        span_label=f"{first.starts_on.year}–{(end - timedelta(days=1)).year}",
        source_url=first.official_url,
        notes=(*party_notes(group), *bloc_notes),
        bloc_evidence_urls=evidence_urls,
    )


def party_notes(group):
    limitations = {exercise.party_limitation for exercise in group if exercise.party_limitation}
    notes = ["O partido é o atribuído ao mandato pela fonte; não prova filiação contínua."]
    if any(exercise.party_limitation for exercise in group) and len(limitations) > 1:
        notes.append("Há mais de um registro de partido no mandato; todos são exibidos.")
    return tuple(notes)


def government_bloc(group, years):
    """(bloc key, notes, evidence URLs) from the reviewed government evidence of each year."""
    from service.political_dashboard.executive_orientation_evidence import (
        classify_executive_orientation,
    )

    by_year, urls = {}, []
    for year in years:
        covering = [exercise for exercise in group if exercise_covers_year(exercise, year)]
        found = [classify_executive_orientation(item.exercise_id, year) for item in covering]
        documented = [row for row in found if row["category"] != "undetermined"]
        if documented:
            by_year[year] = documented[0]
            urls.extend(
                row["source_url"] for row in documented
                if row.get("source_url") and row["source_url"] not in urls
            )
    return bloc_from_yearly_evidence(by_year), evidence_notes(by_year, years), tuple(urls)


def exercise_covers_year(exercise, year):
    return exercise.starts_on.year <= year and (
        exercise.ends_before is None or year <= exercise.ends_before.year
    )


def bloc_from_yearly_evidence(by_year):
    categories = {found["category"] for found in by_year.values()}
    if not categories:
        return "undetermined"
    return categories.pop() if len(categories) == 1 else "controversial"


def evidence_notes(by_year, years):
    from service.political_dashboard.orientation_timeline import ORIENTATION_LABELS

    if not by_year:
        return ("Sem análise de governo revisada para este mandato; bloco não classificado.",)
    notes = []
    categories = {found["category"] for found in by_year.values()}
    if len(categories) > 1:
        runs = "; ".join(
            f"{ORIENTATION_LABELS[found['category']]} em {year}" for year, found in by_year.items()
        )
        notes.append(f"Classificações divergentes no mandato ({runs}); exibido como controverso.")
    unreviewed = [year for year in years if year not in by_year]
    if unreviewed:
        notes.append(
            "Sem análise de governo revisada em " + ", ".join(map(str, unreviewed)) + "."
        )
    notes.append(
        "Bloco do governo conforme síntese editorial revisada, não do partido; "
        "não classifica Congresso nem aliados."
    )
    limitations = {text for found in by_year.values() for text in found.get("limitations", ())}
    notes.extend(sorted(limitations))
    return tuple(notes)


def presidents_in_legislature(terms, window):
    """Terms that held office at any moment of the legislature window, chronologically."""
    start, end = date(window.first_year, 1, 1), window.ends_on_exclusive
    return tuple(term for term in terms if term.start_on < end and term.end_on > start)
