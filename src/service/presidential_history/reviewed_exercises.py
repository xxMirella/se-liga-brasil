"""Explicit reviewed source corrections keep official mandate distinct from actual exercise."""

from copy import deepcopy

from crawlers.presidency.archive_parsing import archive_exercise
from crawlers.presidency.parsing import extract_chronology_text
from service.ingestion.contracts import IngestionError

CASTELO_SOURCE_URL = "https://www.al.sp.gov.br/repositorio/ementario/anexos/094aSO010628.htm"
CASTELO_LOCATOR = "CASTELLO BRANCO (CEARENSE) ‑15/04/1964 A 15/03/1967"
TEMER_SOURCE_URL = (
    "https://www.camara.leg.br/noticias/497259-michel-temer-toma-posse-como-presidente-da-republica/"
)
TEMER_LOCATOR = ("no dia 12 de maio de 2016, Michel Temer assumiu interinamente "
                 "a Presidência da República")


def acquire_reviewed_exercise_source(acquisition, url, locator):
    artifact = acquisition.acquire(url)
    text = " ".join(extract_chronology_text(artifact.path.read_bytes()).split())
    if locator not in text:
        raise IngestionError("REVIEWED_PRESIDENTIAL_EXERCISE_SOURCE_CHANGED")
    return artifact, {"url": url, "sha256": artifact.sha256,
                      "fetched_at": artifact.fetched_at, "locator": locator}


def restore_castelo_exercise(acquisition, exercises, observed_on):
    identifier = "arquivo-nacional-president:196"
    if any(row["person_id"] == identifier for row in exercises):
        return None
    artifact, evidence = acquire_reviewed_exercise_source(
        acquisition, CASTELO_SOURCE_URL, CASTELO_LOCATOR,
    )
    record = archive_exercise("Humberto de Alencar Castelo Branco", "196",
                              "15.4.1964 - 15.3.1967", artifact, observed_on)
    record["evidence"] = [evidence]
    record["source_correction"] = "archive_header_was_lifespan_not_presidential_exercise"
    exercises.append(record)
    return {"person_id": identifier, "kind": record["source_correction"], "evidence": evidence}


def split_temer_interim_exercise(acquisition, exercises):
    indexed = {row["person_id"]: row for row in exercises}
    temer = indexed.get("arquivo-nacional-president:201")
    dilma = indexed.get("arquivo-nacional-president:205")
    if not temer or not dilma or temer["starts_on"] != "2016-08-31":
        return None
    _, evidence = acquire_reviewed_exercise_source(acquisition, TEMER_SOURCE_URL, TEMER_LOCATOR)
    interim = deepcopy(temer)
    interim.update(starts_on="2016-05-12", ends_before="2016-08-31",
                   exercise_id=temer["person_id"] + ":2016-05-12",
                   exercise_capacity="acting_president",
                   source_url=TEMER_SOURCE_URL, evidence=[evidence])
    dilma["official_term_ends_before"] = dilma["ends_before"]
    dilma["ends_before"] = "2016-05-12"
    dilma["evidence"].append(evidence)
    exercises.append(interim)
    return {"person_id": temer["person_id"], "kind": "interim_exercise_separate_from_mandate",
            "evidence": evidence}


def apply_reviewed_exercise_corrections(acquisition, exercises, *, observed_on):
    corrected = deepcopy(exercises)
    corrections = []
    for operation in (
        lambda: restore_castelo_exercise(acquisition, corrected, observed_on),
        lambda: split_temer_interim_exercise(acquisition, corrected),
    ):
        correction = operation()
        if correction:
            corrections.append(correction)
    return corrected, corrections
