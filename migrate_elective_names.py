"""One-off migration: strip 'Elective - ' prefix from elective rotation names.

The is_elective flag already tracks elective status, so the prefix is redundant.
"Elective - HPB" becomes "HPB", "Elective - MIS" becomes "MIS", etc.
Plain "Elective" (no sub-type) is left as-is.

Delete this script after running.
"""

import sqlite3
import sys

DB_PATH = "resident_schedule.db"


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        "SELECT id, rotation FROM schedule "
        "WHERE is_elective = 1 AND rotation LIKE 'Elective -%'"
    )
    rows = cur.fetchall()

    updated = 0
    for sid, rotation in rows:
        # Strip "Elective - ", "Elective- ", "Elective -", etc.
        new_name = rotation.split("-", 1)[1].strip()
        cur.execute("UPDATE schedule SET rotation = ? WHERE id = ?", (new_name, sid))
        print(f"  {rotation!r} -> {new_name!r}")
        updated += 1

    conn.commit()
    conn.close()
    print(f"\nDone. Updated {updated} rotation entries in {db_path}.")


if __name__ == "__main__":
    main()
