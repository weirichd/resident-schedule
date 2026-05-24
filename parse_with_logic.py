"""One-shot parser for Rotation Schedule 2026-2027.

Reads the Excel file and the vacation requests file, applies all the
schedule parsing rules, and writes the result to SQLite.
"""

import json
import re
from datetime import date, timedelta

import pandas as pd

ACADEMIC_YEAR_START = 2026  # July 2026
NEXT_YEAR = 2027

ROTATION_SCHEDULE = "Rotation Schedule 2026-2027.xlsx"
VACATION_FILE = "Vacation Requests 26-27.xlsx"
ANESTHESIA_VACATION_FILE = "General Surgery Vacations.xlsx"
DB_PATH = "resident_schedule.db"


# Correct misspellings that appear in source files
NAME_CORRECTIONS = {
    "Desphande": "Deshpande",
}


# Map raw cell text to canonical rotation names
ROTATION_MAP = {
    "ACS": "Acute Care Surgery",
    "EGS": "Acute Care Surgery",
    "HPB": "Hepatobiliary Surgery",
    "Hepatobiliary": "Hepatobiliary Surgery",
    "ZE": "Zollinger Ellison",
    "Zollinger-Ellison": "Zollinger Ellison",
    "Mel-Sarc": "Melanoma and Sarcoma",
    "Melanoma-Sarcoma": "Melanoma and Sarcoma",
    "Mel/Sarc": "Melanoma and Sarcoma",
    "Breast-Endocrine": "Breast and Endocrine",
    "Breast/Endo": "Breast and Endocrine",
    "Colorectal": "Colorectal Surgery",
    "CRS": "Colorectal Surgery",
    "Pediatric Surgery": "Pediatric Surgery",
    "Peds": "Pediatric Surgery",
    "Ped Surg": "Pediatric Surgery",
    "SICU": "Surgical ICU",
    "Outpatient SONC": "Outpatient Surgical Oncology",
    "SONC": "Outpatient Surgical Oncology",
    "Vacation": "VACATION",
    "VACATION": "VACATION",
    "VACATIO": "VACATION",
    "Vacatio": "VACATION",
    "OFF": "VACATION",
    "Trauma": "Trauma",
    "Traums": "Trauma",
    "Burn": "Burn",
    "Endoscopy": "Endoscopy",
    "Thoracic": "Thoracic",
    "Vascular": "Vascular",
    "Vascular UH": "Vascular",
    "Vascular - UH": "Vascular",
    "East Vascular": "Vascular East",
    "Vascular East": "Vascular East",
    "Mount Carmel East": "Mount Carmel East",
    "Transplant": "Transplant",
    "Outpatient": "Outpatient",
    "Night Float": "Night Float",
    "Jeopardy": "Jeopardy",
    "JEOPARDY": "Jeopardy",
    "Breast": "Breast",
    "East": "East General Surgery",
    "East - General": "East General Surgery",
    "East General Surgery": "East General Surgery",
    "Elective": "Elective",
    "Ob": "OB",
}


# Canonical non-elective rotation names (from parse_schedule.py SYSTEM_PROMPT).
# Elective rotations may use any sub-type name.
VALID_ROTATIONS = {
    "Acute Care Surgery",
    "Breast",
    "Breast and Endocrine",
    "Burn",
    "Colorectal Surgery",
    "East General Surgery",
    "Elective",
    "Endoscopy",
    "Hepatobiliary Surgery",
    "Jeopardy",
    "Melanoma and Sarcoma",
    "Mount Carmel East",
    "Night Float",
    "Outpatient",
    "Outpatient Surgical Oncology",
    "Pediatric Surgery",
    "Surgical ICU",
    "Thoracic",
    "Transplant",
    "Trauma",
    "Vascular",
    "Vascular East",
    "Zollinger Ellison",
}


def map_rotation(raw: str) -> tuple[str, str | None, bool]:
    """Map a raw rotation string to (canonical_name, location, is_elective).

    Returns location='East' if the rotation is at East campus.
    """
    raw = raw.strip()
    location = None
    is_elective = False

    # Strip elective markers
    elective_match = re.match(r"(?i)^(?:Elective\s*[-:\(]?\s*|Elect\s+)(.+?)\)?$", raw)
    if elective_match:
        is_elective = True
        raw = elective_match.group(1).strip()
    elif re.search(r"(?i)\s*[-:]\s*Elective\s*$", raw):
        is_elective = True
        raw = re.sub(r"(?i)\s*[-:]\s*Elective\s*$", "", raw).strip()
    elif raw.endswith("?"):
        is_elective = True
        raw = raw[:-1].strip()

    # East campus markers
    if raw.startswith("East - ACS") or raw == "East - ACS":
        return "Acute Care Surgery", "East", is_elective
    if raw.startswith("East - General") or raw == "East - General":
        return "East General Surgery", None, is_elective
    if raw == "East" or raw == "East ":
        return "East General Surgery", None, is_elective

    # Direct map
    if raw in ROTATION_MAP:
        canonical = ROTATION_MAP[raw]
        if canonical == "Vascular East":
            location = "East"
        return canonical, location, is_elective

    # Case-insensitive fallback
    for key, value in ROTATION_MAP.items():
        if raw.lower() == key.lower():
            return value, location, is_elective

    # Unknown — return as-is
    return raw, location, is_elective


