"""Generic, roster-independent parser for the FINAL SCHEUDLE sheet.

Replaces parse_with_logic.py's hardcoded anchor-based section walker (which
broke when the roster changed) with structural detection:

  * A "date row" is any row whose block columns (col 3+) hold M/D-M/D ranges.
    It defines the block schedule for the residents that follow it.
  * Resident rows follow a date row until the next date row. Header,
    block-label, call-pool, and blank rows in between are skipped naturally
    (no parseable PGY).

All cell-level parsing (multi-line dated segments, Monday splits, electives,
FLOAT, VACATION blocks, home-program skips, rotation validation) is reused
verbatim from parse_with_logic.
"""

import json
import re

import pandas as pd

import parse_with_logic as P

DATE_RE = re.compile(r"^\s*\d{1,2}/\d{1,2}\s*-\s*\d{1,2}/\d{1,2}\s*$")

# External-hospital sections: General Surgery residents visiting OSU for
# specific rotations (sparse rows). Distinct from off-service OSU rotators
# (Anesthesia/Urology/etc.), who keep their own program and are not "visiting".
VISITING_INSTITUTIONS = {
    "Doctors": "Doctors Hospital",
    "Riverside": "Riverside Methodist",
    "Mount Carmel": "Mount Carmel",
    "Parkview": "Parkview",
    "Kettering": "Kettering",
}

SKIP_NAMES = {
    "Call pool",
    "switch day",
    "Main call pool",
    "Chief Call pool",
    "East Call Pool",
    "Intern compliments",
    "INTERN COMPLIMENTS",
    "TOTAL",
    "Night Float",
    "Vascular",
    "Colorectal",
    "Zollinger-Ellison",
    "Thoracic",
    "Transplant",
    "Burn",
    "SONC",
    "Peds",
    "ACS",
    "East",
    "SICU",
}


# Corrections for known source-data errors, keyed by (resident_name,
# block_number). The text replaces the raw cell before parsing. Michelle
# Garrison's block 11 (4/5-5/2) was entered with May dates belonging to
# block 12; corrected per program direction.
CELL_OVERRIDES = {
    ("Michelle Garrison", 11): "Vacation 4/5-4/18\nJeopardy 4/19-5/2",
}


def _s(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def _map_program(prog_str: str) -> str:
    if "Vascular" in prog_str:
        return "Vascular Surgery"
    if "CT" in prog_str or "Cardiothoracic" in prog_str:
        return "Cardiothoracic Surgery"
    if "Plastic" in prog_str:
        return "Plastic Surgery"
    if "Urology" in prog_str:
        return "Urology"
    if "Ortho" in prog_str:
        return "Orthopedics"
    if "OMFS" in prog_str:
        return "Oral and Maxillofacial Surgery"
    if "Dental" in prog_str:
        return "Dental Anesthesia"
    if "Anesthesia" in prog_str:
        return "Anesthesia"
    if "Family Medicine" in prog_str:
        return "Family Medicine"
    if "Podiatry" in prog_str:
        return "Podiatry"
    if "ENT" in prog_str:
        return "ENT"
    if "Neuro" in prog_str:
        return "Neurosurgery"
    if "EM" in prog_str or "Emergency" in prog_str:
        return "Emergency Medicine"
    return "General Surgery"


def _block_headers(row: list) -> list[tuple]:
    """Collect consecutive M/D-M/D ranges from col 3 onward."""
    headers = []
    for cell in row[3:]:
        text = _s(cell)
        if not DATE_RE.match(text):
            break
        headers.append(P.parse_block_header(text, P.ACADEMIC_YEAR_START))
    return headers


def _is_date_row(row: list) -> bool:
    return len(row) > 3 and bool(DATE_RE.match(_s(row[3])))


def parse_resident_row(row: list, block_headers: list[tuple]):
    name = _s(row[2]) if len(row) > 2 else ""
    if not name or "TBD" in name.upper() or name in SKIP_NAMES:
        return
    pgy_str = _s(row[1]) if len(row) > 1 else ""
    try:
        pgy = int(float(pgy_str))
    except (ValueError, TypeError):
        return
    if pgy < 1 or pgy > 5:
        return

    prog_str = _s(row[0]) if len(row) > 0 else ""
    is_prelim = "prelim" in prog_str.lower()
    is_visiting = prog_str in VISITING_INSTITUTIONS
    visiting_institution = VISITING_INSTITUTIONS.get(prog_str)
    if is_prelim or is_visiting:
        program = "General Surgery"
    else:
        program = _map_program(prog_str)

    idx = P.add_resident(
        name=name,
        pgy=pgy,
        program=program,
        is_visiting=is_visiting,
        visiting_institution=visiting_institution,
        is_prelim=is_prelim,
    )

    for i, (b_start, b_end) in enumerate(block_headers):
        override = CELL_OVERRIDES.get((name, i + 1))
        if override is not None:
            P.parse_cell(override, b_start, b_end, idx, pgy)
            continue
        col = 3 + i
        if col >= len(row):
            break
        cell = row[col]
        if pd.isna(cell):
            continue
        P.parse_cell(str(cell), b_start, b_end, idx, pgy)


def parse_main_schedule():
    df = pd.read_excel(P.ROTATION_SCHEDULE, sheet_name="FINAL SCHEUDLE", header=None)
    rows = df.values.tolist()

    current_headers: list[tuple] = []
    for row in rows:
        if _is_date_row(row):
            current_headers = _block_headers(row)
            # A date row may itself be the Program/PGY/Name header; its own
            # name cell ("Name") has no parseable PGY, so feeding it through
            # parse_resident_row is harmless.
            parse_resident_row(row, current_headers)
            continue
        if current_headers:
            parse_resident_row(row, current_headers)


def main():
    parse_main_schedule()
    data = {
        "residents": P.residents,
        "rotations": P.rotations,
        "vacations": P.vacations,
    }
    with open("/tmp/parsed_generic.json", "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(
        f"residents={len(P.residents)} "
        f"rotations={len(P.rotations)} vacations={len(P.vacations)}"
    )
    if P._unknown_rotations:
        print(f"\nUnknown non-elective rotations ({len(P._unknown_rotations)}):")
        for r in sorted(P._unknown_rotations):
            print(f"  - {r!r}")
    print("\nWrote /tmp/parsed_generic.json")


if __name__ == "__main__":
    main()
