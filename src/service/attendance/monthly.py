"""Linear monthly consolidation of unique official day records."""

from collections import Counter, defaultdict

from service.attendance.calculation import AttendanceCounts, calculate_attendance


def consolidate_monthly_attendance(days, person_id, artifact, as_of):
    months = defaultdict(Counter)
    last_days = {}
    for day, status in days.items():
        period = day.strftime("%Y-%m")
        months[period][status] += 1
        last_days[period] = max(last_days.get(period, day), day)
    rows = []
    for period, counts in sorted(months.items()):
        attendance = AttendanceCounts(
            sum(counts.values()), counts["present"], counts["excused_absence"],
            counts["unexcused_absence"], counts["unknown"],
        )
        percentage = calculate_attendance(attendance, coverage_complete=True)
        rows.append({
            "recordKey": f"{person_id}:camara:plenary_days:{period}",
            "personId": str(person_id), "institution": "camara",
            "period": period, "basis": "plenary_days",
            "required": attendance.required, "present": attendance.present,
            "excusedAbsences": attendance.excused_absences,
            "unexcusedAbsences": attendance.unexcused_absences,
            "unknown": attendance.unknown,
            "percentage": str(percentage) if percentage is not None else None,
            "partial": period == as_of.strftime("%Y-%m"),
            "observedThrough": last_days[period].isoformat(),
            "sourceUrl": artifact.resource.url, "evidenceSha256": artifact.sha256,
            "sourceObservedAt": artifact.fetched_at,
        })
    return rows
