"""One-off migration: add is_prelim/is_name columns and clean up generic names.

Adds the new columns to the existing resident table, sets flags based on
name patterns, and strips numbering from generic placeholder names.

Safe to run multiple times — checks if columns exist before adding them.
Delete this script after running.
"""

import re
import sqlite3
import sys

DB_PATH = "resident_schedule.db"

# Generic name patterns (before number stripping)
GENERIC_PATTERNS = [
    r"^Plastics(\s+\d+)?$",
    r"^Prelim(\s+\d+)?$",
    r"^Urology(\s+\d+)?$",
    r"^Vascular(\s+\d+)?$",
    r"^CT(\s+\d+)?$",
    r"^Ortho(pedics)?(\s+\d+)?$",
    r"^ENT(\s+\d+)?$",
    r"^Neurosurgery(\s+\d+)?$",
    r"^Anesthesia(\s+\d+)?$",
    r"^Podiatry(\s+\d+)?$",
]


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Check existing columns
    cur.execute("PRAGMA table_info(resident)")
    columns = {row[1] for row in cur.fetchall()}

    if "is_prelim" not in columns:
        cur.execute("ALTER TABLE resident ADD COLUMN is_prelim INTEGER DEFAULT 0")
        print("Added is_prelim column")

    if "is_name" not in columns:
        cur.execute("ALTER TABLE resident ADD COLUMN is_name INTEGER DEFAULT 1")
        print("Added is_name column")

    # Fetch all residents
    cur.execute("SELECT id, name FROM resident")
    residents = cur.fetchall()

    updated = 0
    for rid, name in residents:
        is_generic = any(re.match(p, name, re.IGNORECASE) for p in GENERIC_PATTERNS)
        if not is_generic:
            continue

        # Strip trailing number from generic names
        clean_name = re.sub(r"\s+\d+$", "", name)
        is_prelim = 1 if clean_name.lower() == "prelim" else 0

        cur.execute(
            "UPDATE resident SET name = ?, is_name = 0, is_prelim = ? WHERE id = ?",
            (clean_name, is_prelim, rid),
        )
        updated += 1
        print(f"  {name!r} -> {clean_name!r} (is_name=0, is_prelim={is_prelim})")

    conn.commit()
    conn.close()
    print(f"\nDone. Updated {updated} residents in {db_path}.")


if __name__ == "__main__":
    main()