def parse_block_date(start: str, end: str, year_start: int) -> tuple[date, date]:
    """Parse 'M/D' style dates into (start_date, end_date) for the academic year."""

    def md_to_date(md: str, prev_month: int | None = None) -> date:
        import calendar as _cal

        m, d = md.split("/")
        m, d = int(m), int(d)
        # Months 7-12 are in the start year; months 1-6 are in the next year
        year = year_start if m >= 7 else year_start + 1
        # Fix invalid days (e.g., 2/29 in non-leap year): shift to next month
        last_day = _cal.monthrange(year, m)[1]
        if d > last_day:
            # Shift to first of next month
            if m == 12:
                m, d, year = 1, 1, year + 1
            else:
                m, d = m + 1, 1
        return date(year, m, d)

    return md_to_date(start), md_to_date(end)


def parse_block_header(header: str, year_start: int) -> tuple[date, date]:
    """Parse 'M/D-M/D' header like '7/1-8/30' into a date range.

    Handles obvious typos like '5/3-3/30' → '5/3-5/30'.
    """
    header = header.strip()
    match = re.match(r"^(\d{1,2}/\d{1,2})-(\d{1,2}/\d{1,2})$", header)
    if not match:
        raise ValueError(f"Cannot parse block header: {header!r}")

    start_str, end_str = match.group(1), match.group(2)
    start_date, end_date = parse_block_date(start_str, end_str, year_start)

    # Fix obvious typos: end date is before start date
    if end_date < start_date:
        # Try same month for end, e.g., "5/3-3/30" → "5/3-5/30"
        sm = int(start_str.split("/")[0])
        ed = int(end_str.split("/")[1])
        em = sm
        year = year_start if em >= 7 else year_start + 1
        end_date = date(year, em, ed)

    return start_date, end_date


MONTHLY_HEADERS = {
    "7/1-7/31": (7, "monthly"),
    "8/1-8/31": (8, "monthly"),
    "9/1-9/30": (9, "monthly"),
    "10/1-10/31": (10, "monthly"),
    "11/1-11/30": (11, "monthly"),
    "12/1-12/31": (12, "monthly"),
    "1/1-1/31": (1, "monthly"),
    "2/1-2/28": (2, "monthly"),
    "3/1-3/31": (3, "monthly"),
    "4/1-4/30": (4, "monthly"),
    "5/1-5/31": (5, "monthly"),
    "6/1-6/30": (6, "monthly"),
}


def first_monday_on_or_after(d: date) -> date:
    days_ahead = (0 - d.weekday()) % 7
    return d + timedelta(days=days_ahead)


