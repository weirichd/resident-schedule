"""Check the proposed vacations in 'Vacation Requests 26-27.xlsx' against the
validity rules in app/vacation_checker.py.

Read-only with respect to the database: it loads the populated schedule to run
the rules but never writes vacation rows. Produces a markdown report grouped by
request status (Pending / Approved / Denied), failures highlighted.
"""

import re
import sys
import difflib
from datetime import date

import pandas as pd

import pysqlite3  # noqa: E402  (sqlite shim, matches app/database.py)

sys.modules["sqlite3"] = pysqlite3
import sqlite3  # noqa: E402

from app.vacation_checker import (  # noqa: E402
    check_vacation,
    get_academic_year_bounds,
)

REQUESTS_FILE = "Vacation Requests 26-27.xlsx"
DB_PATH = "resident_schedule.db"
REPORT_PATH = "qa/vacation_request_check.md"

SKIP_NAME_TOKENS = (
    "name of resident",
    "resident",
    "seniors",
    "interns",
    "other institusions",
    "other institutions",
    "other programs",
    "other time off",
    "general surgery",
)


def norm(n: str) -> str:
    return re.sub(r"[^a-z]", "", n.lower())


def parse_dates(raw) -> tuple[date, date] | None:
    """Parse a 'Dates Requested' cell into (start, end).

    Years are assigned from the month using the academic-year rule (month >= 7
    -> 2026, else 2027), which normalizes away the file's inconsistent and
    sometimes truncated/typo'd year values. All requests fall in AY 2026-2027.
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    if isinstance(raw, (pd.Timestamp,)):
        d = raw.date()
        return (d, d)
    s = str(raw).strip()
    if not s:
        return None
    pairs = re.findall(r"(\d{1,2})/(\d{1,2})", s)
    if not pairs:
        return None

    def to_date(mo: int, da: int) -> date | None:
        year = 2026 if mo >= 7 else 2027
        try:
            return date(year, mo, da)
        except ValueError:
            return None

    start = to_date(int(pairs[0][0]), int(pairs[0][1]))
    end = to_date(int(pairs[-1][0]), int(pairs[-1][1]))
    if start is None or end is None:
        return None
    return (start, end)


def load_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    residents = [dict(r) for r in con.execute("SELECT * FROM resident").fetchall()]
    schedules = [dict(r) for r in con.execute("SELECT * FROM schedule").fetchall()]
    vacations = [dict(r) for r in con.execute("SELECT * FROM vacation").fetchall()]
    con.close()
    by_id = {r["id"]: r for r in residents}
    # name lookups
    norm_map: dict[str, int] = {}
    for r in residents:
        norm_map.setdefault(norm(r["name"]), r["id"])
    return residents, schedules, vacations, by_id, norm_map


def match_resident(name: str, residents, norm_map):
    key = norm(name)
    if key in norm_map:
        return norm_map[key], "exact"
    # fuzzy on full normalized name
    candidates = {norm(r["name"]): r["id"] for r in residents}
    close = difflib.get_close_matches(key, list(candidates), n=1, cutoff=0.82)
    if close:
        return candidates[close[0]], f"fuzzy~{close[0]}"
    # last-token fallback (handles 'Jorge Flores-Garcia' -> 'Flores Garcia')
    req_tokens = re.findall(r"[a-z]+", name.lower())
    if req_tokens:
        last = req_tokens[-1]
        for r in residents:
            r_tokens = re.findall(r"[a-z]+", r["name"].lower())
            if last in r_tokens and len(last) > 3:
                return r["id"], f"last-name~{r['name']}"
    return None, None


def run_check(rid, req_start, req_end, by_id, schedules, vacations):
    r = by_id[rid]
    resident = {
        "id": r["id"],
        "name": r["name"],
        "pgy": r["pgy"],
        "program": r["program"],
        "is_visiting": bool(r["is_visiting"]),
        "is_prelim": bool(r["is_prelim"]),
    }
    ay_start, ay_end = get_academic_year_bounds(req_start)

    def d(s):
        return date.fromisoformat(s)

    resident_schedule = [
        {
            "resident_id": s["resident_id"],
            "rotation": s["rotation"],
            "start_date": d(s["start_date"]),
            "end_date": d(s["end_date"]),
        }
        for s in schedules
        if s["resident_id"] == rid
        and d(s["end_date"]) >= ay_start
        and d(s["start_date"]) <= ay_end
    ]
    resident_vacations = [
        {
            "vac_start": d(v["vac_start"]),
            "vac_end": d(v["vac_end"]),
            "vac_type": v["vac_type"],
        }
        for v in vacations
        if v["resident_id"] == rid
        and d(v["vac_end"]) >= ay_start
        and d(v["vac_start"]) <= ay_end
    ]
    all_schedules = [
        {
            "resident_id": s["resident_id"],
            "resident_name": by_id[s["resident_id"]]["name"],
            "rotation": s["rotation"],
            "start_date": d(s["start_date"]),
            "end_date": d(s["end_date"]),
        }
        for s in schedules
        if d(s["end_date"]) >= req_start and d(s["start_date"]) <= req_end
    ]
    all_vacations = [
        {
            "resident_id": v["resident_id"],
            "resident_name": by_id[v["resident_id"]]["name"],
            "vac_start": d(v["vac_start"]),
            "vac_end": d(v["vac_end"]),
            "vac_type": v["vac_type"],
        }
        for v in vacations
        if d(v["vac_end"]) >= req_start and d(v["vac_start"]) <= req_end
    ]
    return check_vacation(
        resident=resident,
        req_start=req_start,
        req_end=req_end,
        resident_schedule=resident_schedule,
        resident_vacations=resident_vacations,
        all_schedules=all_schedules,
        all_vacations=all_vacations,
    )


def main():
    residents, schedules, vacations, by_id, norm_map = load_db()
    df = pd.read_excel(REQUESTS_FILE, sheet_name="VACATION REQUESTS", header=None)
    rows = df.values.tolist()

    def cell(r, i):
        if i >= len(r):
            return ""
        v = r[i]
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return ""
        return v if isinstance(v, pd.Timestamp) else str(v).strip()

    results = []  # (status, name, match_note, start, end, result_or_error)
    for r in rows:
        name = cell(r, 0)
        if not isinstance(name, str) or not name:
            continue
        low = name.lower()
        if any(tok in low for tok in SKIP_NAME_TOKENS):
            continue
        dates_raw = r[3] if len(r) > 3 else None
        status = (cell(r, 6) or "Pending") or "Pending"
        if isinstance(status, str) and status.strip().lower() in ("status", ""):
            status = "Pending"

        parsed = parse_dates(dates_raw)
        if parsed is None:
            results.append((status, name, None, None, None, "UNPARSEABLE DATES"))
            continue
        start, end = parsed
        rid, note = match_resident(name, residents, norm_map)
        if rid is None:
            results.append((status, name, None, start, end, "RESIDENT NOT FOUND"))
            continue
        res = run_check(rid, start, end, by_id, schedules, vacations)
        results.append((status, name, note, start, end, res))

    write_report(results, by_id)


def fmt_status(s: str) -> str:
    s = (s or "Pending").strip()
    u = s.upper()
    if "APPROV" in u:
        return "Approved"
    if "DENIED" in u or "DENY" in u:
        return "Denied"
    return "Pending"


def write_report(results, by_id):
    groups: dict[str, list] = {"Pending": [], "Approved": [], "Denied": []}
    for item in results:
        groups[fmt_status(item[0])].append(item)

    lines = ["# Vacation Request Validity Check", ""]
    lines.append(f"Run against `resident_schedule.db` on {date.today().isoformat()}.")
    lines.append("Requests are **not** written to the database — rules only.")
    lines.append("")

    total = len(results)
    n_fail = sum(
        1
        for _, _, _, _, _, res in results
        if hasattr(res, "all_passed") and not res.all_passed
    )
    n_err = sum(1 for *_, res in results if isinstance(res, str))
    n_exempt = sum(1 for *_, res in results if hasattr(res, "exempt") and res.exempt)
    lines.append(
        f"**{total} requests** — {n_fail} fail one or more rules, "
        f"{n_exempt} exempt, {n_err} could not be evaluated."
    )
    lines.append("")

    for status in ("Pending", "Approved", "Denied"):
        items = groups[status]
        if not items:
            continue
        lines.append(f"## {status} ({len(items)})")
        lines.append("")
        for _, name, note, start, end, res in items:
            rng = f"{start} → {end}" if start else "?"
            if isinstance(res, str):
                lines.append(f"- ❓ **{name}** {rng} — _{res}_")
                continue
            tag = "🟢 PASS" if res.all_passed else "🔴 FAIL"
            if res.exempt:
                tag = "⚪ EXEMPT"
            note_s = f" _(matched {note})_" if note and note != "exact" else ""
            lines.append(f"- {tag} **{name}** {rng}{note_s}")
            if res.exempt:
                lines.append(f"    - {res.exempt_reason}")
            elif not res.all_passed:
                for rr in res.results:
                    if not rr.passed:
                        lines.append(f"    - ❌ {rr.display_name}: {rr.message}")
                        for det in rr.details[:6]:
                            lines.append(f"        - {det}")
        lines.append("")

    report = "\n".join(lines)
    with open(REPORT_PATH, "w") as f:
        f.write(report)

    # Console summary
    print(report)
    print(f"\nWrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
