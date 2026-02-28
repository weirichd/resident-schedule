"""LLM-powered orchestrator for parsing Excel schedule files.

Drop-in alternative to excel_parser.py that uses LLM-based cell parsing
instead of the rules-based parser. Layout detection and row classification
are unchanged.
"""

import logging
import os
import re

import pandas as pd

from app.parser.cell_parser import (
    ParsedCell,
    clean_resident_name,
    parse_rotation_cell,
    parse_vacation_annotation_row,
    parse_visiting_name,
)
from app.parser.excel_parser import (
    ScheduleRow,
    _attach_vacations_to_results,
    _compute_split_dates,
    _detect_year,
    _extract_name,
    _extract_pgy,
    _parse_dates_row,
)
from app.parser.layout_detector import LayoutInfo, detect_layout
from app.parser.llm_cell_parser import (
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_OLLAMA_MODEL,
    parse_rotation_cells_llm_batch,
)
from app.parser.row_classifier import RowType, classify_row

logger = logging.getLogger(__name__)

# Maximum cells per LLM batch call
MAX_BATCH_SIZE = 40


def parse_excel_llm(
    file_path: str,
    year: int | None = None,
    debug: bool = False,
    model: str | None = None,
    ollama_model: str | None = None,
) -> tuple[list[ScheduleRow], int]:
    """Parse an Excel schedule file using LLM-powered cell parsing.

    Args:
        file_path: Path to the Excel file.
        year: Academic year start (e.g., 2025 for 2025-2026).
        debug: If True, log detailed parsing info.
        model: Anthropic model name override.
        ollama_model: Ollama model name override.

    Returns:
        Tuple of (list of ScheduleRow objects, detected academic year).
    """
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Determine LLM backend
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    use_ollama = not api_key
    if use_ollama:
        logger.info(
            "No ANTHROPIC_API_KEY set. Using ollama backend "
            "(model: %s)",
            ollama_model or DEFAULT_OLLAMA_MODEL,
        )
    else:
        logger.info(
            "Using Anthropic backend (model: %s)",
            model or DEFAULT_ANTHROPIC_MODEL,
        )

    # Read the file
    if file_path.endswith(".xlsb"):
        df = pd.read_excel(file_path, engine="pyxlsb", header=None)
    else:
        df = pd.read_excel(file_path, header=None)

    df.columns = range(df.columns.size)

    # Clean non-breaking spaces
    for col in df:
        df.loc[df[col] == "\xa0", col] = None

    # Auto-detect year
    if year is None:
        year = _detect_year(df, file_path)
        logger.info("Auto-detected year: %d", year)

    results: list[ScheduleRow] = []

    # First pass: collect structure (dates, residents, row types)
    # Second pass: batch LLM calls per resident row
    current_dates: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    current_layout: LayoutInfo | None = None
    section_pgy: str | None = None
    section_institution: str | None = None
    prev_row_type: str | None = None
    prev_resident_data: list[tuple[int, ParsedCell]] | None = None
    prev_resident_name: str | None = None

    # Collect all cells to parse per resident row for batching
    pending_rows: list[dict] = []

    for row_idx in range(len(df)):
        row = df.iloc[row_idx]

        # Detect layout changes
        layout_candidate = detect_layout(df, start_row=row_idx)
        if layout_candidate and layout_candidate.date_row_idx == row_idx:
            current_layout = layout_candidate
            current_dates = _parse_dates_row(
                row, current_layout.rotation_start_col, year
            )
            logger.debug(
                "Row %d: DATE ROW with %d date ranges, layout=%s",
                row_idx,
                len(current_dates),
                current_layout,
            )
            prev_row_type = RowType.DATE
            prev_resident_data = None
            continue

        if current_layout is None:
            pgy_match = re.search(
                r"PGY[\s-]*(\d)", str(row.tolist()), re.IGNORECASE
            )
            if pgy_match:
                section_pgy = pgy_match.group(1)
                logger.debug(
                    "Row %d: SECTION HEADER PGY-%s", row_idx, section_pgy
                )

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
            logger.debug(
                "Row %d: SECTION HEADER PGY-%s", row_idx, section_pgy
            )

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
                section_institution = None

        if row_type == RowType.DATE:
            current_dates = _parse_dates_row(
                row, current_layout.rotation_start_col, year
            )
            logger.debug(
                "Row %d: DATE ROW with %d date ranges",
                row_idx,
                len(current_dates),
            )
            prev_row_type = RowType.DATE
            prev_resident_data = None
            continue

        if row_type == RowType.VACATION_ANNOTATION:
            # Process any pending rows first so vacations attach
            if pending_rows:
                _process_pending_batch(
                    pending_rows,
                    results,
                    model=model,
                    use_ollama=use_ollama,
                    ollama_model=ollama_model,
                )
                pending_rows = []

            if prev_resident_data is not None:
                vac_data = parse_vacation_annotation_row(
                    row, current_layout.rotation_start_col
                )
                _attach_vacations_to_results(
                    results, vac_data, prev_resident_name
                )
            logger.debug("Row %d: VACATION ANNOTATION", row_idx)
            prev_row_type = RowType.VACATION_ANNOTATION
            continue

        if row_type == RowType.RESIDENT:
            # Flush previous pending rows before processing new ones
            if pending_rows:
                _process_pending_batch(
                    pending_rows,
                    results,
                    model=model,
                    use_ollama=use_ollama,
                    ollama_model=ollama_model,
                )
                pending_rows = []

            name = _extract_name(row, current_layout.name_col)
            pgy = _extract_pgy(
                row, current_layout.pgy_col, section_pgy
            )

            if not name or pgy is None:
                logger.warning(
                    "Row %d: Incomplete resident data: name=%s, pgy=%s",
                    row_idx,
                    name,
                    pgy,
                )
                prev_row_type = RowType.SKIP
                continue

            # Check for visiting resident
            visiting = parse_visiting_name(name)
            is_visiting = (
                visiting is not None or section_institution is not None
            )
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
                "Row %d: RESIDENT %s PGY-%s%s",
                row_idx,
                name,
                pgy,
                f" (visiting from {institution})" if is_visiting else "",
            )

            # Collect cells for this resident
            row_cells: list[dict] = []
            for block_idx, col_idx in enumerate(
                range(current_layout.rotation_start_col, len(row))
            ):
                if block_idx >= len(current_dates):
                    break

                cell_val = row.get(col_idx)
                if pd.isna(cell_val) or not str(cell_val).strip():
                    continue

                block_start, block_end = current_dates[block_idx]
                row_cells.append(
                    {
                        "cell_id": col_idx,
                        "cell_value": str(cell_val).strip(),
                        "block_start": block_start,
                        "block_end": block_end,
                        "name": name,
                        "pgy": pgy,
                        "is_visiting": is_visiting,
                        "institution": institution,
                    }
                )

            if row_cells:
                pending_rows.extend(row_cells)

            prev_resident_name = name
            prev_resident_data = []  # placeholder, updated after batch
            prev_row_type = RowType.RESIDENT
            continue

        # Skip row
        logger.debug("Row %d: SKIP", row_idx)
        prev_row_type = row_type

    # Flush any remaining pending rows
    if pending_rows:
        _process_pending_batch(
            pending_rows,
            results,
            model=model,
            use_ollama=use_ollama,
            ollama_model=ollama_model,
        )

    logger.info("Parsed %d schedule entries", len(results))
    return results, year


