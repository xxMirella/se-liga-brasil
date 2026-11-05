"""Annual party bands keep geography fixed and never manufacture undocumented majorities."""


from service.political_dashboard.composition_charts import is_political_party
from service.political_dashboard.political_palette import (
    MIXED_COLOR,
    UNKNOWN_COLOR,
    political_party_color,
)

TIMELINE_START_YEAR = 1880


def timeline_series(data):
    if data["level"] == "federal":
        return [("senado", "Senado", "legislative"),
                ("presidency", "Presidência", "executive"),
                ("camara", "Câmara dos Deputados", "legislative")]
    if data["level"] == "municipal":
        return [("municipal_government", "Prefeitura", "executive"),
                ("municipal_council", "Câmara Municipal", "legislative")]
    government = "district_government" if data["uf"] == "DF" else "state_government"
    assembly = data["assembly"].get("institution_code") or "state_assembly"
    return [("senado", "Senado · " + data["uf"], "legislative"),
            (government, "Governo estadual", "executive"),
            (assembly, "Assembleia Legislativa", "legislative")]


def timeline_institution(row, code):
    for institution in row.get("institutions", []):
        if institution["institution_code"] == code:
            return institution
        if code == "state_assembly" and set(institution.get("office_kinds") or []) & {
            "state_deputy", "district_deputy"
        }:
            return institution
    return None


def timeline_cell(row, code, kind, view="political_party"):
    if view == "political_orientation":
        from service.political_dashboard.orientation_historical_context import (
            documented_legislative_absence,
        )

        absence = documented_legislative_absence(code, row["year"])
        if absence:
            return absence
        from service.political_dashboard.senate_orientation_1992_1994 import (
            senate_1992_1994_cell,
        )

        itamar_snapshot = senate_1992_1994_cell(row["year"]) if code == "senado" else None
        if itamar_snapshot:
            return itamar_snapshot
    if row["year"] < 1889 and code == "presidency":
        return {"label": "Monarquia · Presidência ainda não existia",
                "color": UNKNOWN_COLOR, "state": "not_applicable"}
    institution = timeline_institution(row, code)
    if institution is None:
        legacy = {"senado": "senate_observations", "alesp": "assembly_observations",
                  "alerj": "assembly_observations", "presidency": "presidency_observations",
                  "state_government": "government_observations",
                  "municipal_government": "mayoralty_observations",
                  "municipal_council": "municipal_council_observations"}
        available = bool(row.get(legacy.get(code, "")))
        return {"label": "Partido não informado" if available else "Sem dados",
                "color": UNKNOWN_COLOR, "state": "unknown" if available else "missing"}
    if institution.get("institutional_status") == "suspended_whole_year":
        return {"label": "Senado sem funcionamento", "color": UNKNOWN_COLOR,
                "state": "suspended"}
    if view == "political_orientation":
        from service.political_dashboard.orientation_timeline import orientation_cell

        return orientation_cell(institution, row["year"], kind)
    return executive_cell(institution) if kind == "executive" else legislative_cell(institution)


def legislative_cell(institution):
    groups = institution.get("political_parties") or []
    known = [group for group in groups if is_political_party(group) and group.get("count", 0)]
    if not institution.get("total") or not known:
        return {"label": "Partido não informado", "color": UNKNOWN_COLOR, "state": "unknown"}
    maximum = max(group["count"] for group in known)
    leaders = [group["abbreviation"] for group in known if group["count"] == maximum]
    if len(leaders) > 1:
        return {"label": "Empate: " + " / ".join(sorted(leaders)),
                "color": MIXED_COLOR, "state": "mixed"}
    partial = (institution.get("coverage") not in {"observed_complete", "verified_current_roster"}
               or any(not is_political_party(group) for group in groups))
    return {"label": leaders[0], "color": political_party_color(leaders[0]),
            "state": "partial" if partial else "known"}


def executive_party_records(institution):
    current = institution.get("current")
    records = (institution.get("segments") or []) + (
        institution.get("national_observations") or []
    )
    has_periods = any(record.get("political_party_periods") for record in records)
    current_verified = current and str(current.get("political_party_status", "")).startswith(
        "verified_"
    ) and current.get("political_party")
    if current_verified and not has_periods:
        records = [current]
    periods = [period for record in records
               for period in (record.get("political_party_periods") or [record])]
    return periods, bool(current_verified and not has_periods)


def executive_cell(institution):
    records, snapshot = executive_party_records(institution)
    known = [record for record in records if str(record.get("political_party_status", ""))
             .startswith("verified_") and record.get("political_party")]
    parties = sorted({record["political_party"] for record in known})
    if not parties:
        return {"label": "Partido não informado", "color": UNKNOWN_COLOR, "state": "unknown"}
    if len(parties) > 1:
        return {"label": " / ".join(parties), "color": MIXED_COLOR, "state": "mixed"}
    return {"label": parties[0], "color": political_party_color(parties[0]),
            "state": "known" if snapshot else "partial"}
