"""Validate reviewed passages against immutable original source documents."""

from crawlers.state_government.parsing import evidence, source_exercise, visible_text


def documented_exercise(artifact, name, uf, start, end, required_text, text=None):
    content = text if text is not None else visible_text(artifact.path.read_bytes())
    if required_text not in content:
        raise ValueError("STATE_GOVERNMENT_EVIDENCE_TEXT_NOT_FOUND:" + name)
    result = source_exercise(name, uf, name)
    result.update(
        starts_on=start,
        ends_before=end,
        date_precision="day",
        observed_through=start if not end else None,
        source_url=artifact.resource.url,
        evidence=[evidence(artifact, required_text)],
    )
    return result
