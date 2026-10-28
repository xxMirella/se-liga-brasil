"""Read only the explicit active fieldset of the official current legislature."""

import re
from datetime import date
from html import unescape
from urllib.parse import urljoin

from parsing.html import decode_html
from service.ingestion.contracts import IngestionError


def parse_current_roster(payload, base_url, expected_total, reference=None):
    html = decode_html(payload)
    period = re.search(r'id="ContentPlaceHolder1_legislatura_data"[^>]*>([^<]+)</h5>', html)
    if not period:
        raise IngestionError("NOPAPER_CURRENT_LEGISLATURE_DATES_MISSING")
    dates = re.findall(r"(\d{2})/(\d{2})/(\d{4})", period[1])
    if len(dates) != 2:
        raise IngestionError("NOPAPER_CURRENT_LEGISLATURE_DATES_INVALID")
    start, end = (date(int(year), int(month), int(day)) for day, month, year in dates)
    if not start <= (reference or date.today()) <= end:
        raise IngestionError("NOPAPER_LEGISLATURE_NOT_CURRENT")
    active = [
        fieldset
        for fieldset in html.split("<div class='custom-fieldset'>")[1:]
        if re.search(r"class='custom-legend[^']*'>\s*Ativo\s*</div>", fieldset)
    ]
    if len(active) != 1:
        raise IngestionError("NOPAPER_ACTIVE_FIELDSET_MISSING_OR_AMBIGUOUS")
    pattern = (
        r"<a href='(parlamentar.aspx\?id=(\d+))' class='kt-widget__username pb-1'>"
        r"\s*([^<]+)</a>\s*<span class='kt-widget__username pt-0'>\s*<small>\(([^<]+)\)</small>"
    )
    members = [
        {
            "provider_subject_id": identifier,
            "name": unescape(name).strip(),
            "political_party": unescape(political_party).strip(),
            "official_url": urljoin(base_url, path),
        }
        for path, identifier, name, political_party in re.findall(pattern, active[0])
    ]
    if len(members) != expected_total:
        raise IngestionError(
            "NOPAPER_CURRENT_ROSTER_TOTAL_MISMATCH",
            {"expected": expected_total, "observed": len(members)},
        )
    return members