def split_block_monday(
    block_start: date, block_end: date
) -> tuple[date, date, date, date]:
    """Pick a Monday split closest to the block midpoint (favoring first half).

    Returns (first_start, first_end, second_start, second_end).
    """
    total_days = (block_end - block_start).days + 1
    midpoint = block_start + timedelta(days=total_days // 2)

    # Find the Monday closest to midpoint
    candidates = []
    d = block_start
    while d <= block_end:
        if d.weekday() == 0:  # Monday
            candidates.append(d)
        d += timedelta(days=1)

    if not candidates:
        # Fallback: split at midpoint
        split = midpoint
    else:
        split = min(candidates, key=lambda x: abs((x - midpoint).days))

    return (
        block_start,
        split - timedelta(days=1),
        split,
        block_end,
    )


# ---------- Data containers ----------

residents = []
rotations = []
vacations = []
_resident_index = 0


def add_resident(
    name: str,
    pgy: int,
    program: str = "General Surgery",
    is_visiting: bool = False,
    visiting_institution: str | None = None,
    is_prelim: bool = False,
    is_name: bool = True,
) -> int:
    """Add a resident and return its index."""
    global _resident_index
    name = NAME_CORRECTIONS.get(name, name)
    idx = _resident_index
    residents.append(
        {
            "index": idx,
            "name": name,
            "pgy": pgy,
            "program": program,
            "is_visiting": is_visiting,
            "visiting_institution": visiting_institution,
            "is_prelim": is_prelim,
            "is_name": is_name,
        }
    )
    _resident_index += 1
    return idx


def add_rotation(
    resident_idx: int,
    rotation: str,
    start: date,
    end: date,
    location: str | None = None,
    is_elective: bool = False,
):
    rotations.append(
        {
            "resident_index": resident_idx,
            "rotation": rotation,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "location": location,
            "is_elective": is_elective,
        }
    )


def add_vacation(
    resident_idx: int,
    start: date,
    end: date,
    vac_type: str = "vacation",
):
    vacations.append(
        {
            "resident_index": resident_idx,
            "vac_start": start.isoformat(),
            "vac_end": end.isoformat(),
            "vac_type": vac_type,
        }
    )


# ---------- Cell parsing ----------

# Skip-list — these are home-program rotations or non-rotations.
# Compared case-insensitively against the cell text.
HOME_PROGRAM_NAMES = {
    "plastics",
    "urology",
    "anes",
    "procedure",
    "simulation",
    "research",
    "out",
}


def _is_home_program(text: str) -> bool:
    return text.strip().lower() in HOME_PROGRAM_NAMES


def parse_cell(
    cell: str,
    block_start: date,
    block_end: date,
    resident_idx: int,
    pgy: int,
):
    """Parse a single cell and add rotations/vacations as appropriate."""
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return
    cell = str(cell).strip()
    if not cell:
        return
    if cell.upper() == "TBD":
        return
    if _is_home_program(cell):
        return
    if "TBD" in cell.upper() and "/" not in cell:
        return  # e.g., "Elective - TBD"

    # Multi-line cells with explicit date ranges
    if "\n" in cell:
        lines = [line.strip() for line in cell.split("\n") if line.strip()]
        # If any line has explicit dates, only process dated lines.
        # Header-only lines (like "Elective") still apply their flag.
        has_dated = any(re.search(r"\d+/\d+\s*-\s*\d+/\d+", line) for line in lines)
        if has_dated:
            elective_re = r"(?i)^elective\s*[-:]?\s*$"
            elective_header = any(re.match(elective_re, line.strip()) for line in lines)
            for line in lines:
                stripped = line.strip()
                if re.match(elective_re, stripped):
                    continue  # pure elective marker — only sets the flag
                if re.search(r"\d+/\d+\s*-\s*\d+/\d+", line):
                    _parse_segment_with_flag(
                        line,
                        block_start,
                        block_end,
                        resident_idx,
                        pgy,
                        force_elective=elective_header,
                    )
                else:
                    # Undated rotation line spans the whole block, e.g. the
                    # "Hepatobiliary" in "Hepatobiliary\nVacation 6/24-6/30".
                    _add_other(
                        stripped,
                        block_start,
                        block_end,
                        resident_idx,
                        force_elective=elective_header,
                    )
        else:
            for line in lines:
                _parse_dated_segment(line, block_start, block_end, resident_idx, pgy)
        return

    # Inline date range: "Rotation X/Y-X/Y"
    if re.search(r"\d+/\d+\s*-\s*\d+/\d+", cell):
        _parse_dated_segment(cell, block_start, block_end, resident_idx, pgy)
        return

    # FLOAT with explicit dates: "FLOAT [7/1-7/26]/ACS"
    float_match = re.match(
        r"^(.*)?FLOAT\s*\[([^\]]+)\](.*)$", cell, flags=re.IGNORECASE
    )
    if float_match:
        # Treat as single rotation; override Monday split
        # For simplicity, use the bracketed dates as-is
        before, dates, after = (
            float_match.group(1) or "",
            float_match.group(2),
            float_match.group(3) or "",
        )
        # Parse the date range
        date_match = re.match(r"(\d+/\d+)\s*-\s*(\d+/\d+)", dates)
        if date_match:
            year_start = ACADEMIC_YEAR_START
            float_start, float_end = parse_block_date(
                date_match.group(1), date_match.group(2), year_start
            )
            add_rotation(resident_idx, "Night Float", float_start, float_end)
            # Handle the rest of the cell as separate rotation
            other = (before + after).strip().strip("/").strip()
            if other and other.upper() != "FLOAT":
                # Determine remaining date range
                if float_start > block_start:
                    (
                        add_rotation(
                            resident_idx,
                            *_resolve(other),
                            start=block_start,
                            end=float_start - timedelta(days=1),
                        )
                        if False
                        else _add_other(
                            other,
                            block_start,
                            float_start - timedelta(days=1),
                            resident_idx,
                        )
                    )
                if float_end < block_end:
                    _add_other(
                        other,
                        float_end + timedelta(days=1),
                        block_end,
                        resident_idx,
                    )
            return

    # Split rotations: "ACS/SICU" or "BURN/VACATIO" etc.
    if "/" in cell:
        # Compound exceptions — single rotations, not splits
        if cell.upper() in ("SONC/HPB", "CARDIAC/CVICU"):
            rot, loc, elec = map_rotation(cell)
            add_rotation(resident_idx, rot, block_start, block_end, loc, elec)
            return

        # If the whole cell starts with "Elective" before any split, strip
        # the marker and apply elective to both halves (e.g., "Elective Ob/Gyn"
        # or "Elective - Ob/Gyn").
        whole_cell_elective = False
        cell_for_split = cell
        m = re.match(r"(?i)^Elective\s*[-:]?\s*(.+/.+)$", cell_for_split)
        if m:
            whole_cell_elective = True
            cell_for_split = m.group(1).strip()

        parts = [p.strip() for p in cell_for_split.split("/")]
        if len(parts) == 2:
            f_start, f_end, s_start, s_end = split_block_monday(block_start, block_end)
            for part, start, end in [
                (parts[0], f_start, f_end),
                (parts[1], s_start, s_end),
            ]:
                _add_other(
                    part,
                    start,
                    end,
                    resident_idx,
                    force_elective=whole_cell_elective,
                )
            return

    # Default: single rotation for the whole block
    _add_other(cell, block_start, block_end, resident_idx)


def _resolve(raw: str) -> tuple[str, str | None, bool]:
    return map_rotation(raw)


_unknown_rotations: set[str] = set()


def _add_other(
    raw: str, start: date, end: date, resident_idx: int, force_elective: bool = False
):
    """Add a single rotation or vacation entry."""
    raw = raw.strip()
    if not raw or raw.upper() == "TBD":
        return
    if _is_home_program(raw):
        return
    if "TBD" in raw.upper():
        return

    rot, loc, elec = map_rotation(raw)
    is_elective = elec or force_elective
    if rot == "VACATION":
        add_vacation(resident_idx, start, end)
        return
    # Validate non-elective rotations against the canonical list. Electives
    # are allowed to use any sub-type per rule 10.
    if not is_elective and rot not in VALID_ROTATIONS:
        _unknown_rotations.add(rot)
    add_rotation(resident_idx, rot, start, end, loc, is_elective)


def _parse_dated_segment(
    line: str, block_start: date, block_end: date, resident_idx: int, pgy: int
):
    """Parse a segment like 'ACS 7/27-8/30' into a rotation entry."""
    _parse_segment_with_flag(line, block_start, block_end, resident_idx, pgy)


def _parse_segment_with_flag(
    line: str,
    block_start: date,
    block_end: date,
    resident_idx: int,
    pgy: int,
    force_elective: bool = False,
):
    line = line.strip()
    if not line:
        return
    match = re.match(r"^(.+?)\s+(\d+/\d+)\s*-\s*(\d+/\d+)\s*$", line)
    if not match:
        _add_other(
            line, block_start, block_end, resident_idx, force_elective=force_elective
        )
        return
    rot_text = match.group(1).strip()
    start_str = match.group(2)
    end_str = match.group(3)
    seg_start, seg_end = parse_block_date(start_str, end_str, ACADEMIC_YEAR_START)
    # Typo guard: clamp to block window. If end falls after the block end
    # (e.g., "5/10-9/6" should be "5/10-6/6"), assume it was meant to be
    # within the block and snap to the block end.
    if seg_end > block_end:
        seg_end = block_end
    if seg_start < block_start:
        seg_start = block_start
    if seg_start > seg_end:
        return  # Skip malformed segment
    _add_other(
        rot_text, seg_start, seg_end, resident_idx, force_elective=force_elective
    )


# ---------- Section parsers ----------


def parse_blocked_section(
    df_rows: list[list],
    name_col: int,
    pgy_col: int,
    program_col: int,
    block_headers: list[tuple[date, date]],
    block_col_start: int,
    program_default: str = "General Surgery",
    is_visiting: bool = False,
    visiting_institution: str | None = None,
    pgy_override: int | None = None,
):
    """Parse a section where each row is a resident with one cell per block."""
    for row in df_rows:
        name_cell = row[name_col] if len(row) > name_col else None
        if pd.isna(name_cell) or not str(name_cell).strip():
            continue
        name = str(name_cell).strip()
        if "TBD" in name.upper():
            continue
        if name in (
            "Call pool",
            "switch day",
            "Main call pool",
            "Chief Call pool",
            "INTERN COMPLIMENTS",
            "TOTAL",
            "East Call Pool",
        ):
            continue

        # Get PGY
        pgy = pgy_override
        if pgy is None and len(row) > pgy_col:
            pgy_cell = row[pgy_col]
            if not pd.isna(pgy_cell):
                try:
                    pgy = int(pgy_cell)
                except (ValueError, TypeError):
                    continue
        if pgy is None or pgy < 1 or pgy > 5:
            continue

        # Get program
        program = program_default
        if program_col is not None and len(row) > program_col:
            prog_cell = row[program_col]
            if not pd.isna(prog_cell) and str(prog_cell).strip():
                prog_str = str(prog_cell).strip()
                if "Vascular" in prog_str:
                    program = "Vascular Surgery"
                elif "CT" in prog_str:
                    program = "Cardiothoracic Surgery"
                elif "Plastic" in prog_str:
                    program = "Plastic Surgery"
                elif "Urology" in prog_str:
                    program = "Urology"
                elif "Ortho" in prog_str:
                    program = "Orthopedics"
                elif "OMFS" in prog_str:
                    program = "Oral and Maxillofacial Surgery"
                elif "Anesthesia" in prog_str and "Dental" not in prog_str:
                    program = "Anesthesia"
                elif "Dental" in prog_str:
                    program = "Dental Anesthesia"
                elif "Family Medicine" in prog_str:
                    program = "Family Medicine"
                elif "Podiatry" in prog_str:
                    program = "Podiatry"
                elif "ENT" in prog_str:
                    program = "ENT"
                elif "Neuro" in prog_str:
                    program = "Neurosurgery"
                elif "EM" in prog_str or "Emergency" in prog_str:
                    program = "Emergency Medicine"

        # Detect prelim
        is_prelim = False
        clean_name = name
        if name.lower().startswith("prelim"):
            is_prelim = True
            clean_name = re.sub(
                r"^prelim\s*[-:]?\s*", "", name, flags=re.IGNORECASE
            ).strip()

        # Skip rows where the "name" is just a generic specialty
        is_generic = clean_name.lower() in (
            "plastics",
            "urology",
            "ct",
            "vascular",
            "ortho",
            "anesthesia",
        )

        idx = add_resident(
            name=clean_name,
            pgy=pgy,
            program=program,
            is_visiting=is_visiting,
            visiting_institution=visiting_institution,
            is_prelim=is_prelim,
            is_name=not is_generic,
        )

        # Walk through block cells
        for i, (b_start, b_end) in enumerate(block_headers):
            col = block_col_start + i
            if col >= len(row):
                break
            cell = row[col]
            if pd.isna(cell):
                continue
            parse_cell(str(cell), b_start, b_end, idx, pgy)


# ---------- Main parsing ----------


def find_anchor_row(rows: list[list], name: str) -> int:
    """Find the row index containing a resident with the given name."""
    for i, row in enumerate(rows):
        if len(row) > 2 and not pd.isna(row[2]) and str(row[2]).strip() == name:
            return i
    raise ValueError(f"Anchor not found: {name}")


def parse_section_by_anchor(
    rows: list[list],
    anchor_name: str,
    count: int,
    block_headers,
    block_col_start: int = 3,
    is_visiting: bool = False,
    visiting_institution: str | None = None,
):
    start = find_anchor_row(rows, anchor_name)
    parse_blocked_section(
        rows[start : start + count],
        name_col=2,
        pgy_col=1,
        program_col=0,
        block_headers=block_headers,
        block_col_start=block_col_start,
        is_visiting=is_visiting,
        visiting_institution=visiting_institution,
    )


def parse_main_schedule():
    """Walk through the main 'FINAL SCHEUDLE' sheet section by section."""
    df = pd.read_excel(ROTATION_SCHEDULE, sheet_name="FINAL SCHEUDLE", header=None)
    rows = df.values.tolist()

    # ---- PGY-5 ----
    pgy5_dates = [
        parse_block_header(h, 2026)
        for h in [
            "7/1-8/30",
            "8/31-11/1",
            "11/2-12/27",
            "12/28-2/28",
            "3/1-5/2",
            "5/3-6/30",
        ]
    ]
    parse_section_by_anchor(rows, "Shruthi Srinivas", 6, pgy5_dates)

    # ---- PGY-4 ----
    pgy4_dates = [
        parse_block_header(h, 2026)
        for h in [
            "7/1-8/16",
            "8/17-10/4",
            "10/5-11/15",
            "11/16-1/3",
            "1/4-2/14",
            "2/15-4/4",
            "4/5-5/16",
            "5/17-6/30",
        ]
    ]
    parse_section_by_anchor(rows, "Dan Bacon", 8, pgy4_dates)

    # ---- PGY-3 Gen Surg ----
    pgy3_gs_dates = [
        parse_block_header(h, 2026)
        for h in [
            "7/1-8/23",
            "8/24-10/18",
            "10/19-12/6",
            "12/7-1/31",
            "2/1-3/21",
            "3/22-5/9",
            "5/10-6/30",
        ]
    ]
    parse_section_by_anchor(rows, "Michelle Chan", 7, pgy3_gs_dates)

    # ---- 13-block visiting/Doctors PGY-4/3 (Cristina Rizzo and 8 more) ----
    blocks_13_dates = [
        parse_block_header(h, 2026)
        for h in [
            "7/1-7/26",
            "7/27-8/23",
            "8/24-9/20",
            "9/21-10/18",
            "10/19-11/15",
            "11/16-12/13",
            "12/14-1/10",
            "1/11-2/7",
            "2/8-3/7",
            "3/8-4/4",
            "4/5-5/2",
            "5/3-5/30",
            "5/31-6/30",
        ]
    ]
    parse_section_by_anchor(
        rows,
        "Cristina Rizzo",
        9,
        blocks_13_dates,
        is_visiting=True,
        visiting_institution="Doctors Hospital",
    )

    # ---- PGY-3 misc (Shannon McDonnell, Neelesh Baragoda) ----
    parse_section_by_anchor(rows, "Shannon McDonnell", 2, blocks_13_dates)

    # ---- PGY-2 Gen Surg (10 residents incl. 2 prelim) ----
    parse_section_by_anchor(rows, "Keith Gagnon", 10, blocks_13_dates)

    # ---- PGY-2 Vascular/CT ----
    parse_section_by_anchor(rows, "Drayson Campbell", 2, blocks_13_dates)

    # ---- PGY-2 Plastic Surgery ----
    parse_section_by_anchor(rows, "Eric Min", 4, blocks_13_dates)

    # ---- PGY-2 OMFS ----
    parse_section_by_anchor(rows, "Dana Al-Sayyed", 2, blocks_13_dates)

    # ---- PGY-3 EM/IM ----
    parse_section_by_anchor(rows, "Donna Kayal", 2, blocks_13_dates)

    # ---- Monthly date schema ----
    monthly_dates = []
    months = [
        (7, 2026),
        (8, 2026),
        (9, 2026),
        (10, 2026),
        (11, 2026),
        (12, 2026),
        (1, 2027),
        (2, 2027),
        (3, 2027),
        (4, 2027),
        (5, 2027),
        (6, 2027),
    ]
    import calendar

    for m, y in months:
        first = date(y, m, 1)
        last_day = calendar.monthrange(y, m)[1]
        last = date(y, m, last_day)
        monthly_dates.append((first, last))

    # ---- PGY-2 Anesthesia (21 residents, monthly) ----
    parse_section_by_anchor(rows, "Bar-Meir", 21, monthly_dates)

    # ---- PGY-1 Gen Surg (7 residents) ----
    parse_section_by_anchor(rows, "Yoon-Jung Chang", 7, blocks_13_dates)

    # ---- PGY-1 Prelim Gen Surg (6 residents) ----
    parse_section_by_anchor(rows, "Prelim - Aymin Bahhur", 6, blocks_13_dates)

    # ---- PGY-1 Vascular/CT ----
    parse_section_by_anchor(rows, "Rahul Rodriguez", 2, blocks_13_dates)

    # ---- Doctors PGY-1 ----
    parse_section_by_anchor(
        rows,
        "Jacob Spencer",
        4,
        blocks_13_dates,
        is_visiting=True,
        visiting_institution="Doctors Hospital",
    )

    # ---- Plastic Surgery (James Yoon PGY-4 + 5 PGY-1) ----
    parse_section_by_anchor(rows, "James Yoon", 6, blocks_13_dates)

    # ---- Urology PGY-1 ----
    parse_section_by_anchor(rows, "Grant Sajdak", 4, blocks_13_dates)

    # ---- Family Medicine ----
    parse_section_by_anchor(rows, "Evan Suppa", 9, blocks_13_dates)

    # ---- Anesthesia PGY-1 (monthly, 20 residents) ----
    parse_section_by_anchor(rows, "Becker", 20, monthly_dates)

    # ---- OMFS PGY-1 ----
    parse_section_by_anchor(rows, "Paul Wiley", 2, blocks_13_dates)

    # ---- Orthopedic Surgery PGY-1 ----
    parse_section_by_anchor(rows, "Audria Wood", 6, blocks_13_dates)

    # ---- Podiatry ----
    parse_section_by_anchor(rows, "Joseph Dunnan", 2, blocks_13_dates)

    # ---- ENT ----
    parse_section_by_anchor(rows, "Molly Hunter", 5, blocks_13_dates)

    # ---- Dental Anesthesia (monthly) ----
    parse_section_by_anchor(rows, "Josh Mason", 2, monthly_dates)

    # ---- Neurosurgery (monthly) ----
    parse_section_by_anchor(rows, "Nassim Stegamat", 4, monthly_dates)


# ---------- Vacation file parsing ----------


HOLIDAY_PLACEHOLDERS = {"THANKSGIVING", "CHRISTMAS", "NEW YEARS"}


def find_resident_idx(name_query: str) -> int | None:
    """Find a resident by name match (handles last-name only, full name, typos)."""
    name_query = name_query.strip()
    # Skip holiday placeholders silently
    if name_query.upper() in HOLIDAY_PLACEHOLDERS:
        return None
    # Strip program annotations like "Surina Patel (Urology)" or "Christine (Tina) Kinstedt"
    cleaned = re.sub(r"\s*\([^)]+\)\s*", " ", name_query).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    # Normalize hyphens to spaces (e.g., "Flores-Garcia" → "Flores Garcia")
    cleaned_alt = cleaned.replace("-", " ")
    if not cleaned:
        return None

    parts = cleaned.split()
    last = parts[-1]
    first = parts[0] if len(parts) > 1 else None

    # Exact full-name match (with hyphen normalization)
    for r in residents:
        if r["name"].strip().lower() == cleaned.lower():
            return r["index"]
        if r["name"].strip().replace("-", " ").lower() == cleaned_alt.lower():
            return r["index"]

    # Multi-token compound last name (e.g., "Jorge Flores-Garcia" → "Flores Garcia")
    parts_alt = cleaned_alt.split()
    if len(parts_alt) >= 2:
        compound = " ".join(parts_alt[-2:]).lower()
        for r in residents:
            rname_lower = r["name"].lower().replace("-", " ")
            if compound in rname_lower:
                return r["index"]

    # Exact full-name match
    for r in residents:
        if r["name"].strip().lower() == cleaned.lower():
            return r["index"]

    # Last-name match
    matches = [r for r in residents if r["name"].split()[-1].lower() == last.lower()]
    if len(matches) == 1:
        return matches[0]["index"]

    # First-name match (when only first name given like "Ian", "Michelle", "Paulos")
    if not first:
        matches = [r for r in residents if r["name"].split()[0].lower() == last.lower()]
        if len(matches) == 1:
            return matches[0]["index"]

    # Typo tolerance: Levenshtein-ish matching on last name
    def similar(a: str, b: str) -> bool:
        a, b = a.lower(), b.lower()
        if a == b:
            return True
        # One char insertion/deletion/substitution check
        if abs(len(a) - len(b)) > 2:
            return False
        # Common substring length / max length > threshold
        common = sum(1 for c in a if c in b)
        return common / max(len(a), len(b)) > 0.75

    matches = [r for r in residents if similar(r["name"].split()[-1], last)]
    if len(matches) == 1:
        return matches[0]["index"]

    # Try first-name disambiguation among similar last-name matches
    if first:
        first_matches = [
            r
            for r in matches
            if r["name"].split()[0].lower().startswith(first.lower()[:3])
        ]
        if len(first_matches) == 1:
            return first_matches[0]["index"]

    return None


def _parse_week_dates(label: str) -> tuple[date, date] | None:
    """Parse week labels like 'August 3-9' into (start, end) dates."""
    label = label.strip()
    if not label:
        return None

    # Patterns: "July 1-5", "July 27-Aug 2", "Aug 31 - Sept 6"
    months = {
        "January": 1,
        "Jan": 1,
        "February": 2,
        "Feb": 2,
        "March": 3,
        "Mar": 3,
        "April": 4,
        "Apr": 4,
        "May": 5,
        "June": 6,
        "Jun": 6,
        "July": 7,
        "Jul": 7,
        "August": 8,
        "Aug": 8,
        "September": 9,
        "Sept": 9,
        "Sep": 9,
        "October": 10,
        "Oct": 10,
        "November": 11,
        "Nov": 11,
        "December": 12,
        "Dec": 12,
    }

    # Try "Month D-D"
    m = re.match(r"^([A-Za-z]+)\s*(\d+)\s*-\s*(\d+)\s*$", label)
    if m:
        mname = m.group(1)
        mnum = months.get(mname)
        if mnum:
            d1 = int(m.group(2))
            d2 = int(m.group(3))
            year = 2026 if mnum >= 7 else 2027
            return date(year, mnum, d1), date(year, mnum, d2)

    # Try "Month D - Month D" (cross-month)
    m = re.match(r"^([A-Za-z]+)\s*(\d+)\s*-\s*([A-Za-z]+)\s*(\d+)\s*$", label)
    if m:
        m1 = months.get(m.group(1))
        m2 = months.get(m.group(3))
        if m1 and m2:
            d1 = int(m.group(2))
            d2 = int(m.group(4))
            y1 = 2026 if m1 >= 7 else 2027
            y2 = 2026 if m2 >= 7 else 2027
            return date(y1, m1, d1), date(y2, m2, d2)

    return None


def _disambiguate_by_service(
    name: str, service: str, wstart: date, wend: date
) -> int | None:
    """If multiple residents could match the name, pick the one whose rotation
    during [wstart, wend] matches the service hint."""
    cleaned = re.sub(r"\s*\([^)]+\)\s*", " ", name).strip()
    parts = cleaned.split()
    candidates = []
    for r in residents:
        rparts = r["name"].split()
        # First-name only query
        if len(parts) == 1 and rparts[0].lower() == parts[0].lower():
            candidates.append(r)
        elif rparts[-1].lower() == parts[-1].lower():
            candidates.append(r)

    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]["index"]

    # Map the service hint to canonical rotation
    canonical, hint_loc, _ = map_rotation(service)
    raw_service = service.lower().strip()
    matches = []
    for r in candidates:
        for rot in rotations:
            if rot["resident_index"] != r["index"]:
                continue
            rs = date.fromisoformat(rot["start_date"])
            re_ = date.fromisoformat(rot["end_date"])
            if rs > wend or re_ < wstart:
                continue
            rot_text = rot["rotation"].lower()
            # Match canonical rotation, raw service text, or location hint
            if (
                rot_text == canonical.lower()
                or canonical.lower() in rot_text
                or raw_service in rot_text
                or (rot.get("location") and raw_service in rot["location"].lower())
            ):
                matches.append(r)
                break
    if len(matches) == 1:
        return matches[0]["index"]
    return None


