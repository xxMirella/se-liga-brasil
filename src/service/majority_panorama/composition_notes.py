"""Reader-facing coverage caveats of one house composition. Pure text, no I/O."""

from datetime import date


def format_brazilian_date(day):
    return f"{day.day:02d}/{day.month:02d}/{day.year}"


def composition_notes(window, reference_year, record, counts, house_seats, today):
    notes = [
        reference_year_note(window, reference_year, today),
        *snapshot_notes(record),
        *coverage_notes_for_total(record, house_seats),
        *classification_notes(reference_year, record, counts),
    ]
    return tuple(note for note in notes if note)


def reference_year_note(window, reference_year, today):
    if window.first_year <= today.year < window.end_year_exclusive:
        return f"Legislatura em curso: dado mais recente do banco ({reference_year})."
    if reference_year == window.last_year:
        return f"Composição de {reference_year}, último ano da legislatura."
    return (
        f"Composição de {reference_year}: o último ano da legislatura com composição verificada; "
        f"{reference_year + 1} a {window.last_year} não têm composição verificada."
    )


def snapshot_notes(record):
    snapshot_on = str(record.get("snapshot_on") or "")[:10]
    try:
        text = format_brazilian_date(date.fromisoformat(snapshot_on))
    except ValueError:
        return ()
    return (f"Fotografia anual de {text}; não comprova filiação contínua no ano.",)


def coverage_notes_for_total(record, house_seats):
    total = record["total"]
    if total < house_seats:
        return (
            f"Cobertura parcial: {total} de {house_seats} cadeiras documentadas; as demais "
            "não aparecem e a maioria é calculada sobre o total documentado.",
        )
    if record.get("coverage") == "observed_partial":
        return ("A fonte anual marca a cobertura como parcial, embora todas as cadeiras "
                "tenham sido contadas.",)
    return ()


def classification_notes(reference_year, record, counts):
    notes = []
    undetermined = counts.get("undetermined", 0)
    if undetermined:
        notes.append(
            f"{undetermined} de {record['total']} cadeiras sem classificação de partido datada "
            f"para {reference_year}; o projeto não usa classificação de outros anos."
        )
    reported = sum(group["count"] for group in record.get("political_parties") or ())
    if record["total"] > reported:
        notes.append(
            f"{record['total'] - reported} cadeiras sem partido informado na fonte, "
            "contadas em Sem classificação."
        )
    return notes