def _process_pending_batch(
    pending: list[dict],
    results: list[ScheduleRow],
    model: str | None = None,
    use_ollama: bool = False,
    ollama_model: str | None = None,
) -> None:
    """Process a batch of pending cells through the LLM.

    Batches cells into groups of MAX_BATCH_SIZE and converts results
    to ScheduleRow objects appended to results.
    """
    if not pending:
        return

    # Build batch for LLM
    cells_for_llm = [
        (item["cell_id"], item["cell_value"]) for item in pending
    ]

    # Process in batches
    all_parsed: dict[int, list[ParsedCell]] = {}
    for batch_start in range(0, len(cells_for_llm), MAX_BATCH_SIZE):
        batch = cells_for_llm[batch_start: batch_start + MAX_BATCH_SIZE]
        batch_results = parse_rotation_cells_llm_batch(
            batch,
            model=model,
            use_ollama=use_ollama,
            ollama_model=ollama_model,
        )
        all_parsed.update(batch_results)

    # Convert to ScheduleRow objects
    for item in pending:
        cell_id = item["cell_id"]
        parsed_cells = all_parsed.get(cell_id)

        if not parsed_cells:
            # Try rules-based fallback
            parsed_cells = parse_rotation_cell(item["cell_value"])
            if not parsed_cells:
                continue

        block_start = item["block_start"]
        block_end = item["block_end"]
        name = item["name"]
        pgy = item["pgy"]
        is_visiting = item["is_visiting"]
        institution = item["institution"]

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
        elif len(parsed_cells) == 2:
            split_dates = _compute_split_dates(block_start, block_end)
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
        else:
            # More than 2 split rotations (unusual) — treat each
            for cell in parsed_cells:
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
