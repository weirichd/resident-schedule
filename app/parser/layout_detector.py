"""Auto-detect column layout from Excel schedule files."""

import re

import pandas as pd

# Pattern matching date ranges like "7/1-7/31" or "8/25-10/19"
DATE_RANGE_PATTERN = re.compile(r"\d{1,2}/\d{1,2}\s*-\s*\d{1,2}/\d{1,2}")


class LayoutInfo:
    """Detected column layout for a schedule section."""

    def __init__(
        self,
        name_col: int,
        pgy_col: int | None,
        rotation_start_col: int,
        date_row_idx: int,
    ):
        self.name_col = name_col
        self.pgy_col = pgy_col
        self.rotation_start_col = rotation_start_col
        self.date_row_idx = date_row_idx

    def __repr__(self) -> str:
        return (
            f"LayoutInfo(name_col={self.name_col}, pgy_col={self.pgy_col}, "
            f"rotation_start_col={self.rotation_start_col}, "
            f"date_row_idx={self.date_row_idx})"
        )


def _is_date_range(val) -> bool:
    """Check if a value looks like a date range (e.g., '7/1-8/25')."""
    if pd.isna(val):
        return False
    return bool(DATE_RANGE_PATTERN.match(str(val).strip()))


def _count_date_cells(row: pd.Series) -> int:
    """Count how many cells in a row match the date range pattern."""
    return sum(1 for val in row if _is_date_range(val))


def find_dates_label_col(row: pd.Series) -> int | None:
    """Find the column index that contains 'Dates' in a row."""
    for idx, val in row.items():
        if pd.notna(val) and str(val).strip() == "Dates":
            return int(idx)
    return None


def detect_layout(df: pd.DataFrame, start_row: int = 0) -> LayoutInfo | None:
    """Detect the column layout starting from a given row.

    Strategy:
    1. Find a row containing "Dates" label → that column is name_col
    2. pgy_col = name_col - 1 (if it contains numeric PGY values)
    3. rotation_start_col = name_col + 1
    4. Fall back to scanning for rows with ≥3 date-range cells
    """
    for idx in range(start_row, min(start_row + 50, len(df))):
        row = df.iloc[idx]

        # Strategy 1: Look for "Dates" label
        dates_col = find_dates_label_col(row)
        if dates_col is not None:
            # Verify this row also has date ranges after the Dates label
            date_count = _count_date_cells(row)
            if date_count >= 3:
                name_col = dates_col
                pgy_col = dates_col - 1 if dates_col > 0 else None
                rotation_start_col = dates_col + 1
                return LayoutInfo(
                    name_col=name_col,
                    pgy_col=pgy_col,
                    rotation_start_col=rotation_start_col,
                    date_row_idx=idx,
                )

        # Strategy 2: Look for rows with many date ranges
        date_count = _count_date_cells(row)
        if date_count >= 3:
            # Find the first date-range column
            first_date_col = None
            for col_idx, val in row.items():
                if _is_date_range(val):
                    first_date_col = int(col_idx)
                    break

            if first_date_col is not None:
                name_col = first_date_col - 1
                pgy_col = first_date_col - 2 if first_date_col >= 2 else None
                rotation_start_col = first_date_col
                return LayoutInfo(
                    name_col=name_col,
                    pgy_col=pgy_col,
                    rotation_start_col=rotation_start_col,
                    date_row_idx=idx,
                )

    return None


def detect_all_sections(df: pd.DataFrame) -> list[tuple[int, LayoutInfo]]:
    """Detect all schedule sections in a dataframe.

    Returns list of (start_row, LayoutInfo) tuples.
    Each section starts at a date row.
    """
    sections = []
    search_from = 0

    while search_from < len(df):
        layout = detect_layout(df, start_row=search_from)
        if layout is None:
            break

        sections.append((layout.date_row_idx, layout))
        # Search for next section after current date row + at least a few data rows
        search_from = layout.date_row_idx + 2

    return sections
