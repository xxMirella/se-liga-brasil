"""Resolve official author profiles in one identity batch, without persisting provider IDs."""

import re

from crawlers.camara.voting_identity import cached_profile_artifact, resolve_voting_people


def author_profile_key(row):
    match = re.fullmatch(
        r"https://dadosabertos\.camara\.leg\.br/api/v2/deputados/([1-9][0-9]*)",
        row.get("uri") or "",
    )
    return match[1] if match else None


def prepare_author_resolver(acquisition, connection, proposition_keys, maximum=25):
    from crawlers.camara.legislative_history import proposition_identifier

    keys = set()
    for official_key in dict.fromkeys(proposition_keys):
        identifier = proposition_identifier(official_key)
        for rows, _ in acquisition.pages(
            f"proposicoes/{identifier}/autores", "camara_legislative_autores"
        ):
            keys.update(key for row in rows if (key := author_profile_key(row)))
    artifacts, downloaded = {}, 0
    for key in sorted(keys, key=int):
        artifact = cached_profile_artifact(acquisition.configuration, key)
        if artifact is None and downloaded < maximum:
            _, artifact = acquisition.json_document(f"deputados/{key}", "camara_profile")
            downloaded += 1
        if artifact:
            artifacts[key] = artifact
    index = resolve_voting_people(connection, artifacts)

    def resolve(row):
        return (index.get(author_profile_key(row)) or {}).get("person_id")

    return resolve, {
        "authors_requested": len(keys), "authors_resolved": len(index),
        "identity_unresolved": len(keys) - len(index), "profile_downloads": downloaded,
    }
