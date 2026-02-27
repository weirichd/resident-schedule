"""Main orchestrator for parsing Excel schedule files."""

import logging
import re
from dataclasses import dataclass, field

import pandas as pd

from app.parser.cell_parser import (
    ParsedCell,
    VacationInfo,
    clean_resident_name,
    parse_rotation_cell,
    parse_vacation_annotation_row,
    parse_visiting_name,
)
from app.parser.layout_detector import (
    DATE_RANGE_PATTERN,
    LayoutInfo,
    detect_layout,
)
from app.parser.rotation_map import is_common_rotation
from app.parser.row_classifier import RowType, classify_row

logger = logging.getLogger(__name__)


@dataclass
class ScheduleRow:
    """A single parsed schedule entry."""

    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD
    name: str
    pgy: int
    rotation: str
    rotation_full: str
    location: str | None = None
    is_visiting: bool = False
    visiting_institution: str | None = None
    vacations: list[VacationInfo] = field(default_factory=list)


def parse_date(s: str, year: int) -> pd.Timestamp:
    """Parse a M/D date string into a Timestamp.

    Academic year convention: months July-Dec use `year`, Jan-June use `year+1`.
    """
    s = s.strip()
    month, day = s.split("/")
    month, day = int(month), int(day)

    if month <= 6:
        return pd.Timestamp(year + 1, month, day)
    return pd.Timestamp(year, month, day)