def parse_vacation_file():
    """Parse Vacation Requests 26-27.xlsx 'Weeks' sheet and add vacations."""
    df = pd.read_excel(VACATION_FILE, sheet_name="Weeks", header=None)
    rows = df.values.tolist()

    # Skip the header row, walk the rest
    unmatched = []
    for row in rows[1:]:
        if not row or pd.isna(row[0]):
            continue
        week_label = str(row[0]).strip()
        if week_label.upper() in ("THANKSGIVING", "CHRISTMAS", "NEW YEARS"):
            continue
        if "CHIEF SPECIAL VACATIONS" in week_label.upper():
            break  # rest is special section we'll skip for now

        dates = _parse_week_dates(week_label)
        if not dates:
            continue
        wstart, wend = dates

        # Walk the resident slots: (Resident, Service, Notes) trios starting at col 1
        for trio_start in range(1, len(row), 3):
            if trio_start + 1 >= len(row):
                break
            name = row[trio_start]
            if pd.isna(name) or not str(name).strip():
                continue
            name_str = str(name).strip()

            # Skip holiday placeholders silently
            if name_str.upper() in HOLIDAY_PLACEHOLDERS:
                continue

            # Determine vac_type from notes
            notes = ""
            if trio_start + 2 < len(row) and not pd.isna(row[trio_start + 2]):
                notes = str(row[trio_start + 2]).lower()
            vac_type = "conference" if "conference" in notes else "vacation"

            # Service hint for disambiguation
            service_hint = ""
            if trio_start + 1 < len(row) and not pd.isna(row[trio_start + 1]):
                service_hint = str(row[trio_start + 1]).strip()

            idx = find_resident_idx(name_str)
            if idx is None and service_hint:
                idx = _disambiguate_by_service(name_str, service_hint, wstart, wend)
            if idx is None:
                unmatched.append((week_label, name_str))
                continue
            add_vacation(idx, wstart, wend, vac_type=vac_type)

    # Now handle the "Other Dates OFF" section and special vacations
    # Look for explicit date rows in the same sheet
    in_other = False
    for row in rows:
        if not row or pd.isna(row[0]):
            in_other = False
            continue
        first_cell = str(row[0]).strip()
        if first_cell.startswith("Other Dates OFF"):
            in_other = True
            continue
        if first_cell.startswith("Name of Resident"):
            continue
        if first_cell.startswith("CHIEF SPECIAL VACATIONS"):
            in_other = False
            continue

        if in_other and len(row) > 3:
            name = first_cell
            dates_raw = str(row[3]).strip() if not pd.isna(row[3]) else ""
            reason = (
                str(row[4]).strip().lower()
                if len(row) > 4 and not pd.isna(row[4])
                else ""
            )
            vac_type = (
                "conference"
                if "training" in reason or "conference" in reason
                else "vacation"
            )

            idx = find_resident_idx(name)
            if idx is None:
                unmatched.append((dates_raw, name))
                continue

            # Parse dates_raw — various formats
            parsed = _parse_explicit_dates(dates_raw)
            if parsed:
                for s, e in parsed:
                    add_vacation(idx, s, e, vac_type=vac_type)
            else:
                unmatched.append((dates_raw, name))

    # Parse "Sheet1" too — it has more "Other time off requests"
    df1 = pd.read_excel(VACATION_FILE, sheet_name="Sheet1", header=None)
    sheet1_rows = df1.values.tolist()
    for row in sheet1_rows:
        if not row or pd.isna(row[0]):
            continue
        first_cell = str(row[0]).strip()
        if first_cell in (
            "Other time off requests",
            "Other Services",
            "Other Programs",
            "Resident",
            "Name of Resident",
        ):
            continue

        if len(row) >= 4:
            name = first_cell
            dates_raw = str(row[3]).strip() if not pd.isna(row[3]) else ""
            reason = (
                str(row[4]).strip().lower()
                if len(row) > 4 and not pd.isna(row[4])
                else ""
            )
            vac_type = (
                "conference"
                if "training" in reason or "conference" in reason
                else "vacation"
            )

            idx = find_resident_idx(name)
            if idx is None:
                unmatched.append((dates_raw, name))
                continue

            parsed = _parse_explicit_dates(dates_raw)
            if parsed:
                for s, e in parsed:
                    add_vacation(idx, s, e, vac_type=vac_type)
            else:
                unmatched.append((dates_raw, name))

    return unmatched


