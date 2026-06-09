"""Import the final approved vacation list into the SQLite vacation table.

Source of truth: approved_vacations_26-27.tsv (transcribed from the program
coordinator's approval email). The committed resident_schedule.db is the deploy
artifact, so this script repopulates the `vacation` table directly rather than
going through the Excel "Weeks"-grid parser in parse_with_logic.py.

Behaviour:
  * Matches each row's resident name to a row in the `resident` table
    (explicit corrections first, then exact, then a high-cutoff fuzzy match
    that is always reported for review).
  * Parses the messy date formats (2-/4-digit years, en-dashes, single days,
    year-less ranges inferred from the academic calendar).
  * Rows without an APPROVED status, with TBD dates, or that fail to match are
    skipped and reported -- never silently dropped.
  * --dry-run prints the full plan and writes nothing. Without it, the existing
    vacation rows are replaced (after a timestamped .db backup).

Usage:
    python import_approved_vacations.py --dry-run
    python import_approved_vacations.py --commit
"""

import argparse
import csv
import difflib
import shutil
import sys
from datetime import date

import pysqlite3  # sqlite shim, matches app/database.py and check_vacation_requests.py

sys.modules["sqlite3"] = pysqlite3
import sqlite3  # noqa: E402

TSV_PATH = "approved_vacations_26-27.tsv"
DB_PATH = "resident_schedule.db"

# Academic year runs July 2026 -> June 2027. Used to infer missing years.
AY_START_YEAR = 2026
AY_END_YEAR = 2027

# Paste spelling -> exact `resident.name` in the DB. Verified against the roster.
NAME_CORRECTIONS = {
    "Diamantis Tsillimigras": "Diamantis Tsilimigras",
    "Dottie Stearns": "Dottie Sterns",
    "Aymen Bahhur": "Aymin Bahhur",
    "Raman Sing": "Raman Singh",
    "Christine (Tina) Kinstedt": "Christine Kinstedt",
    # Plastics residents are stored by last name only in the DB.
    "Michael Edgar": "Edgar",
    "Anam Furrukh": "Furrukh",
    "Mohammed Shaheen": "Shaheen",
    "Jorge Flores-Garcia": "Flores Garcia",
    "George Durisek": "Durisek",
}

# Raw date string -> corrected date string, for obvious typos in the source.
# Surina Patel's Burn week reads "1/25/26-1/29/27"; the 5-day end is 1/29/27, so
# the start is 1/25/27 (a "26" typo). Without this it spans a full year.
DATE_CORRECTIONS = {
    "1/25/26-1/29/27": "1/25/27-1/29/27",
}

# Notes containing any of these (case-insensitive) are tagged vac_type=conference.
CONFERENCE_TOKENS = ("conference", "training")


def four_digit_year(token):
    """'26' -> 2026, '2027' -> 2027, '' / None -> None."""
    if token is None or token == "":
        return None
    y = int(token)
    return y + 2000 if y < 100 else y


def infer_year_from_month(month):
    return AY_START_YEAR if month >= 7 else AY_END_YEAR


def parse_side(token):
    """'8/3/2026' or '8/3' -> (month, day, year_or_None)."""
    parts = token.strip().split("/")
    month = int(parts[0])
    day = int(parts[1])
    year = four_digit_year(parts[2]) if len(parts) > 2 else None
    return month, day, year


def parse_dates(raw):
    """Return (start_iso, end_iso) or None if undatable (e.g. TBD)."""
    s = DATE_CORRECTIONS.get(raw.strip(), raw.strip())
    s = s.replace("–", "-").replace("—", "-")  # en/em dash -> hyphen
    if s.upper() == "TBD" or not s:
        return None

    sides = [p.strip() for p in s.split("-") if p.strip()]
    if len(sides) == 1:
        sm, sd, sy = parse_side(sides[0])
        em, ed, ey = sm, sd, sy
    else:
        sm, sd, sy = parse_side(sides[0])
        em, ed, ey = parse_side(sides[1])

    # Fill missing years: borrow from the other side, else infer from month.
    if sy is None and ey is not None:
        sy = ey
    if ey is None and sy is not None:
        ey = sy
    if sy is None:
        sy = infer_year_from_month(sm)
    if ey is None:
        ey = infer_year_from_month(em)

    start = date(sy, sm, sd)
    end = date(ey, em, ed)
    return start.isoformat(), end.isoformat()