def parse_date_range(s: str, year: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Parse a 'M/D-M/D' date range string."""
    s = s.strip()
    parts = re.split(r"\s*-\s*", s, maxsplit=1)
    start = parse_date(parts[0], year)
    end = parse_date(parts[1], year)
    return start, end


def _snap_to_sunday(dt: pd.Timestamp) -> pd.Timestamp:
    """Find the nearest Sunday at or before the given date."""
    days_since_sunday = (dt.weekday() + 1) % 7
    return dt - pd.Timedelta(days=days_since_sunday)


def _compute_split_dates(
    block_start: pd.Timestamp, block_end: pd.Timestamp, num_parts: int = 2
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Split a block's date range into equal parts for "/" rotations.

    Split points are snapped to the nearest Sunday boundary.
    """
    if num_parts < 2:
        return [(block_start, block_end)]

    total_days = (block_end - block_start).days
    ranges = []
    current_start = block_start

    for i in range(num_parts - 1):
        split_point = block_start + pd.Timedelta(
            days=total_days * (i + 1) // num_parts
        )
        split_sunday = _snap_to_sunday(split_point)
        ranges.append((current_start, split_sunday))
        current_start = split_sunday + pd.Timedelta(days=1)

    ranges.append((current_start, block_end))
    return ranges


def _parse_dates_row(
    row: pd.Series, rotation_start_col: int, year: int
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Parse a date row and return list of (start, end) tuples."""
    dates = []
    for col_idx in range(rotation_start_col, len(row)):
        val = row.get(col_idx)
        if pd.notna(val) and DATE_RANGE_PATTERN.match(str(val).strip()):
            try:
                start, end = parse_date_range(str(val).strip(), year)
                dates.append((start, end))
            except (ValueError, IndexError):
                logger.warning(f"Could not parse date range: {val}")
    return dates


def _extract_pgy(
    row: pd.Series, pgy_col: int | None, section_pgy: str | None
) -> int | None:
    """Extract PGY level from row or section context."""
    if pgy_col is not None:
        val = row.get(pgy_col)
        if pd.notna(val):
            try:
                return int(float(str(val)))
            except (ValueError, TypeError):
                pass

    if section_pgy is not None:
        return int(section_pgy)

    return None


def _extract_name(row: pd.Series, name_col: int) -> str:
    """Extract resident name from the name column."""
    val = row.get(name_col)
    if pd.isna(val):
        return ""
    return str(val).strip()


def parse_excel(
    file_path: str, year: int | None = None, debug: bool = False
) -> tuple[list[ScheduleRow], int]:
    """Parse an Excel schedule file and return structured data.

    Args:
        file_path: Path to the Excel file.
        year: Academic year start (e.g., 2025 for 2025-2026). Auto-detected if None.
        debug: If True, log detailed parsing info.

    Returns:
        Tuple of (list of ScheduleRow objects, detected academic year).
    """
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Read the file
    if file_path.endswith(".xlsb"):
        df = pd.read_excel(file_path, engine="pyxlsb", header=None)
    else:
        df = pd.read_excel(file_path, header=None)

    df.columns = range(df.columns.size)

    # Clean non-breaking spaces
    for col in df:
        df.loc[df[col] == "\xa0", col] = None

    # Auto-detect year from filename or title row
    if year is None:
        year = _detect_year(df, file_path)
        logger.info(f"Auto-detected year: {year}")

    results: list[ScheduleRow] = []

    # Process the sheet section by section
    # We scan top to bottom, finding date rows and processing residents under them
    current_dates: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    current_layout: LayoutInfo | None = None
    section_pgy: str | None = None
    section_institution: str | None = None
    prev_row_type: str | None = None
    prev_resident_data: list[tuple[int, ParsedCell]] | None = None  # (col_idx, cell)
    prev_resident_name: str | None = None

    for row_idx in range(len(df)):
        row = df.iloc[row_idx]

        # Detect layout changes (new date row = new section)
        layout_candidate = detect_layout(df, start_row=row_idx)
        if layout_candidate and layout_candidate.date_row_idx == row_idx:
            current_layout = layout_candidate
            current_dates = _parse_dates_row(
                row, current_layout.rotation_start_col, year
            )
            logger.debug(
                f"Row {row_idx}: DATE ROW with {len(current_dates)} date ranges, "
                f"layout={current_layout}"
            )
            prev_row_type = RowType.DATE
            prev_resident_data = None
            continue

        if current_layout is None:
            # Haven't found a layout yet — check for section headers
            pgy_match = re.search(r"PGY[\s-]*(\d)", str(row.tolist()), re.IGNORECASE)
            if pgy_match:
                section_pgy = pgy_match.group(1)
                logger.debug(f"Row {row_idx}: SECTION HEADER PGY-{section_pgy}")

            # Check for visiting section context
            row_text = " ".join(str(v) for v in row if pd.notna(v))
            for inst in [
                "DOCTORS",
                "MOUNT CARMEL",
                "RIVERSIDE",
                "KETTERING",
                "PARKVIEW",
            ]:
                if inst in row_text.upper():
                    section_institution = inst.title()
                    if "DOCTOR" in inst:
                        section_institution = "Doctors Hospital"
                    elif "CARMEL" in inst:
                        section_institution = "Mount Carmel"
                    break

            prev_row_type = RowType.SKIP
            continue

        # Classify the row
        row_type, pgy_ctx = classify_row(
            row,
            current_layout.name_col,
            current_layout.pgy_col,
            current_layout.rotation_start_col,
            prev_row_type,
        )

        if pgy_ctx:
            section_pgy = pgy_ctx
            logger.debug(f"Row {row_idx}: SECTION HEADER PGY-{section_pgy}")

            # Check for institution context in section header
            row_text = " ".join(str(v) for v in row if pd.notna(v))
            for inst in [
                "DOCTORS",
                "MOUNT CARMEL",
                "RIVERSIDE",
                "KETTERING",
                "PARKVIEW",
            ]:
                if inst in row_text.upper():
                    section_institution = inst.title()
                    if "DOCTOR" in inst:
                        section_institution = "Doctors Hospital"
                    elif "CARMEL" in inst:
                        section_institution = "Mount Carmel"
                    break
            else:
                # Reset institution if this is a new PGY section without institution
                section_institution = None

        if row_type == RowType.DATE:
            current_dates = _parse_dates_row(
                row, current_layout.rotation_start_col, year
            )
            logger.debug(
                f"Row {row_idx}: DATE ROW with {len(current_dates)} date ranges"
            )
            prev_row_type = RowType.DATE
            prev_resident_data = None
            continue

        if row_type == RowType.VACATION_ANNOTATION:
            # Attach vacation data to previous resident's schedule rows
            if prev_resident_data is not None:
                vac_data = parse_vacation_annotation_row(
                    row, current_layout.rotation_start_col
                )
                _attach_vacations_to_results(results, vac_data, prev_resident_name)
            logger.debug(f"Row {row_idx}: VACATION ANNOTATION")
            prev_row_type = RowType.VACATION_ANNOTATION
            continue

        if row_type == RowType.RESIDENT:
            name = _extract_name(row, current_layout.name_col)
            pgy = _extract_pgy(row, current_layout.pgy_col, section_pgy)

            if not name or pgy is None:
                logger.warning(
                    f"Row {row_idx}: Incomplete resident data: name={name}, pgy={pgy}"
                )
                prev_row_type = RowType.SKIP
                continue

            # Check for visiting resident
            visiting = parse_visiting_name(name)
            is_visiting = visiting is not None or section_institution is not None
            institution = None
            if visiting:
                name = visiting.name
                institution = visiting.institution
            elif section_institution:
                institution = section_institution
            else:
                # Strip specialty track suffixes ("Song - Urology" → "Song")
                name = clean_resident_name(name)

            logger.debug(
                f"Row {row_idx}: RESIDENT {name} PGY-{pgy}"
                + (f" (visiting from {institution})" if is_visiting else "")
            )

            # Parse each rotation cell
            resident_cells: list[tuple[int, ParsedCell]] = []
            for block_idx, col_idx in enumerate(
                range(current_layout.rotation_start_col, len(row))
            ):
                if block_idx >= len(current_dates):
                    break

                cell_val = row.get(col_idx)
                block_start, block_end = current_dates[block_idx]

                parsed_cells = parse_rotation_cell(cell_val)

                if not parsed_cells:
                    continue

                if len(parsed_cells) == 1:
                    cell = parsed_cells[0]
                    results.append(
                        ScheduleRow(
                            start_date=block_start.strftime("%Y-%m-%d"),
                            end_date=block_end.strftime("%Y-%m-%d"),
                            name=name,
                            pgy=pgy,
                            rotation=cell.rotation,
                            rotation_full=cell.rotation_full,
                            location=cell.location,
                            is_visiting=is_visiting,
                            visiting_institution=institution,
                            vacations=cell.vacations,
                        )
                    )
                    resident_cells.append((col_idx, cell))
                else:
                    # Split rotation (2-way or 3-way) — divide the block dates
                    split_dates = _compute_split_dates(
                        block_start, block_end, len(parsed_cells)
                    )
                    for i, cell in enumerate(parsed_cells):
                        s_start, s_end = split_dates[i]
                        results.append(
                            ScheduleRow(
                                start_date=s_start.strftime("%Y-%m-%d"),
                                end_date=s_end.strftime("%Y-%m-%d"),
                                name=name,
                                pgy=pgy,
                                rotation=cell.rotation,
                                rotation_full=cell.rotation_full,
                                location=cell.location,
                                is_visiting=is_visiting,
                                visiting_institution=institution,
                                vacations=cell.vacations,
                            )
                        )
                    resident_cells.append((col_idx, parsed_cells[0]))

            prev_resident_data = resident_cells
            prev_resident_name = name
            prev_row_type = RowType.RESIDENT
            continue

        # Skip row
        logger.debug(f"Row {row_idx}: SKIP")
        prev_row_type = row_type

    logger.info(f"Parsed {len(results)} schedule entries")
    return results, year


def _attach_vacations_to_results(
    results: list[ScheduleRow],
    vac_data: dict[int, list[VacationInfo]],
    resident_name: str | None,
) -> None:
    """Attach vacation annotation data to the most recent results for a resident."""
    if not resident_name or not vac_data:
        return

    # Find recent results for this resident (in reverse order)
    resident_results = [r for r in results if r.name == resident_name]

    for col_offset, vacations in vac_data.items():
        # Try to match by position — vacation annotations correspond to the
        # same column positions as the rotation they annotate
        for vac in vacations:
            # Add to the most recent result for this resident
            # that doesn't already have this vacation
            for res in reversed(resident_results):
                if not any(
                    v.vac_start == vac.vac_start and v.vac_end == vac.vac_end
                    for v in res.vacations
                ):
                    res.vacations.append(vac)
                    break


def _detect_year(df: pd.DataFrame, file_path: str) -> int:
    """Auto-detect the academic year from file content or name."""
    # Try filename first
    year_match = re.search(r"(\d{4})\s*[-–]\s*\d{4}", file_path)
    if year_match:
        return int(year_match.group(1))

    # Try title row
    for idx in range(min(5, len(df))):
        for val in df.iloc[idx]:
            if pd.notna(val):
                m = re.search(r"(\d{4})\s*[-–]\s*\d{4}", str(val))
                if m:
                    return int(m.group(1))

    # Fall back to current year
    current = pd.Timestamp.now()
    if current.month >= 7:
        return current.year
    return current.year - 1


def schedule_rows_to_dataframe(rows: list[ScheduleRow]) -> pd.DataFrame:
    """Convert ScheduleRow list to a DataFrame for database insertion."""
    records = []
    for r in rows:
        records.append(
            {
                "start_date": r.start_date,
                "end_date": r.end_date,
                "name": r.name,
                "pgy": r.pgy,
                "rotation": r.rotation,
                "rotation_full": r.rotation_full,
                "location": r.location,
                "is_visiting": 1 if r.is_visiting else 0,
                "visiting_institution": r.visiting_institution,
            }
        )
    return pd.DataFrame(records)


def resolve_vacation_dates(rows: list[ScheduleRow], year: int) -> None:
    """Resolve M/D vacation dates to full YYYY-MM-DD format in place.

    Uses the academic year convention: Jul-Dec → year, Jan-Jun → year+1.
    """
    for r in rows:
        for v in r.vacations:
            if "/" in v.vac_start and len(v.vac_start) <= 5:
                try:
                    start_ts = parse_date(v.vac_start, year)
                    v.vac_start = start_ts.strftime("%Y-%m-%d")
                except (ValueError, IndexError):
                    pass
            if "/" in v.vac_end and len(v.vac_end) <= 5:
                try:
                    end_ts = parse_date(v.vac_end, year)
                    v.vac_end = end_ts.strftime("%Y-%m-%d")
                except (ValueError, IndexError):
                    pass


def extract_vacations(rows: list[ScheduleRow]) -> list[dict]:
    """Extract vacation records linked to schedule entries.

    Returns list of dicts ready for insertion.
    Note: schedule_id must be set after schedule rows are inserted.
    """
    vacations = []
    for r in rows:
        for v in r.vacations:
            vacations.append(
                {
                    "name": r.name,
                    "rotation": r.rotation,
                    "start_date": r.start_date,
                    "vac_start": v.vac_start,
                    "vac_end": v.vac_end,
                    "vac_type": v.vac_type,
                    "approved_status": v.approved_status,
                    "covered_by": v.covered_by,
                }
            )
    return vacations


def get_rotation_map_entries(rows: list[ScheduleRow]) -> list[dict]:
    """Build rotation_map entries from parsed data."""
    seen: dict[str, str] = {}
    for r in rows:
        if r.rotation not in seen and r.rotation != "VACATION":
            seen[r.rotation] = r.rotation_full

    entries = []
    for abbrev, full_name in sorted(seen.items()):
        entries.append(
            {
                "abbrev": abbrev,
                "full_name": full_name,
                "is_common": 1 if is_common_rotation(full_name) else 0,
            }
        )
    return entries