def _parse_explicit_dates(raw: str) -> list[tuple[date, date]]:
    """Parse explicit date strings like '8/8-8/9/26', 'Dec. 7 & 9 2026',
    'March 1-7, 2027', '8/10-8/14', '1/18-1/22 OR 1/25-1/29', etc."""
    raw = raw.strip()
    if not raw:
        return []

    # "ANY" or "Any 2 weeks" — skip
    if raw.upper().startswith("ANY"):
        return []

    # "OR" — take only the first option
    if " OR " in raw.upper():
        raw = raw.split(" OR ")[0].strip()

    months = {
        "January": 1,
        "Jan": 1,
        "February": 2,
        "Feb": 2,
        "March": 3,
        "Mar": 3,
        "April": 4,
        "Apr": 4,
        "May": 5,
        "June": 6,
        "Jun": 6,
        "July": 7,
        "Jul": 7,
        "August": 8,
        "Aug": 8,
        "September": 9,
        "Sept": 9,
        "Sep": 9,
        "October": 10,
        "Oct": 10,
        "November": 11,
        "Nov": 11,
        "December": 12,
        "Dec": 12,
    }

    # "Month D-D, YYYY" or "Month D-D"
    m = re.match(r"^([A-Za-z]+)\.?\s*(\d+)\s*-\s*(\d+)(?:,?\s*(\d{4}))?$", raw)
    if m:
        mname = m.group(1)
        mnum = months.get(mname)
        if mnum:
            d1, d2 = int(m.group(2)), int(m.group(3))
            year = int(m.group(4)) if m.group(4) else (2026 if mnum >= 7 else 2027)
            return [(date(year, mnum, d1), date(year, mnum, d2))]

    # "Month. D & D YYYY" — discrete days
    m = re.match(r"^([A-Za-z]+)\.?\s*(\d+)\s*&\s*(\d+)\s*(\d{4})?$", raw)
    if m:
        mnum = months.get(m.group(1))
        if mnum:
            d1, d2 = int(m.group(2)), int(m.group(3))
            year = int(m.group(4)) if m.group(4) else (2026 if mnum >= 7 else 2027)
            return [
                (date(year, mnum, d1), date(year, mnum, d1)),
                (date(year, mnum, d2), date(year, mnum, d2)),
            ]

    # "M/D-M/D/YY" or "M/D-M/D" or "M/D/M/D"
    m = re.match(
        r"^(\d{1,2})/(\d{1,2})\s*[-/]\s*(\d{1,2})/(\d{1,2})(?:/\d{2,4})?$", raw
    )
    if m:
        m1, d1, m2, d2 = (int(x) for x in m.groups())
        y1 = 2026 if m1 >= 7 else 2027
        y2 = 2026 if m2 >= 7 else 2027
        return [(date(y1, m1, d1), date(y2, m2, d2))]

    # "M/D/YY"
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", raw)
    if m:
        return [
            (
                date(int(m.group(3)), int(m.group(1)), int(m.group(2))),
                date(int(m.group(3)), int(m.group(1)), int(m.group(2))),
            )
        ]

    return []