def load_roster(conn):
    rows = conn.execute("SELECT id, name, program FROM resident").fetchall()
    by_lower = {name.lower(): (rid, name) for rid, name, _ in rows}
    names = [name for _, name, _ in rows]
    return rows, by_lower, names


def match_resident(raw_name, by_lower, names):
    """Return (resident_id, matched_name, how) or (None, None, 'unmatched')."""
    corrected = NAME_CORRECTIONS.get(raw_name.strip(), raw_name.strip())
    key = corrected.lower()
    if key in by_lower:
        rid, name = by_lower[key]
        how = "exact" if corrected == raw_name.strip() else "corrected"
        return rid, name, how
    close = difflib.get_close_matches(corrected, names, n=1, cutoff=0.85)
    if close:
        rid, name = by_lower[close[0].lower()]
        return rid, name, "fuzzy"
    return None, None, "unmatched"


def vac_type_for(notes):
    low = notes.lower()
    return "conference" if any(t in low for t in CONFERENCE_TOKENS) else "vacation"


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="parse and report only")
    g.add_argument("--commit", action="store_true", help="replace vacation rows")
    ap.add_argument(
        "--include-unapproved",
        action="store_true",
        help="also import rows whose status is not APPROVED",
    )
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    _, by_lower, names = load_roster(conn)

    planned = []  # (resident_id, name, start, end, vac_type, raw_name, dates, notes)
    skipped = []  # (reason, row dict)
    fuzzy = []
    long_spans = []

    with open(TSV_PATH, newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            name = row["name"].strip()
            status = (row.get("status") or "").strip().upper()
            if status != "APPROVED" and not args.include_unapproved:
                skipped.append(("not approved (status=%r)" % status, row))
                continue

            dates = parse_dates(row["dates"])
            if dates is None:
                skipped.append(("undatable dates=%r" % row["dates"], row))
                continue
            start, end = dates

            rid, matched, how = match_resident(name, by_lower, names)
            if rid is None:
                skipped.append(("no resident match", row))
                continue
            if how == "fuzzy":
                fuzzy.append((name, matched, row["program"]))

            span = (date.fromisoformat(end) - date.fromisoformat(start)).days
            if span > 21 or span < 0:
                long_spans.append((name, start, end, span, row["dates"]))

            planned.append(
                (
                    rid,
                    matched,
                    start,
                    end,
                    vac_type_for(row["notes"]),
                    name,
                    row["dates"],
                    row["notes"],
                )
            )

    # ---- report ----
    print("=" * 72)
    print("APPROVED VACATION IMPORT  (%s)" % ("DRY RUN" if args.dry_run else "COMMIT"))
    print("=" * 72)
    print("Planned inserts : %d" % len(planned))
    print("Skipped         : %d" % len(skipped))
    print()

    if fuzzy:
        print("FUZZY NAME MATCHES (review these):")
        for raw, matched, prog in fuzzy:
            print("  %-28s -> %-24s (%s)" % (raw, matched, prog))
        print()

    if long_spans:
        print("LONG / NEGATIVE SPANS (review these):")
        for name, s, e, span, raw in long_spans:
            print("  %-22s %s .. %s  (%d days)  raw=%r" % (name, s, e, span, raw))
        print()

    if skipped:
        print("SKIPPED ROWS:")
        for reason, row in skipped:
            print(
                "  %-22s %-14s %-28s  [%s]"
                % (row["name"], row["dates"], reason, row["notes"])
            )
        print()

    print("PLANNED INSERTS:")
    for rid, matched, start, end, vt, raw, rawdates, notes in planned:
        flag = "" if matched == raw else "  (<- %s)" % raw
        print("  %-24s %s .. %s  %-10s%s" % (matched, start, end, vt, flag))
    print()

    if args.dry_run:
        print("Dry run -- no changes written.")
        return

    # ---- commit ----
    stamp = date.today().isoformat()
    backup = "%s.bak-%s" % (DB_PATH, stamp)
    shutil.copy2(DB_PATH, backup)
    print("Backed up DB -> %s" % backup)

    before = conn.execute("SELECT COUNT(*) FROM vacation").fetchone()[0]
    conn.execute("DELETE FROM vacation")
    conn.executemany(
        "INSERT INTO vacation (resident_id, vac_start, vac_end, vac_type) "
        "VALUES (?, ?, ?, ?)",
        [(rid, s, e, vt) for rid, _, s, e, vt, _, _, _ in planned],
    )
    conn.commit()
    after = conn.execute("SELECT COUNT(*) FROM vacation").fetchone()[0]
    print("vacation rows: %d -> %d" % (before, after))
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
