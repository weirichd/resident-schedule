"""Automatic row classification for Excel schedule files."""

import re

import pandas as pd

from app.parser.layout_detector import DATE_RANGE_PATTERN

# Patterns
PGY_HEADER_PATTERN = re.compile(r"PGY[\s-]*(\d)", re.IGNORECASE)
VACATION_PATTERN = re.compile(
    r"(Vac|Conf|VACATION)\s*[:/]?\s*\d{1,2}/\d{1,2}", re.IGNORECASE
)
BLOCK_LABEL_PATTERN = re.compile(r"^Block\s+\d+$", re.IGNORECASE)
# Aggregate/count rows: "Anesthesia x 22", "EM x 18", "SICU Interns", "SICU total",
# "ACS R2s", "TOTAL TCCB", "SICU R2"
AGGREGATE_PATTERN = re.compile(
    r"(?:\bx\s+\d+\b"  # "x 22", "x 18"
    r"|\b(?:total|interns|R2s|R2)\s*$"  # ends with total/interns/R2s/R2
    r"|^TOTAL\b)",  # starts with TOTAL
    re.IGNORECASE,
)
TITLE_KEYWORDS = {
    "Rotation Schedule",
    "General Surgery",
    "DO NOT MOVE",
    "CONFIRMED",
    "PENDING",
    "Legend:",
    "NOTES",
    "ABSITE",
    "Applications",
    "THESE ROTATION",
    "WILL NEED",
    "VASC LAB",
    "opens late",
    "Opens July",
    "interviews",
    "4th year match",
    "5th year match",
}


class RowType:
    DATE = "date"
    RESIDENT = "resident"
    VACATION_ANNOTATION = "vacation_annotation"
    SECTION_HEADER = "section_header"
    SKIP = "skip"


def _is_blank_row(row: pd.Series) -> bool:
    """Check if a row is blank (all NaN or whitespace)."""
    for val in row:
        if pd.notna(val) and str(val).strip():
            return False
    return True


def _has_title_keyword(row: pd.Series) -> bool:
    """Check if row contains known title/header keywords to skip."""
    row_text = " ".join(str(v) for v in row if pd.notna(v))
    for keyword in TITLE_KEYWORDS:
        if keyword.lower() in row_text.lower():
            return True
    return False


def _is_block_label_row(row: pd.Series) -> bool:
    """Check if row contains only block labels like 'Block 1', 'Block 2', etc."""
    non_null = [str(v).strip() for v in row if pd.notna(v) and str(v).strip()]
    if not non_null:
        return False
    return all(BLOCK_LABEL_PATTERN.match(v) for v in non_null)


def _is_week_label_row(row: pd.Series) -> bool:
    """Check if row contains week labels like '8 weeks', '7 weeks'."""
    non_null = [str(v).strip() for v in row if pd.notna(v) and str(v).strip()]
    if not non_null:
        return False
    return all(re.match(r"^\d+\s+weeks?$", v, re.IGNORECASE) for v in non_null)


def _count_date_ranges(row: pd.Series) -> int:
    """Count cells matching date range pattern."""
    count = 0
    for val in row:
        if pd.notna(val) and DATE_RANGE_PATTERN.match(str(val).strip()):
            count += 1
    return count


def _is_pgy_header(row: pd.Series) -> str | None:
    """Check if row is a PGY section header (e.g., 'PGY-5').

    Returns PGY value as string if found, None otherwise.
    """
    for val in row:
        if pd.notna(val):
            m = PGY_HEADER_PATTERN.match(str(val).strip())
            if m:
                return m.group(1)
    return None


def _is_vacation_annotation_row(
    row: pd.Series, name_col: int, rotation_start_col: int
) -> bool:
    """Check if row is a vacation annotation row (row below a resident).

    These rows have no name/PGY but contain vacation patterns in rotation columns.
    """
    # Should not have a name or PGY value
    if pd.notna(row.get(name_col)) and str(row.get(name_col, "")).strip():
        name_val = str(row[name_col]).strip()
        # Allow "Dates" and empty strings through
        if name_val and name_val != "Dates":
            return False

    # Check rotation columns for vacation patterns
    has_vacation = False
    for col_idx in range(rotation_start_col, len(row)):
        val = row.get(col_idx)
        if pd.notna(val):
            val_str = str(val).strip()
            if val_str and VACATION_PATTERN.search(val_str):
                has_vacation = True
            elif (
                val_str and not val_str.startswith("[") and not val_str.startswith("(")
            ):
                # Has non-vacation content — not a pure annotation row
                return False
    return has_vacation


def _is_resident_row(row: pd.Series, name_col: int, pgy_col: int | None) -> bool:
    """Check if row looks like a resident data row."""
    # Must have something in the name column
    name_val = row.get(name_col)
    if pd.isna(name_val) or not str(name_val).strip():
        return False

    name_str = str(name_val).strip()

    # Skip known non-name values
    if name_str in ("Dates", ""):
        return False
    if BLOCK_LABEL_PATTERN.match(name_str):
        return False
    # Skip aggregate/count rows like "Anesthesia x 22", "SICU Interns", "ACS total"
    if AGGREGATE_PATTERN.search(name_str):
        return False

    # Check for PGY value
    if pgy_col is not None:
        pgy_val = row.get(pgy_col)
        if pd.notna(pgy_val):
            try:
                pgy_int = int(float(str(pgy_val)))
                if 1 <= pgy_int <= 6:
                    return True
            except (ValueError, TypeError):
                pass

    # Even without a valid PGY, if the name looks like a person name
    # and there's rotation data, treat as resident
    has_rotation_data = False
    for col_idx in range(name_col + 1, min(name_col + 15, len(row))):
        val = row.get(col_idx)
        if pd.notna(val) and str(val).strip():
            has_rotation_data = True
            break

    # Check if name looks like a name (not a number, not a keyword)
    if has_rotation_data and not name_str.replace(".", "").isdigit():
        return True

    return False


def classify_row(
    row: pd.Series,
    name_col: int,
    pgy_col: int | None,
    rotation_start_col: int,
    prev_row_type: str | None = None,
) -> tuple[str, str | None]:
    """Classify a single row.

    Returns (row_type, pgy_context) where pgy_context is set for section headers.
    """
    # Blank row
    if _is_blank_row(row):
        return RowType.SKIP, None

    # Block label row (Block 1, Block 2, etc.)
    if _is_block_label_row(row):
        return RowType.SKIP, None

    # Week label row
    if _is_week_label_row(row):
        return RowType.SKIP, None

    # PGY section header
    pgy_val = _is_pgy_header(row)
    if pgy_val is not None:
        # Check if it's truly a header (not a resident row with PGY in it)
        date_count = _count_date_ranges(row)
        if date_count == 0:
            return RowType.SECTION_HEADER, pgy_val

    # Date row
    date_count = _count_date_ranges(row)
    if date_count >= 3:
        return RowType.DATE, None

    # Vacation annotation row (must check before resident since it may share columns)
    if prev_row_type == RowType.RESIDENT:
        if _is_vacation_annotation_row(row, name_col, rotation_start_col):
            return RowType.VACATION_ANNOTATION, None

    # Resident row — check BEFORE title keywords because title keywords like
    # "CONFIRMED", "PENDING", "interviews", "opens late", "4th year match" etc.
    # can appear in status columns (C0) or notes columns (C13/C14) of valid
    # resident rows, causing false positives in _has_title_keyword.
    if _is_resident_row(row, name_col, pgy_col):
        return RowType.RESIDENT, None

    # Title/metadata rows
    if _has_title_keyword(row):
        return RowType.SKIP, None

    return RowType.SKIP, None
