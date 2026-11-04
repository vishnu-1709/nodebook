"""iCalendar export for reminders (SPEC §5.10 v0.2). Hand-written RFC 5545, no dependency."""

from __future__ import annotations

from datetime import timedelta, timezone

from backend.core.clock import now
from backend.core.reminders import due
from backend.core.schemas import Reminder


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    out, cur = [], line
    while len(cur.encode()) > 75:
        cut = 75
        while len(cur[:cut].encode()) > 75:
            cut -= 1
        out.append(cur[:cut])
        cur = " " + cur[cut:]
    out.append(cur)
    return "\r\n".join(out)


def _dt(d) -> str:  # noqa: ANN001
    return d.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def reminders_ics(items: list[Reminder]) -> str:
    stamp = _dt(now())
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Nodebook//Reminders//EN", "CALSCALE:GREGORIAN"]
    for r in items:
        start = due(r)
        summary = r.text + (f" #{' #'.join(r.tags)}" if r.tags else "")
        lines += [
            "BEGIN:VEVENT",
            f"UID:{r.id}@nodebook.local",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{_dt(start)}",
            f"DTEND:{_dt(start + timedelta(hours=1))}",
            f"SUMMARY:{_esc(summary)}",
            *([f"CATEGORIES:{_esc(','.join(r.tags))}"] if r.tags else []),
            "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_esc(r.text)}", "TRIGGER:-PT1H", "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(ln) for ln in lines) + "\r\n"