def parse_anesthesia_vacation_file():
    """Parse General Surgery Vacations.xlsx — anesthesia residents' vacations
    while rotating on GS. Rows: Resident Name, Rotation, Vaction Dates.
    """
    df = pd.read_excel(ANESTHESIA_VACATION_FILE, header=0)
    df.columns = [str(c).strip() for c in df.columns]
    name_col = next(c for c in df.columns if "name" in c.lower())
    date_col = next(c for c in df.columns if "date" in c.lower())

    unmatched = []
    for _, row in df.iterrows():
        name = row.get(name_col)
        date_label = row.get(date_col)
        if pd.isna(name) or pd.isna(date_label):
            continue
        name_str = str(name).strip()
        date_str = str(date_label).strip()

        idx = find_resident_idx(name_str)
        if idx is None:
            unmatched.append((date_str, name_str))
            continue

        dates = _parse_week_dates(date_str)
        if not dates:
            unmatched.append((date_str, name_str))
            continue
        wstart, wend = dates
        add_vacation(idx, wstart, wend, vac_type="vacation")

    return unmatched


# ---------- Main ----------


def main():
    parse_main_schedule()
    print(
        f"After main schedule: {len(residents)} residents, "
        f"{len(rotations)} rotations, {len(vacations)} vacations"
    )

    unmatched = parse_vacation_file()
    print(f"After vacations: {len(vacations)} vacations")
    if unmatched:
        print(f"\nUnmatched vacation entries ({len(unmatched)}):")
        for week, name in unmatched:
            print(f"  - {week}: {name}")

    anes_unmatched = parse_anesthesia_vacation_file()
    print(f"After anesthesia vacations: {len(vacations)} vacations")
    if anes_unmatched:
        print(f"\nUnmatched anesthesia vacation entries ({len(anes_unmatched)}):")
        for dates_raw, name in anes_unmatched:
            print(f"  - {dates_raw}: {name}")

    if _unknown_rotations:
        print(
            f"\nNon-elective rotations not in VALID_ROTATIONS "
            f"({len(_unknown_rotations)}):"
        )
        for r in sorted(_unknown_rotations):
            print(f"  - {r!r}")

    data = {
        "residents": residents,
        "rotations": rotations,
        "vacations": vacations,
    }

    with open("/tmp/parsed_schedule.json", "w") as f:
        json.dump(data, f, indent=2, default=str)
    print("\nWrote /tmp/parsed_schedule.json")


if __name__ == "__main__":
    main()
